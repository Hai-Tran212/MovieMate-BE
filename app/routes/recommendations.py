"""
Recommendation Routes
Endpoints for content-based, collaborative, and hybrid movie recommendations
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.recommendation_service import RecommendationService
from app.utils.dependencies import get_current_user
from app.models.user import User
from typing import List, Dict, Optional
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


@router.get("/mood/{mood}")
async def get_mood_recommendations(
    mood: str,
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations (1-50)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get recommendations based on current mood
    
    **Available Moods:**
    - `happy`: Comedy, Family, Animation, Music
    - `sad`: Drama, Romance
    - `excited`: Action, Adventure, Sci-Fi
    - `relaxed`: Comedy, Family, Animation
    - `scared`: Horror, Thriller
    - `thoughtful`: Drama, Mystery, History, Documentary
    - `romantic`: Romance, Comedy, Drama
    
    **Algorithm:**
    - Maps mood to specific genre combinations
    - Considers runtime preferences per mood
    - Personalizes based on user's rating history
    - Adds diversity to avoid repetitive recommendations
    
    **Parameters:**
    - `mood`: One of the available moods listed above
    - `limit`: Number of recommendations (default: 20, max: 50)
    
    **Returns:**
    List of movies matching the mood with mood scores
    
    **Example:**
    ```
    GET /api/recommendations/mood/happy?limit=15
    ```
    
    **Response:**
    ```json
    {
        "mood": "happy",
        "genres": [35, 10751, 16, 10402],
        "recommendations": [...],
        "count": 15
    }
    ```
    
    **Note:** Authentication optional. If authenticated, recommendations are personalized.
    """
    from app.utils.dependencies import get_current_user
    from app.models.user import User
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    
    try:
        # Default to anonymous user
        user_id: int = 1
        
        # Try to authenticate if Authorization header is present
        if authorization and authorization.startswith("Bearer "):
            try:
                # Extract token and get user
                from app.utils.security import decode_token
                token = authorization.replace("Bearer ", "")
                payload = decode_token(token)
                
                if payload and payload.get("type") == "access":
                    authenticated_user_id = payload.get("user_id")
                    user = db.query(User).filter(User.id == authenticated_user_id).first()
                    
                    if user is not None and authenticated_user_id is not None:
                        # Use the ID from token payload (it's an int)
                        user_id = authenticated_user_id
                        logger.info(f"Authenticated user {user_id} requesting mood recommendations")
            except Exception as auth_error:
                # If auth fails, just continue with anonymous user
                logger.debug(f"Authentication failed, using anonymous user: {str(auth_error)}")
        
        recommendations = RecommendationService.get_mood_based_recommendations(
            db=db,
            user_id=user_id,
            mood=mood,
            limit=limit
        )
        
        # Get mood configuration for response
        mood_config = RecommendationService.MOOD_TO_GENRES.get(mood, {})
        
        return {
            "mood": mood,
            "genres": mood_config.get('include', []) if isinstance(mood_config, dict) else mood_config,
            "excluded_genres": mood_config.get('exclude', []) if isinstance(mood_config, dict) else [],
            "runtime_preference": RecommendationService.MOOD_RUNTIME_PREFS.get(mood),
            "recommendations": recommendations,
            "count": len(recommendations),
            "algorithm": "enhanced_mood_matching_v2"  # Version tracking
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting mood recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Mood recommendation error: {str(e)}")


# ==================== HYBRID RECOMMENDATION ENDPOINTS ====================

@router.get("/hybrid", response_model=Dict)
async def get_hybrid_recommendations(
    movie_id: Optional[int] = Query(None, description="Optional movie ID for content-based component"),
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations (1-50)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get hybrid recommendations combining content-based and collaborative filtering
    
    **Algorithm:**
    - 70% Content-based filtering (similar movies or user preferences)
    - 30% Collaborative filtering (similar users' ratings)
    - Normalized hybrid scoring
    
    **Parameters:**
    - `movie_id`: Optional - if provided, uses similar movies as content component
    - `limit`: Number of recommendations (default: 20, max: 50)
    
    **Returns:**
    Hybrid recommendations with combined scores showing:
    - `hybrid_score`: Combined score (0.0 to 1.0)
    - `content_score`: Content-based component score
    - `collab_score`: Collaborative filtering component score
    
    **Authentication Required:** Yes (JWT token in Authorization header)
    
    **Example:**
    ```
    GET /api/recommendations/hybrid?limit=10
    GET /api/recommendations/hybrid?movie_id=550&limit=20
    ```
    """
    try:
        recommendations = RecommendationService.get_hybrid_recommendations(
            db=db,
            user_id=current_user.id,
            movie_id=movie_id,
            limit=limit
        )
        
        return {
            "user_id": current_user.id,
            "movie_id": movie_id,
            "algorithm": "hybrid_70_30",
            "content_weight": RecommendationService.HYBRID_CONTENT_WEIGHT,
            "collaborative_weight": RecommendationService.HYBRID_COLLABORATIVE_WEIGHT,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error in hybrid recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Hybrid recommendation error: {str(e)}")


@router.get("/for-you", response_model=Dict)
async def get_personalized_recommendations(
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations (1-50)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized recommendations for the current user
    
    **Algorithm:**
    Uses hybrid recommendation algorithm based on:
    - User's rating history
    - Similar users' preferences
    - Content-based similarity
    
    **Parameters:**
    - `limit`: Number of recommendations (default: 20, max: 50)
    
    **Returns:**
    Personalized movie recommendations with hybrid scores
    
    **Authentication Required:** Yes (JWT token in Authorization header)
    
    **Example:**
    ```
    GET /api/recommendations/for-you?limit=15
    ```
    """
    try:
        recommendations = RecommendationService.get_personalized_recommendations(
            db=db,
            user_id=current_user.id,
            limit=limit
        )
        
        return {
            "user_id": current_user.id,
            "algorithm": "personalized_hybrid",
            "recommendations": recommendations,
            "count": len(recommendations),
            "message": "Recommendations personalized based on your rating history and similar users"
        }
        
    except Exception as e:
        logger.error(f"Error in personalized recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Personalized recommendation error: {str(e)}")
