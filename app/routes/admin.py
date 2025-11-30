"""
Admin Routes for Background Jobs Management
Provides endpoints to monitor and control scheduled TMDB jobs

Features:
- Manual job triggers
- Job status monitoring
- Pause/resume jobs
- Cache statistics
- Protected by authentication

All endpoints require authentication via get_current_user dependency
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.movie_cache import MovieCache
from app.services.background_jobs import background_jobs
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/admin", tags=["Admin - Background Jobs"])


@router.post("/jobs/trigger/trending", status_code=status.HTTP_200_OK)
async def trigger_trending_update(
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger trending movies update
    
    - Fetches trending movies (day and week) from TMDB
    - Updates MovieCache with fresh data
    - Returns execution status
    
    **Requires authentication**
    """
    try:
        background_jobs.update_trending_movies()
        return {
            "message": "Trending movies update triggered successfully",
            "job": "update_trending",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": current_user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger trending update: {str(e)}"
        )


@router.post("/jobs/trigger/popular", status_code=status.HTTP_200_OK)
async def trigger_popular_update(
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger popular movies update
    
    - Fetches popular movies (5 pages = 100 movies) from TMDB
    - Updates MovieCache with fresh data
    - Returns execution status
    
    **Requires authentication**
    """
    try:
        background_jobs.update_popular_movies()
        return {
            "message": "Popular movies update triggered successfully",
            "job": "update_popular",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": current_user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger popular update: {str(e)}"
        )


@router.post("/jobs/trigger/cleanup", status_code=status.HTTP_200_OK)
async def trigger_cache_cleanup(
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger cache cleanup
    
    - Removes movie cache entries older than 30 days
    - Returns number of deleted entries
    
    **Requires authentication**
    """
    try:
        background_jobs.cleanup_old_cache()
        return {
            "message": "Cache cleanup triggered successfully",
            "job": "cleanup_cache",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": current_user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger cleanup: {str(e)}"
        )


@router.get("/jobs/status", status_code=status.HTTP_200_OK)
async def get_jobs_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get status of all scheduled background jobs
    
    Returns:
    - Job IDs and names
    - Next run times
    - Last execution times
    - Current status (idle/running/success/failed)
    - Error messages (if any)
    
    **Requires authentication**
    """
    try:
        stats = background_jobs.get_job_stats()
        return {
            "scheduler_running": stats['scheduler_running'],
            "timezone": stats['timezone'],
            "jobs": stats['jobs'],
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.post("/jobs/pause/{job_id}", status_code=status.HTTP_200_OK)
async def pause_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Pause a specific background job
    
    Valid job_ids:
    - update_trending
    - update_popular
    - cleanup_cache
    
    **Requires authentication**
    """
    valid_jobs = ['update_trending', 'update_popular', 'cleanup_cache']
    
    if job_id not in valid_jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id. Must be one of: {', '.join(valid_jobs)}"
        )
    
    try:
        background_jobs.pause_job(job_id)
        return {
            "message": f"Job '{job_id}' paused successfully",
            "job_id": job_id,
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_by": current_user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause job: {str(e)}"
        )


@router.post("/jobs/resume/{job_id}", status_code=status.HTTP_200_OK)
async def resume_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Resume a paused background job
    
    Valid job_ids:
    - update_trending
    - update_popular
    - cleanup_cache
    
    **Requires authentication**
    """
    valid_jobs = ['update_trending', 'update_popular', 'cleanup_cache']
    
    if job_id not in valid_jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id. Must be one of: {', '.join(valid_jobs)}"
        )
    
    try:
        background_jobs.resume_job(job_id)
        return {
            "message": f"Job '{job_id}' resumed successfully",
            "job_id": job_id,
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "resumed_by": current_user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume job: {str(e)}"
        )


@router.get("/cache/stats", status_code=status.HTTP_200_OK)
async def get_cache_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get movie cache statistics
    
    Returns:
    - Total cached movies
    - Cache by date ranges (last 24h, 7d, 30d)
    - Average rating and popularity
    - Genre distribution
    
    **Requires authentication**
    """
    try:
        # Total count
        total_movies = db.query(MovieCache).count()
        
        # Recent caches
        now = datetime.now(timezone.utc)
        last_24h = db.query(MovieCache).filter(
            MovieCache.cached_at > now - timedelta(hours=24)
        ).count()
        
        last_7d = db.query(MovieCache).filter(
            MovieCache.cached_at > now - timedelta(days=7)
        ).count()
        
        last_30d = db.query(MovieCache).filter(
            MovieCache.cached_at > now - timedelta(days=30)
        ).count()
        
        # Average metrics
        from sqlalchemy import func
        avg_rating = db.query(func.avg(MovieCache.vote_average)).scalar() or 0.0
        avg_popularity = db.query(func.avg(MovieCache.popularity)).scalar() or 0.0
        
        # Top rated movies in cache
        top_rated = db.query(MovieCache).order_by(
            MovieCache.vote_average.desc()
        ).limit(5).all()
        
        return {
            "total_cached_movies": total_movies,
            "cache_age_distribution": {
                "last_24_hours": last_24h,
                "last_7_days": last_7d,
                "last_30_days": last_30d,
                "older_than_30_days": total_movies - last_30d
            },
            "average_metrics": {
                "rating": round(avg_rating, 2),
                "popularity": round(avg_popularity, 2)
            },
            "top_rated_cached": [
                {
                    "title": movie.title,
                    "tmdb_id": movie.tmdb_id,
                    "rating": movie.vote_average,
                    "cached_at": movie.cached_at.isoformat() if movie.cached_at else None
                }
                for movie in top_rated
            ],
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache statistics: {str(e)}"
        )


@router.delete("/cache/clear", status_code=status.HTTP_200_OK)
async def clear_all_cache(
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clear all movie cache entries (DANGEROUS)
    
    Query Parameters:
    - confirm: Must be true to execute
    
    **Requires authentication**
    **Use with caution - this will delete all cached data**
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must set confirm=true to clear cache"
        )
    
    try:
        count = db.query(MovieCache).count()
        db.query(MovieCache).delete()
        db.commit()
        
        return {
            "message": "Cache cleared successfully",
            "deleted_count": count,
            "cleared_at": datetime.now(timezone.utc).isoformat(),
            "cleared_by": current_user.email,
            "warning": "All movie cache data has been deleted. Run populate jobs to rebuild."
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )
