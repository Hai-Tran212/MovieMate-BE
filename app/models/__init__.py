"""
Import all models to ensure they are registered with SQLAlchemy
"""
from app.models.user import User
from app.models.movie import Movie
from app.models.movie_cache import MovieCache
from app.models.rating import Rating
from app.models.watchlist import Watchlist
from app.models.review import Review
from app.models.user_pref import UserPref

__all__ = [
    "User",
    "Movie",
    "MovieCache",
    "Rating",
    "Watchlist",
    "Review",
    "UserPref"
]
