"""
Migration script to create the password reset tokens table.

Run:
    python -m app.migrations.create_password_reset_tokens
"""

import sys
import os

# Ensure project root is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import engine, Base  # noqa: E402
from app.models.password_reset_token import PasswordResetToken  # noqa: E402


def create_table():
    """Create password reset tokens table."""
    print("Creating password_reset_tokens table...")
    try:
        Base.metadata.create_all(bind=engine, tables=[PasswordResetToken.__table__])
        print("✅ password_reset_tokens table created successfully!")
    except Exception as exc:  # pragma: no cover - migration runtime
        print(f"❌ Failed to create table: {exc}")
        raise


if __name__ == "__main__":
    create_table()

