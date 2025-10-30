from fastapi import APIRouter, Query
from app.services.tmdb_service import TMDBService

router = APIRouter(prefix="/api/movies", tags=["Movies"])

# Movie Routes
@router.get("/search")
def search_movies(query: str = Query(..., min_length=1), page: int = Query(1, ge=1)):
    """Search movies by title"""
    return TMDBService.search_movies(query, page)

# Trending, Popular, Now Playing, Top Rated, Movie Details
@router.get("/trending/{time_window}")
def get_trending(time_window: str, page: int = Query(1, ge=1)):
    """Get trending movies (day/week)"""
    return TMDBService.get_trending(time_window, page)

# Popular Movies
@router.get("/popular")
def get_popular(page: int = Query(1, ge=1)):
    """Get popular movies"""
    return TMDBService.get_popular(page)

# Now Playing Movies
@router.get("/now-playing")
def get_now_playing(page: int = Query(1, ge=1)):
    """Get now playing movies"""
    return TMDBService.get_now_playing(page)

# Top Rated Movies
@router.get("/top-rated")
def get_top_rated(page: int = Query(1, ge=1)):
    """Get top rated movies"""
    return TMDBService.get_top_rated(page)

# Movie Details
@router.get("/{movie_id}")
def get_movie_details(movie_id: int):
    """Get movie details"""
    return TMDBService.get_movie_details(movie_id)