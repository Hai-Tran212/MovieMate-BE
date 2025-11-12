"""
Migration script to create watchlist and custom lists tables

Run this script to create the database tables:
    python -m app.migrations.create_watchlist_tables
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import engine, Base
from app.models.user import User
from app.models.watchlist import Watchlist, CustomList, CustomListItem


def create_tables():
    """Create all watchlist-related tables"""
    print("Creating watchlist and custom lists tables...")
    
    try:
        # Import all models to ensure they're registered with Base
        Base.metadata.create_all(bind=engine, tables=[
            Watchlist.__table__,
            CustomList.__table__,
            CustomListItem.__table__
        ])
        
        print("✅ Tables created successfully!")
        print("   - watchlists")
        print("   - custom_lists")
        print("   - custom_list_items")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise


if __name__ == "__main__":
    create_tables()
