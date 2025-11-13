from sqlalchemy import Column, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class UserPref(Base):
    __tablename__ = "user_prefs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    favorite_genres = Column(JSON)  # List of genre IDs [28, 12, 16, ...]
    disliked_genres = Column(JSON)  # List of genre IDs to avoid
    preferred_languages = Column(JSON)  # List of language codes ['en', 'vi', ...]
    min_rating = Column(Integer, default=0)  # Minimum rating threshold (0-10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="preferences")
