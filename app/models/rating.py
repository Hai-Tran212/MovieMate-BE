from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Float, nullable=False)  # Rating value (e.g., 1-5 or 1-10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="ratings")
    movie = relationship("Movie")
    
    # Ensure one rating per user per movie
    __table_args__ = (
        UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_rating'),
    )
