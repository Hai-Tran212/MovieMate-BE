"""
Rating Schemas - Pydantic models for rating request/response validation
Follows the same pattern as watchlist schemas for consistency
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class RatingCreate(BaseModel):
    """Schema for creating/updating a rating"""
    movie_id: int = Field(..., description="TMDB movie ID", gt=0)
    rating: float = Field(..., description="Rating value (1-10)", ge=1.0, le=10.0)
    
    @validator('rating')
    def validate_rating(cls, v):
        """Ensure rating is within valid range"""
        if v < 1.0 or v > 10.0:
            raise ValueError('Rating must be between 1 and 10')
        return round(v, 1)  # Round to 1 decimal place


class RatingUpdate(BaseModel):
    """Schema for updating an existing rating"""
    rating: float = Field(..., description="New rating value (1-10)", ge=1.0, le=10.0)
    
    @validator('rating')
    def validate_rating(cls, v):
        """Ensure rating is within valid range"""
        if v < 1.0 or v > 10.0:
            raise ValueError('Rating must be between 1 and 10')
        return round(v, 1)


class RatingResponse(BaseModel):
    """Schema for rating response (matches database model)"""
    id: int
    user_id: int
    movie_id: int  # Internal DB movie ID
    rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Custom property to get TMDB ID from relationship
    @property
    def tmdb_id(self) -> Optional[int]:
        """Get TMDB ID from movie relationship if available"""
        if hasattr(self, 'movie') and self.movie:
            return self.movie.tmdb_id
        return None
    
    class Config:
        orm_mode = True
        from_attributes = True


class RatingWithMovieResponse(BaseModel):
    """
    Schema for rating response with movie details included
    Useful for displaying ratings with movie information
    """
    id: int
    user_id: int
    rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Movie details (from relationship)
    tmdb_id: int = Field(..., description="TMDB movie ID")
    movie_title: str = Field(..., description="Movie title")
    movie_poster_path: Optional[str] = Field(None, description="Poster path")
    movie_release_date: Optional[str] = Field(None, description="Release date")
    movie_vote_average: Optional[float] = Field(None, description="TMDB average rating")
    
    class Config:
        orm_mode = True
        from_attributes = True


class RatingStats(BaseModel):
    """Schema for user rating statistics"""
    total_ratings: int = Field(..., description="Total number of ratings")
    average_rating: float = Field(..., description="Average rating given by user")
    rating_distribution: dict = Field(
        ..., 
        description="Distribution of ratings (1-10)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "total_ratings": 42,
                "average_rating": 7.5,
                "rating_distribution": {
                    "1": 0, "2": 1, "3": 2, "4": 3, 
                    "5": 5, "6": 8, "7": 10, "8": 7, 
                    "9": 4, "10": 2
                }
            }
        }


class MovieRatingStats(BaseModel):
    """Schema for movie-specific rating statistics"""
    total_ratings: int = Field(..., description="Total ratings for this movie")
    average_rating: float = Field(..., description="Average user rating")
    
    class Config:
        schema_extra = {
            "example": {
                "total_ratings": 156,
                "average_rating": 8.2
            }
        }


class UserRatingForMovie(BaseModel):
    """
    Schema for checking if user has rated a specific movie
    Returns rating value or None
    """
    rating: Optional[float] = Field(None, description="User's rating (1-10) or None if not rated")
    rating_id: Optional[int] = Field(None, description="Rating ID if exists")
    
    class Config:
        schema_extra = {
            "example": {
                "rating": 8.5,
                "rating_id": 123
            }
        }
