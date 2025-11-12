from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Watchlist(Base):
    """
    Watchlist model - Movies saved by users to watch later
    """
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    movie_id = Column(Integer, nullable=False, index=True)  # TMDB movie ID
    watched = Column(Boolean, default=False)
    rating = Column(Integer, nullable=True)  # User's rating 1-10 (optional)
    notes = Column(Text, nullable=True)  # Personal notes about the movie
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    watched_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="watchlist_items")

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
        return f"<CustomListItem(list_id={self.list_id}, movie_id={self.movie_id})>"
