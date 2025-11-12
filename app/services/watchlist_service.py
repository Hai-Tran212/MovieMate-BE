from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime

from app.models.watchlist import Watchlist, CustomList, CustomListItem
from app.schemas.watchlist import (
    WatchlistAdd,
    WatchlistUpdate,
    WatchlistStats,
    CustomListCreate,
    CustomListUpdate,
    CustomListItemAdd
)


class WatchlistService:
    """Service for watchlist operations"""

    @staticmethod
    def add_to_watchlist(db: Session, user_id: int, watchlist_data: WatchlistAdd) -> Watchlist:
        """Add a movie to user's watchlist"""
        # Check if already in watchlist
        existing = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.movie_id == watchlist_data.movie_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already in watchlist"
            )

        # Create new watchlist item
        watchlist_item = Watchlist(
            user_id=user_id,
            movie_id=watchlist_data.movie_id,
            notes=watchlist_data.notes
        )
        db.add(watchlist_item)
        db.commit()
        db.refresh(watchlist_item)
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
        query = db.query(Watchlist).filter(Watchlist.user_id == user_id)
        
        if watched is not None:
            query = query.filter(Watchlist.watched == watched)
        
        return query.order_by(Watchlist.added_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_watchlist_item(db: Session, user_id: int, item_id: int) -> Watchlist:
        """Get a specific watchlist item"""
        item = db.query(Watchlist).filter(
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

        # Update fields
        if update_data.watched is not None:
            item.watched = update_data.watched  # type: ignore
            if update_data.watched:
                item.watched_at = datetime.utcnow()  # type: ignore
            else:
                item.watched_at = None  # type: ignore

        if update_data.rating is not None:
            item.rating = update_data.rating  # type: ignore

        if update_data.notes is not None:
            item.notes = update_data.notes  # type: ignore

        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def remove_from_watchlist(db: Session, user_id: int, item_id: int) -> None:
        """Remove a movie from watchlist"""
        item = WatchlistService.get_watchlist_item(db, user_id, item_id)
        db.delete(item)
        db.commit()

    @staticmethod
    def check_in_watchlist(db: Session, user_id: int, movie_id: int) -> bool:
        """Check if a movie is in user's watchlist"""
        exists = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.movie_id == movie_id
        ).first()
        return exists is not None

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

        avg_rating = db.query(func.avg(Watchlist.rating)).filter(
            Watchlist.user_id == user_id,
            Watchlist.rating.isnot(None)
        ).scalar()

        return WatchlistStats(
            total_items=total or 0,
            watched_items=watched or 0,
            unwatched_items=(total or 0) - (watched or 0),
            average_rating=float(avg_rating) if avg_rating else None
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
