"""
Advanced search and filter schemas
Extensible design for future features
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationInfo
from typing import Optional, List
from enum import Enum


# ============================================
# Enums for type-safe filter options
# ============================================

class SortOption(str, Enum):
    """Available sort options for movie discovery"""
    POPULARITY_DESC = "popularity.desc"
    POPULARITY_ASC = "popularity.asc"
    VOTE_AVERAGE_DESC = "vote_average.desc"
    VOTE_AVERAGE_ASC = "vote_average.asc"
    RELEASE_DATE_DESC = "release_date.desc"
    RELEASE_DATE_ASC = "release_date.asc"
    REVENUE_DESC = "revenue.desc"
    REVENUE_ASC = "revenue.asc"


class TimeWindow(str, Enum):
    """Time window for trending movies"""
    DAY = "day"
    WEEK = "week"


# ============================================
# Base Filter Schema (Extensible)
# ============================================

class BaseFilterSchema(BaseModel):
    """
    Base schema for all filter operations
    Provides common pagination and sorting
    """
    page: int = Field(default=1, ge=1, le=500, description="Page number")
    
    model_config = ConfigDict(use_enum_values=True)


# ============================================
# Advanced Search Schema
# ============================================

class AdvancedSearchSchema(BaseFilterSchema):
    """
    Advanced movie search/discovery schema
    Extensible design: Add new filters without breaking existing functionality
    """
    # Genre filtering (comma-separated IDs or list)
    genre: Optional[str] = Field(
        None, 
        description="Genre IDs (comma-separated, e.g., '28,12' for Action+Adventure)",
        json_schema_extra={"example": "28,12"}
    )
    
    # Year filtering
    year: Optional[int] = Field(
        None, 
        ge=1900, 
        le=2030,
        description="Release year filter"
    )
    
    # Rating filtering
    min_rating: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Minimum vote average (0-10)"
    )
    
    max_rating: Optional[float] = Field(
        None,
        ge=0,
        le=10,
        description="Maximum vote average (0-10)"
    )
    
    # Sorting
    sort_by: SortOption = Field(
        default=SortOption.POPULARITY_DESC,
        description="Sort order for results"
    )
    
    # Runtime filtering (for future Context-Aware feature)
    min_runtime: Optional[int] = Field(
        None,
        ge=0,
        le=500,
        description="Minimum runtime in minutes (future: context-aware)"
    )
    
    max_runtime: Optional[int] = Field(
        None,
        ge=0,
        le=500,
        description="Maximum runtime in minutes (future: context-aware)"
    )
    
    # Language filtering (for future internationalization)
    language: Optional[str] = Field(
        None,
        max_length=5,
        description="ISO 639-1 language code (e.g., 'en', 'vi')"
    )
    
    # Region filtering (for future regional content)
    region: Optional[str] = Field(
        None,
        max_length=2,
        description="ISO 3166-1 region code (e.g., 'US', 'VN')"
    )

    # Optional text query to combine with filters (server-side filtering)
    query: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Optional text query to combine with filters"
    )
    
    # Adult content filter
    include_adult: bool = Field(
        default=False,
        description="Include adult content in results"
    )
    
    # Future: Watchlist filter (requires auth)
    # exclude_watchlist: Optional[bool] = None
    
    # Future: Rated filter (requires auth)
    # exclude_rated: Optional[bool] = None
    
    @field_validator('max_rating')
    @classmethod
    def validate_rating_range(cls, v, info: ValidationInfo):
        """Ensure max_rating >= min_rating"""
        min_rating = info.data.get('min_rating')
        if v is not None and min_rating is not None:
            if v < min_rating:
                raise ValueError('max_rating must be >= min_rating')
        return v
    
    @field_validator('max_runtime')
    @classmethod
    def validate_runtime_range(cls, v, info: ValidationInfo):
        """Ensure max_runtime >= min_runtime"""
        min_runtime = info.data.get('min_runtime')
        if v is not None and min_runtime is not None:
            if v < min_runtime:
                raise ValueError('max_runtime must be >= min_runtime')
        return v
    
    def to_tmdb_params(self) -> dict:
        """
        Convert schema to TMDB API parameters
        Extensible: Easy to add new mappings
        """
        params = {
            'page': self.page,
            'sort_by': self.sort_by,
            'include_adult': self.include_adult,
        }
        
        # Add optional filters only if provided
        if self.genre:
            params['with_genres'] = self.genre
        
        if self.year:
            params['primary_release_year'] = self.year
        
        if self.min_rating:
            params['vote_average.gte'] = self.min_rating
        
        if self.max_rating:
            params['vote_average.lte'] = self.max_rating
        
        if self.min_runtime:
            params['with_runtime.gte'] = self.min_runtime
        
        if self.max_runtime:
            params['with_runtime.lte'] = self.max_runtime
        
        if self.language:
            params['with_original_language'] = self.language
        
        if self.region:
            params['region'] = self.region

        if self.query:
            params['query'] = self.query
        
        return params


# ============================================
# Simple Search Schema
# ============================================

class SimpleSearchSchema(BaseFilterSchema):
    """
    Simple text search for movies
    Used for basic search bar functionality
    """
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Search query text"
    )
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Remove dangerous characters for XSS protection"""
        from app.schemas.validation import SafeStringMixin
        return SafeStringMixin.validate_no_script(v)


# ============================================
# Genre Filter Schema
# ============================================

class GenreFilterSchema(BaseFilterSchema):
    """
    Filter movies by specific genres
    Used for genre browsing pages
    """
    genre_ids: str = Field(
        ...,
        description="Comma-separated genre IDs",
        json_schema_extra={"example": "28,12,16"}
    )
    
    sort_by: SortOption = Field(
        default=SortOption.POPULARITY_DESC,
        description="Sort order"
    )
    
    @field_validator('genre_ids')
    @classmethod
    def validate_genre_ids(cls, v):
        """Validate genre IDs are comma-separated integers"""
        try:
            ids = [int(x.strip()) for x in v.split(',')]
            if not ids:
                raise ValueError("At least one genre ID required")
            return ','.join(map(str, ids))
        except ValueError:
            raise ValueError("Invalid genre IDs format. Use comma-separated integers")


# ============================================
# Trending Filter Schema
# ============================================

class TrendingFilterSchema(BaseFilterSchema):
    """
    Filter for trending movies
    """
    time_window: TimeWindow = Field(
        default=TimeWindow.WEEK,
        description="Time window for trending calculation"
    )


# ============================================
# Response Schemas
# ============================================

class MovieListResponse(BaseModel):
    """Standard response for movie list endpoints"""
    page: int
    total_pages: int
    total_results: int
    results: List[dict]


class GenreResponse(BaseModel):
    """Response schema for genre list"""
    id: int
    name: str


class GenreListResponse(BaseModel):
    """Response for genres endpoint"""
    genres: List[GenreResponse]
