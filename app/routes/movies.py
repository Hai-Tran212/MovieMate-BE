from fastapi import APIRouter, Query, Depends
from app.services.tmdb_service import TMDBService
from app.schemas.search import (
    AdvancedSearchSchema,
    SimpleSearchSchema,
    GenreFilterSchema,
    TrendingFilterSchema,
    MovieListResponse,
    GenreListResponse,
    SortOption
)
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/movies", tags=["Movies"])


# ============================================
# Advanced Search & Discovery
# ============================================

@router.get("/discover", response_model=MovieListResponse)
def discover_movies(
    genre: Optional[str] = Query(None, description="Genre IDs (comma-separated)"),
    year: Optional[int] = Query(None, ge=1900, le=2030, description="Release year"),
    min_rating: Optional[float] = Query(None, ge=0, le=10, description="Minimum rating"),
    max_rating: Optional[float] = Query(None, ge=0, le=10, description="Maximum rating"),
    min_runtime: Optional[int] = Query(None, ge=0, le=500, description="Minimum runtime (minutes)"),
    max_runtime: Optional[int] = Query(None, ge=0, le=500, description="Maximum runtime (minutes)"),
    sort_by: SortOption = Query(SortOption.POPULARITY_DESC, description="Sort option"),
    language: Optional[str] = Query(None, max_length=5, description="Language code (e.g., 'en')"),
    region: Optional[str] = Query(None, max_length=2, description="Region code (e.g., 'US')"),
    page: int = Query(1, ge=1, le=500, description="Page number"),
    query: Optional[str] = Query(None, min_length=1, max_length=200, description="Optional text query")
):
    """
    Advanced movie discovery with multiple filters
    
    **Extensible Design**: Easy to add new filters
    
    **Current Filters**:
    - genre: Filter by genre IDs (e.g., "28,12" for Action+Adventure)
    - year: Filter by release year
    - min_rating/max_rating: Filter by rating range (0-10)
    - min_runtime/max_runtime: Filter by runtime range (minutes)
    - sort_by: Sort results (popularity.desc, vote_average.desc, etc.)
    - language: Filter by original language
    - region: Filter by region
    
    **Future Filters** (ready to add):
    - exclude_watchlist: Exclude movies in user's watchlist (requires auth)
    - exclude_rated: Exclude movies user has rated (requires auth)
    - mood: Filter by mood tags (requires mood-based recommendation feature)
    - decade: Filter by decade (e.g., "1980s")
    """
    # Create schema instance for validation
    search_params = AdvancedSearchSchema(
        genre=genre,
        year=year,
        min_rating=min_rating,
        max_rating=max_rating,
        min_runtime=min_runtime,
        max_runtime=max_runtime,
        sort_by=sort_by,
        language=language,
        region=region,
        page=page,
        query=query
    )
    
    tmdb_params = search_params.to_tmdb_params()

    if search_params.query:
        # Discover endpoint does not support free-text search; fall back to search API
        result = TMDBService.search_movies(search_params.query, page)
        filtered_results = _filter_search_results(result.get('results', []), search_params)
        result['results'] = filtered_results
        return result

    return TMDBService.discover_movies(tmdb_params)


@router.get("/genres", response_model=GenreListResponse)
def get_genres():
    """
    Get list of all available movie genres
    
    Used for:
    - Filter dropdowns
    - Genre browsing pages
    - Genre-based recommendations
    """
    return TMDBService.get_genres()

# ============================================
# Simple Search
# ============================================

@router.get("/search", response_model=MovieListResponse)
def search_movies(
    query: str = Query(..., min_length=1, max_length=200, description="Search query"),
    page: int = Query(1, ge=1, description="Page number")
):
    """
    Simple text search for movies
    
    Used for: Basic search bar functionality
    """
    
    # TẠM THỜI BYPASS SCHEMA ĐỂ KIỂM TRA
    # search_params = SimpleSearchSchema(query=query, page=page)
    # return TMDBService.search_movies(search_params.query, search_params.page)

    # DÙNG LẠI CODE GỐC:
    return TMDBService.search_movies(query, page)
# # ============================================
# # Simple Search
# # ============================================

# @router.get("/search", response_model=MovieListResponse)
# def search_movies(
#     query: str = Query(..., min_length=1, max_length=200, description="Search query"),
#     page: int = Query(1, ge=1, description="Page number")
# ):
#     """
#     Simple text search for movies
    
#     Used for: Basic search bar functionality
#     """
#     # Validate with schema (XSS protection)
#     search_params = SimpleSearchSchema(query=query, page=page)
#     return TMDBService.search_movies(search_params.query, search_params.page)



# ============================================
# Trending, Popular, Now Playing, Top Rated
# ============================================

@router.get("/trending/{time_window}")
def get_trending(time_window: str, page: int = Query(1, ge=1)):
    """Get trending movies (day/week)"""
    return TMDBService.get_trending(time_window, page)

@router.get("/popular")
def get_popular(page: int = Query(1, ge=1)):
    """Get popular movies"""
    return TMDBService.get_popular(page)

@router.get("/now-playing")
def get_now_playing(page: int = Query(1, ge=1)):
    """Get now playing movies"""
    return TMDBService.get_now_playing(page)

@router.get("/top-rated")
def get_top_rated(page: int = Query(1, ge=1)):
    """Get top rated movies"""
    return TMDBService.get_top_rated(page)


# ============================================
# Movie Details (MUST be last - dynamic route)
# ============================================

@router.get("/{movie_id}")
def get_movie_details(movie_id: int):
    """Get movie details by ID - MUST be defined last to avoid path conflicts"""
    return TMDBService.get_movie_details(movie_id)


def _filter_search_results(results: List[Dict[str, Any]], params: AdvancedSearchSchema) -> List[Dict[str, Any]]:
    """Filter TMDB search results locally using advanced filters."""
    required_genres = set(
        int(g.strip()) for g in (params.genre or "").split(",") if g.strip().isdigit()
    )

    def matches(movie: Dict[str, Any]) -> bool:
        movie_genres = set(movie.get("genre_ids") or [])
        if required_genres and not required_genres.issubset(movie_genres):
            return False

        release_date = movie.get("release_date") or ""
        release_year = int(release_date.split("-")[0]) if release_date and release_date[:4].isdigit() else None
        if params.year and release_year != params.year:
            return False

        vote_average = movie.get("vote_average") or 0.0
        if params.min_rating is not None and vote_average < params.min_rating:
            return False
        if params.max_rating is not None and vote_average > params.max_rating:
            return False

        language = movie.get("original_language")
        if params.language and language != params.language:
            return False

        return True

    return [movie for movie in results if matches(movie)]