from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime

from app.models.watchlist import Watchlist, CustomList, CustomListItem
from app.models.movie import Movie
from app.schemas.watchlist import (
    WatchlistAdd,
    WatchlistUpdate,
    WatchlistStats,
    CustomListCreate,
    CustomListUpdate,
    CustomListItemAdd
)
from app.services.tmdb_service import TMDBService


class WatchlistService:
    """Service for watchlist operations"""

    @staticmethod
    def _ensure_movie_exists(db: Session, tmdb_id: int) -> int:
        """
        Ensure movie exists in DB, fetch from TMDB if not
        Returns the internal movie.id (not tmdb_id)
        """
        # Check if movie already exists
        movie = db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
        
        if movie:
            return movie.id
        
        # Fetch from TMDB and insert
        try:
            tmdb_details = TMDBService.get_movie_details(tmdb_id)
            
            new_movie = Movie(
                tmdb_id=tmdb_id,
                title=tmdb_details.get("title", "Unknown"),
                overview=tmdb_details.get("overview"),
                release_date=tmdb_details.get("release_date"),
                poster_path=tmdb_details.get("poster_path"),
                backdrop_path=tmdb_details.get("backdrop_path"),
                vote_average=tmdb_details.get("vote_average", 0.0),
                vote_count=tmdb_details.get("vote_count", 0),
                popularity=tmdb_details.get("popularity", 0.0),
                genres=tmdb_details.get("genres", []),
                runtime=tmdb_details.get("runtime")
            )
            db.add(new_movie)
            db.commit()
            db.refresh(new_movie)
            return new_movie.id
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch movie details from TMDB: {str(e)}"
            )

    @staticmethod
    def add_to_watchlist(db: Session, user_id: int, watchlist_data: WatchlistAdd) -> Watchlist:
        """Add a movie to user's watchlist"""
        # Ensure movie exists in DB and get internal movie_id
        internal_movie_id = WatchlistService._ensure_movie_exists(db, watchlist_data.movie_id)
        
        # Check if already in watchlist
        existing = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.movie_id == internal_movie_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already in watchlist"
            )

        # Create new watchlist item
        watchlist_item = Watchlist(
            user_id=user_id,
            movie_id=internal_movie_id
        )
        db.add(watchlist_item)
        db.commit()
        db.refresh(watchlist_item)
        
        # Reload with movie relationship for tmdb_id property
        watchlist_item = db.query(Watchlist).options(joinedload(Watchlist.movie)).filter(
            Watchlist.id == watchlist_item.id
        ).first()
        
        return watchlist_item

    @staticmethod
    def get_watchlist(
        db: Session, 
        user_id: int, 
        watched: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Watchlist]:
        """Get user's watchlist with optional filtering"""
        query = db.query(Watchlist).options(joinedload(Watchlist.movie)).filter(Watchlist.user_id == user_id)
        
        if watched is not None:
            query = query.filter(Watchlist.watched == watched)
        
        return query.order_by(Watchlist.added_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_watchlist_item(db: Session, user_id: int, item_id: int) -> Watchlist:
        """Get a specific watchlist item"""
        item = db.query(Watchlist).options(joinedload(Watchlist.movie)).filter(
            Watchlist.id == item_id,
            Watchlist.user_id == user_id
        ).first()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist item not found"
            )
        return item

    @staticmethod
    def update_watchlist_item(
        db: Session, 
        user_id: int, 
        item_id: int, 
        update_data: WatchlistUpdate
    ) -> Watchlist:
        """Update a watchlist item"""
        item = WatchlistService.get_watchlist_item(db, user_id, item_id)

        # Update watched status
        if update_data.watched is not None:
            item.watched = update_data.watched  # type: ignore
            if update_data.watched:
                item.watched_at = datetime.utcnow()  # type: ignore
            else:
                item.watched_at = None  # type: ignore

        db.commit()
        db.refresh(item)
        
        # Reload with movie relationship for tmdb_id property
        item = db.query(Watchlist).options(joinedload(Watchlist.movie)).filter(
            Watchlist.id == item.id
        ).first()
        
        return item

    @staticmethod
    def remove_from_watchlist(db: Session, user_id: int, item_id: int) -> None:
        """Remove a movie from watchlist"""
        item = WatchlistService.get_watchlist_item(db, user_id, item_id)
        db.delete(item)
        db.commit()

    @staticmethod
    def check_in_watchlist(db: Session, user_id: int, tmdb_id: int) -> dict:
        """
        Check if a movie is in user's watchlist and return item_id if exists
        Note: tmdb_id is the TMDB movie ID, not the internal movie.id
        """
        # First find the internal movie_id from tmdb_id
        movie = db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
        
        if not movie:
            # Movie doesn't exist in DB yet, so definitely not in watchlist
            return {"in_watchlist": False, "item_id": None}
        
        # Check watchlist using internal movie_id
        item = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.movie_id == movie.id
        ).first()
        
        if item:
            return {"in_watchlist": True, "item_id": item.id}
        else:
            return {"in_watchlist": False, "item_id": None}

    @staticmethod
    def get_watchlist_stats(db: Session, user_id: int) -> WatchlistStats:
        """Get watchlist statistics"""
        total = db.query(func.count(Watchlist.id)).filter(
            Watchlist.user_id == user_id
        ).scalar()

        watched = db.query(func.count(Watchlist.id)).filter(
            Watchlist.user_id == user_id,
            Watchlist.watched == True
        ).scalar()

        return WatchlistStats(
            total_items=total or 0,
            watched_items=watched or 0,
            unwatched_items=(total or 0) - (watched or 0)
        )


