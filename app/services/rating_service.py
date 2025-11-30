"""
Rating Service - Handle all rating-related business logic
Follows the same pattern as WatchlistService for consistency
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import List, Optional, Dict
from datetime import datetime

from app.models.rating import Rating
from app.models.movie import Movie
from app.models.movie_cache import MovieCache
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingUpdate
from app.services.tmdb_service import TMDBService


class RatingService:
    """Service for movie rating operations"""

    @staticmethod
    def _ensure_movie_in_cache(db: Session, tmdb_id: int, tmdb_details: dict = None) -> None:
        """
        Ensure movie exists in MovieCache for hybrid recommendations.
        This is a fire-and-forget operation - failures are logged but don't block rating.
        
        Args:
            db: Database session
            tmdb_id: TMDB movie ID
            tmdb_details: Optional pre-fetched TMDB details (to avoid duplicate API call)
        """
        try:
            # Check if already in cache
            existing = db.query(MovieCache).filter(MovieCache.tmdb_id == tmdb_id).first()
            if existing:
                return  # Already cached, nothing to do
            
            # Fetch details if not provided
            if not tmdb_details:
                tmdb_details = TMDBService.get_movie_details(tmdb_id)
            
            if not tmdb_details:
                return  # Can't fetch, skip silently
            
            # Extract feature vectors for recommendations
            genres = [g['id'] for g in tmdb_details.get('genres', [])]
            
            keywords_data = tmdb_details.get('keywords', {}).get('keywords', [])
            keyword_ids = [k['id'] for k in keywords_data]
            keyword_names = [k['name'].lower() for k in keywords_data]
            
            cast_data = tmdb_details.get('credits', {}).get('cast', [])
            cast_ids = [c['id'] for c in cast_data[:10]]
            
            crew_data = tmdb_details.get('credits', {}).get('crew', [])
            important_jobs = ['Director', 'Producer', 'Screenplay', 'Writer']
            crew_ids = [c['id'] for c in crew_data if c.get('job') in important_jobs]
            
            # Create cache entry
            cache_entry = MovieCache(
                tmdb_id=tmdb_id,
                title=tmdb_details.get('title', ''),
                overview=tmdb_details.get('overview', ''),
                release_date=tmdb_details.get('release_date', ''),
                poster_path=tmdb_details.get('poster_path', ''),
                backdrop_path=tmdb_details.get('backdrop_path', ''),
                vote_average=tmdb_details.get('vote_average', 0.0),
                popularity=tmdb_details.get('popularity', 0.0),
                genres=genres,
                keywords=keyword_ids,
                keyword_names=keyword_names,
                cast=cast_ids,
                crew=crew_ids
            )
            
            db.add(cache_entry)
            db.commit()
            
        except Exception:
            # Silent fail - caching is optional, don't break the rating flow
            db.rollback()

    @staticmethod
    def _ensure_movie_exists(db: Session, tmdb_id: int) -> int:
        """
        Ensure movie exists in DB, fetch from TMDB if not
        Returns the internal movie.id (not tmdb_id)
        Pattern from WatchlistService for consistency
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
    def add_or_update_rating(
        db: Session, 
        user_id: int, 
        rating_data: RatingCreate
    ) -> Rating:
        """
        Add a new rating or update existing one
        This follows the pattern of "add or update" for better UX
        
        Args:
            db: Database session
            user_id: User ID
            rating_data: RatingCreate schema with movie_id and rating value
            
        Returns:
            Rating object
            
        Raises:
            HTTPException: If rating value is invalid
        """
        # Validate rating range (1-10)
        if rating_data.rating < 1 or rating_data.rating > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 10"
            )
        
        # Ensure movie exists in DB and get internal movie_id
        internal_movie_id = RatingService._ensure_movie_exists(db, rating_data.movie_id)
        
        # Also ensure movie is in MovieCache for hybrid recommendations (non-blocking)
        RatingService._ensure_movie_in_cache(db, rating_data.movie_id)
        
        # Check if rating already exists
        existing_rating = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.movie_id == internal_movie_id
        ).first()

        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating_data.rating
            existing_rating.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing_rating)
            
            # Reload with movie relationship for tmdb_id property
            existing_rating = db.query(Rating).options(
                joinedload(Rating.movie)
            ).filter(
                Rating.id == existing_rating.id
            ).first()
            
            return existing_rating
        else:
            # Create new rating
            new_rating = Rating(
                user_id=user_id,
                movie_id=internal_movie_id,
                rating=rating_data.rating
            )
            db.add(new_rating)
            db.commit()
            db.refresh(new_rating)
            
            # Reload with movie relationship
            new_rating = db.query(Rating).options(
                joinedload(Rating.movie)
            ).filter(
                Rating.id == new_rating.id
            ).first()
            
            return new_rating

    @staticmethod
    def get_user_ratings(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Rating]:
        """
        Get all ratings by a specific user
        
        Args:
            db: Database session
            user_id: User ID
            skip: Pagination offset
            limit: Max results per page
            
        Returns:
            List of Rating objects with movie relationship loaded
        """
        ratings = db.query(Rating).options(
            joinedload(Rating.movie)
        ).filter(
            Rating.user_id == user_id
        ).order_by(
            Rating.updated_at.desc()
        ).offset(skip).limit(limit).all()
        
        return ratings

    @staticmethod
    def get_user_rating_for_movie(
        db: Session,
        user_id: int,
        tmdb_movie_id: int
    ) -> Optional[Rating]:
        """
        Get user's rating for a specific movie (by TMDB ID)
        
        Args:
            db: Database session
            user_id: User ID
            tmdb_movie_id: TMDB movie ID
            
        Returns:
            Rating object or None if not found
        """
        # Find internal movie_id from tmdb_id
        movie = db.query(Movie).filter(Movie.tmdb_id == tmdb_movie_id).first()
        
        if not movie:
            return None
        
        rating = db.query(Rating).options(
            joinedload(Rating.movie)
        ).filter(
            Rating.user_id == user_id,
            Rating.movie_id == movie.id
        ).first()
        
        return rating

    @staticmethod
    def delete_rating(db: Session, user_id: int, rating_id: int) -> bool:
        """
        Delete a rating by ID
        
        Args:
            db: Database session
            user_id: User ID (for authorization)
            rating_id: Rating ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            HTTPException: If rating not found or unauthorized
        """
        rating = db.query(Rating).filter(
            Rating.id == rating_id,
            Rating.user_id == user_id
        ).first()

        if not rating:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rating not found or you don't have permission to delete it"
            )

        db.delete(rating)
        db.commit()
        return True

    @staticmethod
    def get_user_stats(db: Session, user_id: int) -> Dict:
        """
        Get user's rating statistics
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Dictionary with stats: total_ratings, average_rating, rating_distribution
        """
        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()

        if not ratings:
            return {
                "total_ratings": 0,
                "average_rating": 0.0,
                "rating_distribution": {str(i): 0 for i in range(1, 11)}
            }

        total = len(ratings)
        avg = sum(r.rating for r in ratings) / total

        # Calculate distribution (how many 1s, 2s, ... 10s)
        distribution = {str(i): 0 for i in range(1, 11)}
        for rating in ratings:
            rating_int = int(rating.rating)
            if 1 <= rating_int <= 10:
                distribution[str(rating_int)] += 1

        return {
            "total_ratings": total,
            "average_rating": round(avg, 2),
            "rating_distribution": distribution
        }

    @staticmethod
    def get_movie_ratings_stats(db: Session, tmdb_movie_id: int) -> Dict:
        """
        Get rating statistics for a specific movie
        
        Args:
            db: Database session
            tmdb_movie_id: TMDB movie ID
            
        Returns:
            Dictionary with stats: total_ratings, average_rating
        """
        # Find internal movie_id from tmdb_id
        movie = db.query(Movie).filter(Movie.tmdb_id == tmdb_movie_id).first()
        
        if not movie:
            return {
                "total_ratings": 0,
                "average_rating": 0.0
            }
        
        ratings = db.query(Rating).filter(Rating.movie_id == movie.id).all()
        
        if not ratings:
            return {
                "total_ratings": 0,
                "average_rating": 0.0
            }
        
        total = len(ratings)
        avg = sum(r.rating for r in ratings) / total
        
        return {
            "total_ratings": total,
            "average_rating": round(avg, 2)
        }
