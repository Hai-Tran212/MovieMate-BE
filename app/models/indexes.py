"""
Database Performance Indexes
============================
Creates indexes for frequently queried columns to improve performance.

Usage:
    python -m app.models.indexes

This module creates indexes to optimize:
- User email lookups (login)
- Watchlist queries (user_id, movie_id, watched status)
- Rating queries (user_id, movie_id)
- Review queries (user_id, movie_id)
- Movie cache queries (tmdb_id)

Run this after initial deployment or schema changes.
"""
from sqlalchemy import text, inspect
from app.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index already exists"""
    inspector = inspect(engine)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False


def create_performance_indexes():
    """
    Create indexes to speed up common queries.
    This function is idempotent - safe to run multiple times.
    """
    
    # Define all indexes with their purposes
    indexes = [
        # Users table
        {
            "name": "idx_users_email",
            "table": "users",
            "sql": "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "purpose": "Speed up login email lookup"
        },
        {
            "name": "idx_users_active",
            "table": "users",
            "sql": "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;",
            "purpose": "Filter active users efficiently"
        },
        
        # Watchlist table
        {
            "name": "idx_watchlist_user_id",
            "table": "watchlists",
            "sql": "CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlists(user_id);",
            "purpose": "Speed up user watchlist queries"
        },
        {
            "name": "idx_watchlist_movie_id",
            "table": "watchlists",
            "sql": "CREATE INDEX IF NOT EXISTS idx_watchlist_movie_id ON watchlists(movie_id);",
            "purpose": "Speed up movie watchlist lookups"
        },
        {
            "name": "idx_watchlist_watched",
            "table": "watchlists",
            "sql": "CREATE INDEX IF NOT EXISTS idx_watchlist_watched ON watchlists(user_id, watched);",
            "purpose": "Filter watched/unwatched movies"
        },
        {
            "name": "idx_watchlist_added_at",
            "table": "watchlists",
            "sql": "CREATE INDEX IF NOT EXISTS idx_watchlist_added_at ON watchlists(user_id, added_at DESC);",
            "purpose": "Sort watchlist by date added"
        },
        
        # Ratings table
        {
            "name": "idx_ratings_user_id",
            "table": "ratings",
            "sql": "CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);",
            "purpose": "Speed up user ratings queries"
        },
        {
            "name": "idx_ratings_movie_id",
            "table": "ratings",
            "sql": "CREATE INDEX IF NOT EXISTS idx_ratings_movie_id ON ratings(movie_id);",
            "purpose": "Speed up movie ratings queries"
        },
        {
            "name": "idx_ratings_value",
            "table": "ratings",
            "sql": "CREATE INDEX IF NOT EXISTS idx_ratings_value ON ratings(movie_id, rating);",
            "purpose": "Calculate average ratings faster"
        },
        
        # Reviews table
        {
            "name": "idx_reviews_user_id",
            "table": "reviews",
            "sql": "CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);",
            "purpose": "Speed up user reviews queries"
        },
        {
            "name": "idx_reviews_movie_id",
            "table": "reviews",
            "sql": "CREATE INDEX IF NOT EXISTS idx_reviews_movie_id ON reviews(movie_id);",
            "purpose": "Speed up movie reviews queries"
        },
        {
            "name": "idx_reviews_created_at",
            "table": "reviews",
            "sql": "CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(movie_id, created_at DESC);",
            "purpose": "Sort reviews by date"
        },
        
        # Movie cache table
        {
            "name": "idx_movie_cache_tmdb_id",
            "table": "movie_cache",
            "sql": "CREATE INDEX IF NOT EXISTS idx_movie_cache_tmdb_id ON movie_cache(tmdb_id);",
            "purpose": "Speed up TMDB ID lookups"
        },
        {
            "name": "idx_movie_cache_cached_at",
            "table": "movie_cache",
            "sql": "CREATE INDEX IF NOT EXISTS idx_movie_cache_cached_at ON movie_cache(cached_at);",
            "purpose": "Identify stale cache entries"
        },
        
        # Movies table
        {
            "name": "idx_movies_tmdb_id",
            "table": "movies",
            "sql": "CREATE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id);",
            "purpose": "Speed up TMDB ID lookups"
        },
        
        # Custom lists
        {
            "name": "idx_custom_lists_user_id",
            "table": "custom_lists",
            "sql": "CREATE INDEX IF NOT EXISTS idx_custom_lists_user_id ON custom_lists(user_id);",
            "purpose": "Speed up user custom lists queries"
        },
        {
            "name": "idx_custom_list_items_list_id",
            "table": "custom_list_items",
            "sql": "CREATE INDEX IF NOT EXISTS idx_custom_list_items_list_id ON custom_list_items(list_id);",
            "purpose": "Speed up custom list items queries"
        },
    ]
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process each index individually with its own transaction
    for idx in indexes:
        # Use a separate connection for each index to avoid transaction rollback issues
        with engine.connect() as conn:
            try:
                # Check if index exists (for informational purposes)
                exists = index_exists(idx['table'], idx['name'])
                
                if exists:
                    logger.info(f"✓ Index {idx['name']} already exists - {idx['purpose']}")
                    skipped_count += 1
                else:
                    # Execute the CREATE INDEX statement
                    conn.execute(text(idx['sql']))
                    conn.commit()  # Commit immediately
                    logger.info(f"✓ Created index {idx['name']} - {idx['purpose']}")
                    created_count += 1
                    
            except Exception as e:
                # Rollback this transaction and continue with next index
                conn.rollback()
                error_msg = str(e).split('\n')[0]  # Get first line of error
                logger.error(f"✗ Error creating index {idx['name']}: {error_msg}")
                error_count += 1
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("Index Creation Summary:")
    logger.info(f"  Created: {created_count}")
    logger.info(f"  Skipped (already exists): {skipped_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Total: {len(indexes)}")
    logger.info("="*60)
    
    if error_count == 0:
        logger.info("\n✅ All indexes created successfully!")
    else:
        logger.warning(f"\n⚠️ Completed with {error_count} errors")
    
    return {
        "created": created_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total": len(indexes)
    }


def drop_all_custom_indexes():
    """
    Drop all custom indexes (for testing/debugging).
    WARNING: Use with caution! This will slow down queries.
    """
    logger.warning("⚠️ Dropping all custom indexes...")
    
    index_names = [
        "idx_users_email", "idx_users_active",
        "idx_watchlist_user_id", "idx_watchlist_movie_id", "idx_watchlist_watched", "idx_watchlist_added_at",
        "idx_ratings_user_id", "idx_ratings_movie_id", "idx_ratings_value",
        "idx_reviews_user_id", "idx_reviews_movie_id", "idx_reviews_created_at",
        "idx_movie_cache_tmdb_id", "idx_movie_cache_cached_at",
        "idx_movies_tmdb_id",
        "idx_custom_lists_user_id", "idx_custom_list_items_list_id"
    ]
    
    with engine.connect() as conn:
        for idx_name in index_names:
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {idx_name};"))
                logger.info(f"✓ Dropped index {idx_name}")
            except Exception as e:
                logger.error(f"✗ Error dropping index {idx_name}: {str(e)}")
        conn.commit()
    
    logger.info("✅ All indexes dropped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage database performance indexes")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all custom indexes instead of creating them"
    )
    
    args = parser.parse_args()
    
    if args.drop:
        drop_all_custom_indexes()
    else:
        create_performance_indexes()