class CustomListService:
    """Service for custom list operations"""

    @staticmethod
    def create_list(db: Session, user_id: int, list_data: CustomListCreate) -> CustomList:
        """Create a new custom list"""
        custom_list = CustomList(
            user_id=user_id,
            name=list_data.name,
            description=list_data.description,
            is_public=list_data.is_public
        )
        db.add(custom_list)
        db.commit()
        db.refresh(custom_list)
        return custom_list

    @staticmethod
    def get_user_lists(db: Session, user_id: int) -> List[CustomList]:
        """Get all lists created by user"""
        return db.query(CustomList).filter(
            CustomList.user_id == user_id
        ).order_by(CustomList.created_at.desc()).all()

    @staticmethod
    def get_list(db: Session, user_id: int, list_id: int) -> CustomList:
        """Get a specific custom list"""
        custom_list = db.query(CustomList).filter(
            CustomList.id == list_id,
            CustomList.user_id == user_id
        ).first()

        if not custom_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Custom list not found"
            )
        return custom_list

    @staticmethod
    def update_list(
        db: Session, 
        user_id: int, 
        list_id: int, 
        update_data: CustomListUpdate
    ) -> CustomList:
        """Update a custom list"""
        custom_list = CustomListService.get_list(db, user_id, list_id)

        if update_data.name is not None:
            custom_list.name = update_data.name  # type: ignore
        if update_data.description is not None:
            custom_list.description = update_data.description  # type: ignore
        if update_data.is_public is not None:
            custom_list.is_public = update_data.is_public  # type: ignore

        db.commit()
        db.refresh(custom_list)
        return custom_list

    @staticmethod
    def delete_list(db: Session, user_id: int, list_id: int) -> None:
        """Delete a custom list"""
        custom_list = CustomListService.get_list(db, user_id, list_id)
        db.delete(custom_list)
        db.commit()

    @staticmethod
    def add_item_to_list(
        db: Session, 
        user_id: int, 
        list_id: int, 
        item_data: CustomListItemAdd
    ) -> CustomListItem:
        """Add a movie to custom list"""
        # Verify list ownership
        custom_list = CustomListService.get_list(db, user_id, list_id)

        # Check if movie already in list
        existing = db.query(CustomListItem).filter(
            CustomListItem.list_id == list_id,
            CustomListItem.movie_id == item_data.movie_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already in this list"
            )

        # Add item
        list_item = CustomListItem(
            list_id=list_id,
            movie_id=item_data.movie_id,
            notes=item_data.notes
        )
        db.add(list_item)
        db.commit()
        db.refresh(list_item)
        return list_item

    @staticmethod
    def remove_item_from_list(db: Session, user_id: int, list_id: int, item_id: int) -> None:
        """Remove a movie from custom list"""
        # Verify list ownership
        CustomListService.get_list(db, user_id, list_id)

        # Get and delete item
        item = db.query(CustomListItem).filter(
            CustomListItem.id == item_id,
            CustomListItem.list_id == list_id
        ).first()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in list"
            )

        db.delete(item)
        db.commit()

    @staticmethod
    def get_list_items(db: Session, user_id: int, list_id: int) -> List[CustomListItem]:
        """Get all items in a custom list"""
        # Verify list ownership
        CustomListService.get_list(db, user_id, list_id)

        return db.query(CustomListItem).filter(
            CustomListItem.list_id == list_id
        ).order_by(CustomListItem.added_at.desc()).all()
