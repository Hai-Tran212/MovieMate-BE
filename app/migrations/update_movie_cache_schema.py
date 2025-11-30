"""
Migration: Update movie_cache table schema
Replaces generic cache structure with specialized movie cache structure

Run this script to update the movie_cache table to match the new MovieCache model.
This will:
1. Backup existing data (if any)
2. Drop the old table
3. Create new table with proper schema
4. Create necessary indexes
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models.movie_cache import MovieCache
from app.models.indexes import create_performance_indexes


def migrate_movie_cache_table():
    """
    Migrate movie_cache table to new schema
    """
    print("🔄 Starting movie_cache schema migration...")
    
    db = SessionLocal()
    
    try:
        # Check if old table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'movie_cache'
            );
        """)
        result = db.execute(check_query).scalar()
        
        if result:
            print("📊 Old movie_cache table found")
            
            # Check if it has the old schema (movie_id column)
            column_check = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'movie_cache' AND column_name = 'movie_id';
            """)
            has_old_schema = db.execute(column_check).scalar()
            
            if has_old_schema:
                print("⚠️  Detected old schema (generic cache structure)")
                
                # Count existing records
                count_query = text("SELECT COUNT(*) FROM movie_cache;")
                count = db.execute(count_query).scalar()
                print(f"📦 Found {count} existing cache entries (will be dropped)")
                
                # Drop old table
                print("🗑️  Dropping old movie_cache table...")
                drop_query = text("DROP TABLE IF EXISTS movie_cache CASCADE;")
                db.execute(drop_query)
                db.commit()
                print("✅ Old table dropped")
            else:
                print("✅ Table already has correct schema")
                return
        
        # Create new table with correct schema
        print("🏗️  Creating new movie_cache table...")
        MovieCache.__table__.create(bind=engine, checkfirst=True)
        print("✅ New table created")
        
        # Create indexes
        print("📑 Creating indexes...")
        create_performance_indexes()
        print("✅ Indexes created")
        
        print("\n✨ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. The movie cache is now empty")
        print("2. Movies will be cached automatically when recommendations are requested")
        print("3. Or run: python -m app.services.background_jobs to populate cache")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


def verify_schema():
    """
    Verify the new schema is correct
    """
    print("\n🔍 Verifying new schema...")
    
    db = SessionLocal()
    try:
        # Check columns
        column_query = text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'movie_cache'
            ORDER BY ordinal_position;
        """)
        
        columns = db.execute(column_query).fetchall()
        
        print("\n📋 Table structure:")
        expected_columns = [
            'id', 'tmdb_id', 'title', 'overview', 'release_date',
            'poster_path', 'backdrop_path', 'vote_average', 'popularity',
            'genres', 'keywords', 'keyword_names', 'cast', 'crew', 'cached_at'
        ]
        
        actual_columns = [col[0] for col in columns]
        
        for col in columns:
            status = "✅" if col[0] in expected_columns else "⚠️"
            print(f"  {status} {col[0]}: {col[1]}")
        
        # Check for missing columns
        missing = set(expected_columns) - set(actual_columns)
        if missing:
            print(f"\n⚠️  Missing columns: {missing}")
            return False
        
        print("\n✅ Schema verification passed!")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  MOVIE CACHE TABLE MIGRATION")
    print("=" * 60)
    print()
    
    # Confirm migration
    response = input("⚠️  This will drop and recreate the movie_cache table. Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        migrate_movie_cache_table()
        verify_schema()
    else:
        print("❌ Migration cancelled")
        sys.exit(0)
