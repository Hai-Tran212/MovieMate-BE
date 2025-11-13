"""
Background Jobs Service for TMDB Integration
Automatically updates trending/popular movies and cleans up old cache data

Features:
- Scheduled jobs using APScheduler
- Configurable timezone and intervals
- Job monitoring and statistics
- Extensible architecture for adding new jobs
- Error handling and logging
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.tmdb_service import TMDBService
from app.models.movie_cache import MovieCache
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Optional
from pytz import timezone

logger = logging.getLogger(__name__)


class BackgroundJobService:
    """
    Manages scheduled background jobs for TMDB data updates
    
    Jobs:
    - Update trending movies (hourly)
    - Update popular movies (daily at 3 AM)
    - Cleanup old cache (weekly on Sunday at 4 AM)
    
    Usage:
        jobs = BackgroundJobService()
        jobs.start()  # Start all scheduled jobs
        jobs.shutdown()  # Stop all jobs gracefully
    """

    def __init__(self):
        """Initialize scheduler with timezone configuration"""
        tz_name = os.getenv("TIMEZONE", "UTC")
        self.timezone = timezone(tz_name)
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        
        # Track job execution statistics
        self.job_stats = {
            'update_trending': {'last_run': None, 'status': 'idle', 'error': None},
            'update_popular': {'last_run': None, 'status': 'idle', 'error': None},
            'cleanup_cache': {'last_run': None, 'status': 'idle', 'error': None}
        }

    def start(self):
        """
        Start all scheduled background jobs
        
        Jobs are only started if ENABLE_BACKGROUND_JOBS=true in environment
        """
        if os.getenv("ENABLE_BACKGROUND_JOBS", "true").lower() != "true":
            logger.info("Background jobs disabled via ENABLE_BACKGROUND_JOBS environment variable")
            return

        # Job 1: Update trending movies every hour
        self.scheduler.add_job(
            func=self.update_trending_movies,
            trigger=CronTrigger(minute=0, timezone=self.timezone),  # Every hour at :00
            id='update_trending',
            name='Update trending movies from TMDB',
            replace_existing=True,
            max_instances=1  # Prevent concurrent runs
        )
        logger.info("✓ Scheduled: Update trending movies (hourly)")

        # Job 2: Update popular movies daily at 3 AM
        self.scheduler.add_job(
            func=self.update_popular_movies,
            trigger=CronTrigger(hour=3, minute=0, timezone=self.timezone),
            id='update_popular',
            name='Update popular movies from TMDB',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✓ Scheduled: Update popular movies (daily 3:00 AM)")

        # Job 3: Cleanup old cache weekly on Sunday at 4 AM
        self.scheduler.add_job(
            func=self.cleanup_old_cache,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0, timezone=self.timezone),
            id='cleanup_cache',
            name='Cleanup old movie cache',
            replace_existing=True,
            max_instances=1
        )
        logger.info("✓ Scheduled: Cleanup old cache (weekly Sunday 4:00 AM)")

        # Start the scheduler
        self.scheduler.start()
        logger.info("=" * 60)
        logger.info("🚀 Background jobs started successfully")
        logger.info(f"   Timezone: {self.timezone}")
        logger.info(f"   Active jobs: {len(self.scheduler.get_jobs())}")
        logger.info("=" * 60)

    def shutdown(self):
        """Shutdown scheduler gracefully"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Background jobs stopped gracefully")

    def get_job_stats(self) -> Dict:
        """
        Get statistics for all jobs including next run times
        
        Returns:
            Dict with job information and execution history
        """
        jobs_info = []
        for job in self.scheduler.get_jobs():
            stats = self.job_stats.get(job.id, {})
            jobs_info.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'last_run': stats.get('last_run'),
                'status': stats.get('status', 'idle'),
                'error': stats.get('error')
            })
        
        return {
            'scheduler_running': self.scheduler.running,
            'timezone': str(self.timezone),
            'jobs': jobs_info
        }

    # ============================================
    # Main Job Methods
    # ============================================

    def update_trending_movies(self):
        """
        Fetch and cache trending movies from TMDB
        
        Fetches:
        - Trending movies (day)
        - Trending movies (week)
        
        Updates MovieCache table with fresh data
        """
        job_id = 'update_trending'
        self.job_stats[job_id]['status'] = 'running'
        self.job_stats[job_id]['error'] = None
        
        db: Session = SessionLocal()
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting trending movies update...")
            
            # Fetch trending for both day and week
            trending_day = TMDBService.get_trending('day', page=1)
            trending_week = TMDBService.get_trending('week', page=1)
            
            # Combine results and remove duplicates
            all_movies = trending_day.get('results', []) + trending_week.get('results', [])
            unique_movies = {movie['id']: movie for movie in all_movies}.values()
            
            updated_count = 0
            for movie_data in unique_movies:
                self._update_or_create_cache(db, movie_data)
                updated_count += 1
            
            db.commit()
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"[{job_id}] ✓ Completed in {elapsed:.2f}s - Updated {updated_count} movies")
            
            self.job_stats[job_id]['status'] = 'success'
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        except Exception as e:
            db.rollback()
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"[{job_id}] ✗ Failed after {elapsed:.2f}s: {error_msg}")
            
            self.job_stats[job_id]['status'] = 'failed'
            self.job_stats[job_id]['error'] = error_msg
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        finally:
            db.close()

    def update_popular_movies(self):
        """
        Fetch and cache popular movies from TMDB
        
        Fetches first 5 pages (100 movies) of popular movies
        Updates MovieCache with detailed information
        """
        job_id = 'update_popular'
        self.job_stats[job_id]['status'] = 'running'
        self.job_stats[job_id]['error'] = None
        
        db: Session = SessionLocal()
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting popular movies update...")
            
            updated_count = 0
            pages = int(os.getenv("POPULAR_MOVIES_PAGES", "5"))
            
            for page in range(1, pages + 1):
                popular_data = TMDBService.get_popular(page=page)
                
                for movie_data in popular_data.get('results', []):
                    self._update_or_create_cache(db, movie_data)
                    updated_count += 1
                
                # Commit after each page to avoid large transactions
                db.commit()
                logger.info(f"[{job_id}] Processed page {page}/{pages}")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"[{job_id}] ✓ Completed in {elapsed:.2f}s - Updated {updated_count} movies")
            
            self.job_stats[job_id]['status'] = 'success'
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        except Exception as e:
            db.rollback()
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"[{job_id}] ✗ Failed after {elapsed:.2f}s: {error_msg}")
            
            self.job_stats[job_id]['status'] = 'failed'
            self.job_stats[job_id]['error'] = error_msg
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        finally:
            db.close()

    def cleanup_old_cache(self):
        """
        Remove movie cache entries older than configured retention period
        
        Default: 30 days (configurable via CACHE_RETENTION_DAYS env var)
        """
        job_id = 'cleanup_cache'
        self.job_stats[job_id]['status'] = 'running'
        self.job_stats[job_id]['error'] = None
        
        db: Session = SessionLocal()
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting cache cleanup...")
            
            # Get retention period from environment (default 30 days)
            retention_days = int(os.getenv("CACHE_RETENTION_DAYS", "30"))
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Delete old entries
            deleted_count = db.query(MovieCache).filter(
                MovieCache.cached_at < cutoff_date
            ).delete()
            
            db.commit()
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"[{job_id}] ✓ Completed in {elapsed:.2f}s - Deleted {deleted_count} old entries")
            
            self.job_stats[job_id]['status'] = 'success'
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        except Exception as e:
            db.rollback()
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"[{job_id}] ✗ Failed after {elapsed:.2f}s: {error_msg}")
            
            self.job_stats[job_id]['status'] = 'failed'
            self.job_stats[job_id]['error'] = error_msg
            self.job_stats[job_id]['last_run'] = datetime.now().isoformat()
            
        finally:
            db.close()

    # ============================================
    # Helper Methods
    # ============================================

    def _update_or_create_cache(self, db: Session, movie_data: Dict):
        """
        Update existing cache entry or create new one
        
        Args:
            db: Database session
            movie_data: Movie data from TMDB API
        """
        tmdb_id = movie_data.get('id')
        if not tmdb_id:
            return
        
        # Check if movie already exists in cache
        existing = db.query(MovieCache).filter(
            MovieCache.tmdb_id == tmdb_id
        ).first()
        
        # Extract relevant data
        cache_data = {
            'title': movie_data.get('title', ''),
            'overview': movie_data.get('overview', ''),
            'release_date': movie_data.get('release_date', ''),
            'poster_path': movie_data.get('poster_path'),
            'backdrop_path': movie_data.get('backdrop_path'),
            'vote_average': movie_data.get('vote_average', 0.0),
            'popularity': movie_data.get('popularity', 0.0),
            'genres': [g['id'] for g in movie_data.get('genre_ids', [])] if isinstance(movie_data.get('genre_ids'), list) else movie_data.get('genre_ids', []),
            'cached_at': datetime.utcnow()
        }
        
        if existing:
            # Update existing entry
            for key, value in cache_data.items():
                setattr(existing, key, value)
        else:
            # Create new entry
            cache_data['tmdb_id'] = tmdb_id
            new_cache = MovieCache(**cache_data)
            db.add(new_cache)

    # ============================================
    # Extensibility Methods
    # ============================================

    def add_custom_job(self, 
                       func, 
                       trigger, 
                       job_id: str, 
                       name: str,
                       replace_existing: bool = True):
        """
        Add a custom background job dynamically
        
        Example:
            def my_custom_job():
                print("Custom job running!")
            
            jobs.add_custom_job(
                func=my_custom_job,
                trigger=CronTrigger(hour=5, minute=0),
                job_id='my_job',
                name='My Custom Job'
            )
        
        Args:
            func: Job function to execute
            trigger: APScheduler trigger (CronTrigger, IntervalTrigger, etc.)
            job_id: Unique job identifier
            name: Human-readable job name
            replace_existing: Replace if job_id already exists
        """
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name,
            replace_existing=replace_existing,
            max_instances=1
        )
        
        # Initialize stats tracking
        self.job_stats[job_id] = {
            'last_run': None,
            'status': 'idle',
            'error': None
        }
        
        logger.info(f"✓ Added custom job: {name} (ID: {job_id})")

    def remove_job(self, job_id: str):
        """
        Remove a scheduled job by ID
        
        Args:
            job_id: Job identifier to remove
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.job_stats:
                del self.job_stats[job_id]
            logger.info(f"✓ Removed job: {job_id}")
        except Exception as e:
            logger.error(f"✗ Failed to remove job {job_id}: {str(e)}")

    def pause_job(self, job_id: str):
        """Pause a scheduled job"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸ Paused job: {job_id}")
        except Exception as e:
            logger.error(f"✗ Failed to pause job {job_id}: {str(e)}")

    def resume_job(self, job_id: str):
        """Resume a paused job"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶ Resumed job: {job_id}")
        except Exception as e:
            logger.error(f"✗ Failed to resume job {job_id}: {str(e)}")


# Global singleton instance
background_jobs = BackgroundJobService()
