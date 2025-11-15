from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# ==================== WATCHLIST SCHEMAS ====================

class WatchlistAdd(BaseModel):
    """Schema for adding a movie to watchlist"""
    movie_id: int = Field(..., description="TMDB movie ID (will be converted to internal movie.id)")


class WatchlistUpdate(BaseModel):
    """Schema for updating watchlist item"""
    watched: Optional[bool] = Field(None, description="Mark as watched/unwatched")


class WatchlistResponse(BaseModel):
    """Schema for watchlist item response"""
    id: int
    user_id: int
    movie_id: int  # Internal DB id
    tmdb_id: int  # TMDB movie ID for frontend
    watched: bool
    added_at: datetime
    watched_at: Optional[datetime]

    class Config:
        from_attributes = True  # Pydantic v2 (was orm_mode in v1)


class WatchlistStats(BaseModel):
    """Schema for watchlist statistics"""
    total_items: int
    watched_items: int = 0
    unwatched_items: int = 0


# ==================== CUSTOM LIST SCHEMAS ====================

class CustomListCreate(BaseModel):
    """Schema for creating a custom list"""
    name: str = Field(..., min_length=1, max_length=100, description="List name")
    description: Optional[str] = Field(None, max_length=500, description="List description")
    is_public: bool = Field(False, description="Is list public?")


class CustomListUpdate(BaseModel):
    """Schema for updating a custom list"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="List name")
    description: Optional[str] = Field(None, max_length=500, description="List description")
    is_public: Optional[bool] = Field(None, description="Is list public?")


class CustomListItemAdd(BaseModel):
    """Schema for adding item to custom list"""
    movie_id: int = Field(..., description="Movie ID")
    notes: Optional[str] = Field(None, max_length=500, description="Personal notes")


class CustomListItemResponse(BaseModel):
    """Schema for custom list item response"""
    id: int
    list_id: int
    movie_id: int
    added_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class CustomListResponse(BaseModel):
    """Schema for custom list response"""
    id: int
    user_id: int
    name: str
    description: Optional[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    items_count: Optional[int] = None  # Will be populated via query

    class Config:
        from_attributes = True


class CustomListDetailResponse(CustomListResponse):
    """Schema for custom list with items"""
    list_items: List[CustomListItemResponse] = []
