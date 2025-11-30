"""
Similar Movies Routes - Real-time similarity without caching
For movie detail pages - finds similar movies based on current movie
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict
from app.services.similar_movies_service import SimilarMoviesService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/similar", tags=["Similar Movies"])


@router.get("/movies/{movie_id}", response_model=List[Dict])
async def get_similar_movies(
    movie_id: int,
    limit: int = Query(20, ge=1, le=50, description="Number of similar movies to return")
):
    """
    Get similar movies for a specific movie
    
    Uses TMDB's similar endpoint - no caching required
    Falls back to genre matching if TMDB similar fails
    
    **Use case:** Movie detail pages showing "You might also like"
    
    Args:
        movie_id: TMDB movie ID
        limit: Maximum number of results (1-50)
        
    Returns:
        List of similar movies with:
        - tmdb_id, title, overview
        - poster_path, backdrop_path
        - vote_average, release_date
        - genre_ids
        
    Example:
        GET /api/similar/movies/550?limit=10
        Returns 10 movies similar to Fight Club
    """
    try:
        results = SimilarMoviesService.get_similar_movies(movie_id, limit)
        
        if not results:
            logger.warning(f"No similar movies found for movie {movie_id}")
            return []
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting similar movies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch similar movies: {str(e)}"
        )


@router.get("/by-genre", response_model=List[Dict])
async def get_by_genre(
    genre_ids: str = Query(..., pattern="^[0-9,]+$", description="Comma-separated genre IDs"),
    limit: int = Query(20, ge=1, le=50),
    min_rating: float = Query(8.0, ge=0, le=10, description="Minimum vote average")
):
    """
    Get movies by genre - real-time from TMDB
    
    **Use case:** Browse movies by genre preferences
    
    Args:
        genre_ids: Comma-separated genre IDs (e.g., "28,12,16")
        limit: Maximum results
        min_rating: Filter by minimum rating
        
    Returns:
        List of movies matching genres
        
    Example:
        GET /api/similar/by-genre?genre_ids=28,12&min_rating=7.0
        Returns Action+Adventure movies with rating >= 7.0
    """
    try:
        # Parse genre IDs
        genre_id_list = [int(gid.strip()) for gid in genre_ids.split(',')]
        
        if not genre_id_list:
            raise HTTPException(status_code=400, detail="At least one genre ID required")
        
        results = SimilarMoviesService.get_by_genre(genre_id_list, limit, min_rating)
        return results
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid genre ID format")
    except Exception as e:
        logger.error(f"Error getting movies by genre: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
