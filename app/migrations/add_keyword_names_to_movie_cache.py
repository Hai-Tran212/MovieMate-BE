"""
Migration script to add keyword_names column to movie_cache table.

Usage:
    python -m app.migrations.add_keyword_names_to_movie_cache

This will:
    - Add a JSON column 'keyword_names' to the movie_cache table if it does not exist.

Existing rows will have NULL keyword_names until cache is repopulated or
explicitly refreshed.
"""

import sys
import os

from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import engine


def add_keyword_names_column():
    print("=" * 60)
    print("Adding keyword_names column to movie_cache table...")
    print("=" * 60)

    with engine.connect() as conn:
        # Detect database type from URL
        url = str(engine.url)

        # PostgreSQL: use ALTER TABLE ... ADD COLUMN IF NOT EXISTS
        if url.startswith("postgresql"):
            alter_sql = """
            ALTER TABLE movie_cache
            ADD COLUMN IF NOT EXISTS keyword_names JSONB
            """
        else:
            # Generic SQL (SQLite, MySQL, etc.) - best effort without IF NOT EXISTS
            # Some engines don't support JSON natively, but SQLAlchemy will still
            # map the column correctly for ORM usage.
            alter_sql = """
            ALTER TABLE movie_cache
            ADD COLUMN keyword_names JSON
            """

        try:
            conn.execute(text(alter_sql))
            conn.commit()
            print("✅ keyword_names column added (or already exists).")
        except Exception as e:
            print(f"❌ Error adding keyword_names column: {e}")
            raise


if __name__ == "__main__":
    add_keyword_names_column()


