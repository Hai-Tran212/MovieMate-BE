"""
Utility script to clear all data from the movie_cache table.

Usage (dev only):
    python -m app.migrations.clear_movie_cache

This will:
    - Delete all rows from movie_cache
    - Print the number of rows deleted
"""

import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import get_db_session
from app.models.movie_cache import MovieCache


def clear_movie_cache():
    db = get_db_session()
    try:
        print("=" * 60)
        print("Clearing movie_cache table (DEV ONLY)...")
        print("=" * 60)

        deleted = db.query(MovieCache).delete()
        db.commit()

        print(f"Deleted {deleted} rows from movie_cache.")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"Error clearing movie_cache: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    clear_movie_cache()


