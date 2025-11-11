"""
Movie Cache Model for storing TMDB movie data locally
This improves recommendation performance and reduces API calls
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Text
from sqlalchemy.sql import func
from app.database import Base


class MovieCache(Base):
    """
    Caches movie data from TMDB API for recommendation engine
    
    Attributes:
        id: Primary key
        tmdb_id: TMDB movie ID (unique identifier)
        title: Movie title
        genres: List of genre IDs [28, 12, 16]
        keywords: List of keyword IDs for content matching
        cast: List of top 10 actor IDs
        crew: List of director/writer/producer IDs
        vote_average: TMDB rating (0-10)
        popularity: TMDB popularity score
        overview: Movie description/synopsis
        release_date: Release date (YYYY-MM-DD)
        poster_path: Poster image path
        backdrop_path: Backdrop image path
        cached_at: Timestamp when data was cached
    """
    __tablename__ = "movie_cache"

    # Primary identifiers
    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, unique=True, index=True, nullable=False)
    
    # Basic movie info
    title = Column(String(500), nullable=False)
    overview = Column(Text)
    release_date = Column(String(20))
    poster_path = Column(String(200))
    backdrop_path = Column(String(200))
    
    # Metrics
    vote_average = Column(Float, default=0.0)
    popularity = Column(Float, default=0.0)
    
    # Feature vectors for recommendations (stored as JSON arrays)
    genres = Column(JSON)           # [28, 12, 16] - Action, Adventure, Animation
    keywords = Column(JSON)         # [1234, 5678] - Keyword IDs
    cast = Column(JSON)             # [500, 501] - Actor IDs (top 10)
    crew = Column(JSON)             # [100, 101] - Director, Writer, Producer IDs
    
    # Timestamp
    cached_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<MovieCache(tmdb_id={self.tmdb_id}, title='{self.title}')>"
