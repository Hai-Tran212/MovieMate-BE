"""
Rating Routes - API endpoints for movie rating system
Follows RESTful conventions and watchlist routes pattern
"""

from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.schemas.rating import (
    RatingCreate,
    RatingUpdate,
    RatingResponse,
    RatingWithMovieResponse,
    RatingStats,
    MovieRatingStats,
    UserRatingForMovie
)
from app.services.rating_service import RatingService

router = APIRouter(prefix="/api/ratings", tags=["Ratings"])


def get_user_id(user: User) -> int:
    """Helper to extract user_id as int for type safety"""
    return int(user.id)  # type: ignore


# ==================== RATING CRUD ENDPOINTS ====================

@router.post("/", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
def add_or_update_rating(
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new rating or update existing one for a movie
    
    - **movie_id**: TMDB movie ID (required)
    - **rating**: Rating value from 1 to 10 (required)
    
    If user has already rated this movie, the rating will be updated.
    Otherwise, a new rating will be created.
    """
    return RatingService.add_or_update_rating(db, get_user_id(current_user), rating_data)


@router.get("/user/me", response_model=List[RatingResponse])
def get_my_ratings(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=200, description="Max results per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all ratings by current user
    
    Returns list of ratings ordered by most recently updated first.
    Supports pagination with skip and limit parameters.
    """
    return RatingService.get_user_ratings(db, get_user_id(current_user), skip, limit)


@router.get("/movie/{tmdb_movie_id}", response_model=UserRatingForMovie)
def get_my_rating_for_movie(
    tmdb_movie_id: int = Path(..., description="TMDB movie ID", gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's rating for a specific movie (by TMDB ID)
    
    Returns rating value and ID if user has rated the movie.
    Returns null values if user hasn't rated it yet.
    
    Useful for:
    - Displaying user's existing rating in UI
    - Checking if user has already rated a movie
    - Pre-filling rating widget with current value
    """
    rating = RatingService.get_user_rating_for_movie(
        db, 
        get_user_id(current_user), 
        tmdb_movie_id
    )
    
    if rating:
        return {
            "rating": rating.rating,
            "rating_id": rating.id
        }
    
    return {
        "rating": None,
        "rating_id": None
    }


@router.delete("/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rating(
    rating_id: int = Path(..., description="Rating ID to delete", gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a rating by ID
    
    Only the user who created the rating can delete it.
    Returns 204 No Content on success.
    """
    RatingService.delete_rating(db, get_user_id(current_user), rating_id)
    return None


# ==================== STATISTICS ENDPOINTS ====================

@router.get("/stats", response_model=RatingStats)
def get_my_rating_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's rating statistics
    
    Returns:
    - Total number of ratings
    - Average rating given
    - Distribution of ratings (how many 1s, 2s, ..., 10s)
    
    Useful for user profile or dashboard displays.
    """
    return RatingService.get_user_stats(db, get_user_id(current_user))


@router.get("/movie/{tmdb_movie_id}/stats", response_model=MovieRatingStats)
def get_movie_rating_stats(
    tmdb_movie_id: int = Path(..., description="TMDB movie ID", gt=0),
    db: Session = Depends(get_db)
):
    """
    Get rating statistics for a specific movie
    
    Returns:
    - Total number of user ratings for this movie
    - Average user rating
    
    Public endpoint - no authentication required.
    Useful for displaying community ratings alongside TMDB ratings.
    """
    return RatingService.get_movie_ratings_stats(db, tmdb_movie_id)


# ==================== BULK/UTILITY ENDPOINTS ====================

@router.delete("/user/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_my_ratings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete ALL ratings by current user
    
    ⚠️ WARNING: This action cannot be undone!
    Use with caution.
    
    Useful for:
    - User wanting to reset their ratings
    - Account cleanup operations
    """
    from app.models.rating import Rating
    
    db.query(Rating).filter(
        Rating.user_id == get_user_id(current_user)
    ).delete(synchronize_session=False)
    
    db.commit()
    return None
