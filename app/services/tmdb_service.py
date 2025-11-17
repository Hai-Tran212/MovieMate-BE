import requests
import os
from typing import Dict
from fastapi import HTTPException
from app.utils.cache import cache
import logging

logger = logging.getLogger(__name__)

# TMDB Service to interact with The Movie Database API
class TMDBService:
    BASE_URL = "https://api.themoviedb.org/3"
    API_KEY = os.getenv("TMDB_API_KEY")

    # Internal method to make GET requests to TMDB API
    @classmethod
    def _make_request(cls, endpoint: str, params: Dict = None) -> Dict:
        """
        Make HTTP request to TMDB API.
        
        Args:
            endpoint: API endpoint (e.g., "/movie/popular")
            params: Query parameters
            
        Returns:
            JSON response from TMDB
            
        Raises:
            HTTPException: If API key is missing or request fails
        """
        if not cls.API_KEY:
            raise HTTPException(status_code=500, detail="TMDB API key not configured")
        params = params or {}
        params['api_key'] = cls.API_KEY
        url = f"{cls.BASE_URL}{endpoint}"
    
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            logger.debug(f"TMDB API request successful: {endpoint}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API error for {endpoint}: {str(e)}")
            raise HTTPException(status_code=502, detail=f"TMDB API error: {str(e)}")

    # Public methods to access various TMDB endpoints
    @classmethod
    @cache(ttl=300)  # Cache search results for 5 minutes
    def search_movies(cls, query: str, page: int = 1) -> Dict:
        """
        Search movies by title.
        Cached for 5 minutes to reduce API calls.
        """
        return cls._make_request("/search/movie", {'query': query, 'page': page})
    
    @classmethod
    @cache(ttl=600)  # Cache movie details for 10 minutes
    def get_movie_details(cls, movie_id: int) -> Dict:
        """
        Get detailed movie information including videos and credits.
        Cached for 10 minutes.
        """
        return cls._make_request(f"/movie/{movie_id}", {'append_to_response': 'videos,credits'})

    @classmethod
    @cache(ttl=3600)  # Cache trending for 1 hour
    def get_trending(cls, time_window: str = 'week', page: int = 1) -> Dict:
        """
        Get trending movies.
        Cached for 1 hour as trending data changes slowly.
        """
        return cls._make_request(f"/trending/movie/{time_window}", {'page': page})

    @classmethod
    @cache(ttl=3600)  # Cache popular for 1 hour
    def get_popular(cls, page: int = 1) -> Dict:
        """
        Get popular movies.
        Cached for 1 hour.
        """
        return cls._make_request("/movie/popular", {'page': page})

    @classmethod
    @cache(ttl=3600)  # Cache now playing for 1 hour
    def get_now_playing(cls, page: int = 1) -> Dict:
        """
        Get currently playing movies in theaters.
        Cached for 1 hour.
        """
        return cls._make_request("/movie/now_playing", {'page': page})

    @classmethod
    @cache(ttl=3600)  # Cache top rated for 1 hour
    def get_top_rated(cls, page: int = 1) -> Dict:
        """
        Get top rated movies.
        Cached for 1 hour as top rated changes slowly.
        """
        return cls._make_request("/movie/top_rated", {'page': page})

    @classmethod
    @cache(ttl=300)  # Cache discover results for 5 minutes
    def discover_movies(cls, params: Dict) -> Dict:
        """
        Discover movies with advanced filters.
        Supports: genre, year, rating, sort, etc.
        Cached for 5 minutes.
        """
        return cls._make_request("/discover/movie", params)

    @classmethod
    @cache(ttl=86400)  # Cache genres for 24 hours (rarely changes)
    def get_genres(cls) -> Dict:
        """
        Get list of all movie genres from TMDB.
        Cached for 24 hours as genres rarely change.
        """
        return cls._make_request("/genre/movie/list")