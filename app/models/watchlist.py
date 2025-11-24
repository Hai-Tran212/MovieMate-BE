from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from typing import Optional
from app.database import Base


class Watchlist(Base):
    """
    Watchlist model - Movies saved by users to watch later
    Matches database schema exactly
    """
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey('movies.id', ondelete='CASCADE'), nullable=False, index=True)
    watched = Column(Boolean, default=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    watched_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="watchlist_items")
    movie = relationship("Movie")

    # Ensure one entry per user per movie
    __table_args__ = (
        UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_watchlist'),
    )
    @property
    def tmdb_id(self) -> Optional[int]:
        """Get TMDB ID from related movie"""
        return self.movie.tmdb_id if self.movie else None
        return self.movie.tmdb_id if self.movie else None

    def __repr__(self):
        return f"<Watchlist(user_id={self.user_id}, movie_id={self.movie_id}, watched={self.watched})>"


class CustomList(Base):
    """
    Custom Lists model - Users can create custom movie lists (e.g., "Favorites", "To Watch", "Sci-Fi Collection")
    """
    __tablename__ = "custom_lists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)  # Can other users see this list?
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="custom_lists")
    list_items = relationship("CustomListItem", back_populates="custom_list", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CustomList(id={self.id}, name={self.name}, user_id={self.user_id})>"


class CustomListItem(Base):
    """
    Custom List Items - Movies in a custom list
    """
    __tablename__ = "custom_list_items"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey('custom_lists.id', ondelete='CASCADE'), nullable=False, index=True)
    movie_id = Column(Integer, nullable=False)  # TMDB movie ID
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    # Relationship
    custom_list = relationship("CustomList", back_populates="list_items")

    def __repr__(self):
        return f"<CustomListItem(list_id={self.list_id}, movie_id={self.movie_id})"
