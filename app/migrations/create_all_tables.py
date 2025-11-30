"""
Migration script to create all database tables

Run this script to create all database tables:
    python -m app.migrations.create_all_tables
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import engine, Base
# Import all models to ensure they're registered with Base
from app.models.user import User
from app.models.movie import Movie
from app.models.rating import Rating
from app.models.review import Review
from app.models.watchlist import Watchlist, CustomList, CustomListItem
from app.models.user_pref import UserPref
from app.models.movie_cache import MovieCache
from app.models.password_reset_token import PasswordResetToken


def create_tables():
    """Create all database tables"""
    print("=" * 60)
    print("Creating all database tables...")
    print("=" * 60)
    
    try:
        # Create all tables defined in Base metadata
        Base.metadata.create_all(bind=engine)
        
        print("\n✅ All tables created successfully!")
        print("\nTables created:")
        print("   - users")
        print("   - movies")
        print("   - ratings")
        print("   - reviews")
        print("   - watchlists")
        print("   - custom_lists")
        print("   - custom_list_items")
        print("   - user_preferences")
        print("   - movie_cache")
        print("   - password_reset_tokens")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    create_tables()
