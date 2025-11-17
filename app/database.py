from sqlalchemy import create_engine, pool, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Connection pooling configuration for better performance
# QueuePool maintains a pool of connections that can be reused
engine = create_engine(
    DATABASE_URL,
    poolclass=pool.QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", 5)),  # Number of connections to keep open
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),  # Max connections beyond pool_size
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),  # Seconds to wait for connection
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 3600)),  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Test connections before using them
    echo=os.getenv("DB_ECHO", "false").lower() == "true"  # Set to true for SQL debugging
)

# Log pool statistics for monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log when a new connection is created"""
    logger.debug("Database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when a connection is checked out from the pool"""
    logger.debug(f"Connection checked out from pool. Pool size: {engine.pool.size()}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency for FastAPI routes
def get_db():
    """
    Database session dependency for FastAPI.
    Automatically handles session creation and cleanup.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility function for manual session management
def get_db_session():
    """
    Get a database session for manual management.
    Remember to close the session after use!
    
    Usage:
        db = get_db_session()
        try:
            # Use db here
            db.commit()
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    """
    return SessionLocal()