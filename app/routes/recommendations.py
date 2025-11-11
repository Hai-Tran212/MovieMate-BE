"""
Recommendation Routes
Endpoints for content-based movie recommendations
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.recommendation_service import RecommendationService
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.get("/similar/{movie_id}", response_model=List[Dict])
async def get_similar_movies(
    movie_id: int,
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations (1-50)"),
    use_knn: bool = Query(True, description="Use KNN algorithm (True) or simple genre matching (False)"),
    db: Session = Depends(get_db)
):
    """
    Get movies similar to a specific movie using content-based filtering
    
    **Algorithm:**
    - KNN (K-Nearest Neighbors) with cosine similarity
    - Analyzes: genres, keywords, cast, crew
    - Fallback to genre-based if insufficient data
    
    **Parameters:**
    - `movie_id`: TMDB movie ID
    - `limit`: Number of recommendations (default: 20, max: 50)
    - `use_knn`: Use advanced KNN algorithm or simple genre matching
    
    **Returns:**
    List of similar movies with similarity scores (0.0 to 1.0)
    
    **Example:**
    ```
    GET /api/recommendations/similar/550?limit=10&use_knn=true
    ```
    """
    try:
        recommendations = RecommendationService.get_similar_movies(
            db=db,
            movie_id=movie_id,
            limit=limit,
            use_knn=use_knn
        )
        
        if not recommendations:
            logger.warning(f"No recommendations found for movie {movie_id}")
            return []
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error getting recommendations for movie {movie_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


@router.get("/by-genre", response_model=List[Dict])
async def get_recommendations_by_genre(
    genre_ids: str = Query(
        ..., 
        description="Comma-separated genre IDs (e.g., '28,12,16' for Action, Adventure, Animation)",
        regex="^[0-9,]+$"
    ),
    limit: int = Query(20, ge=1, le=50),
    min_rating: float = Query(8.0, ge=0, le=10, description="Minimum vote average"),
    db: Session = Depends(get_db)
):
    """
    Get movie recommendations based on genre preferences
    
    **Use case:**
    - User browsing by genre
    - Finding movies in specific categories
    
    **Parameters:**
    - `genre_ids`: Comma-separated genre IDs (e.g., "28,12")
    - `limit`: Number of results
    - `min_rating`: Minimum TMDB vote average (0-10)
    
    **Common Genre IDs:**
    - 28: Action
    - 12: Adventure
    - 16: Animation
    - 35: Comedy
    - 80: Crime
    - 99: Documentary
    - 18: Drama
    - 14: Fantasy
    - 27: Horror
    - 10402: Music
    - 9648: Mystery
    - 10749: Romance
    - 878: Science Fiction
    - 10770: TV Movie
    - 53: Thriller
    - 10752: War
    - 37: Western
    
    **Example:**
    ```
    GET /api/recommendations/by-genre?genre_ids=28,12&limit=20&min_rating=7.0
    ```
    """
    try:
        # Parse genre IDs
        genre_id_list = [int(gid.strip()) for gid in genre_ids.split(',') if gid.strip()]
        
        if not genre_id_list:
            raise HTTPException(status_code=400, detail="At least one genre ID required")
        
        recommendations = RecommendationService.get_recommendations_by_genre_ids(
            db=db,
            genre_ids=genre_id_list,
            limit=limit,
            min_vote_average=min_rating
        )
        
        return recommendations
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid genre IDs format. Use comma-separated integers.")
    except Exception as e:
        logger.error(f"Error getting genre recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


@router.post("/populate-cache")
async def populate_movie_cache(
    pages: int = Query(5, ge=1, le=20, description="Number of pages to fetch (20 movies per page)"),
    db: Session = Depends(get_db)
):
    """
    Populate movie cache with popular movies from TMDB
    
    **Purpose:**
    - Bootstrap recommendation engine with data
    - Should be run once during setup
    - Can be run periodically to refresh data
    
    **Parameters:**
    - `pages`: Number of pages (1-20). Each page = 20 movies.
    
    **Recommendation:**
    - Start with 5 pages (100 movies) for testing
    - Use 10-20 pages (200-400 movies) for production
    
    **Example:**
    ```
    POST /api/recommendations/populate-cache?pages=10
    ```
    
    **Response:**
    ```json
    {
        "success": 180,
        "errors": 5,
        "skipped": 15,
        "total_cached": 195
    }
    ```
    """
    try:
        result = RecommendationService.populate_cache_from_popular(db, pages)
        return {
            "message": "Cache population complete",
            **result
        }
    except Exception as e:
        logger.error(f"Error populating cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cache population error: {str(e)}")


@router.get("/cache-stats")
async def get_cache_stats(db: Session = Depends(get_db)):
    """
    Get statistics about the movie cache
    
    **Returns:**
    - Total cached movies
    - Cache age distribution
    - Genre coverage
    
    **Example:**
    ```
    GET /api/recommendations/cache-stats
    ```
    """
    from app.models.movie_cache import MovieCache
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    try:
        total_movies = db.query(MovieCache).count()
        
        # Age distribution
        week_old = db.query(MovieCache).filter(
            MovieCache.cached_at > datetime.now() - timedelta(days=7)
        ).count()
        
        month_old = db.query(MovieCache).filter(
            MovieCache.cached_at > datetime.now() - timedelta(days=30)
        ).count()
        
        return {
            "total_cached_movies": total_movies,
            "fresh_cache_week": week_old,
            "fresh_cache_month": month_old,
            "cache_ready": total_movies >= RecommendationService.MIN_CACHE_SIZE,
            "min_required": RecommendationService.MIN_CACHE_SIZE
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")
