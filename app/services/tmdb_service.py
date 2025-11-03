import requests
import os
from typing import Dict
from fastapi import HTTPException

# TMDB Service to interact with The Movie Database API
class TMDBService:
    BASE_URL = "https://api.themoviedb.org/3"
    API_KEY = os.getenv("TMDB_API_KEY")

    # Internal method to make GET requests to TMDB API
    @classmethod
    def _make_request(cls, endpoint: str, params: Dict = None) -> Dict:
        if not cls.API_KEY:
            raise HTTPException(status_code=500, detail="TMDB API key not configured")
        params = params or {}
        params['api_key'] = cls.API_KEY
        url = f"{cls.BASE_URL}{endpoint}"
    
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"TMDB API error: {str(e)}")

    # Public methods to access various TMDB endpoints
    @classmethod
    def search_movies(cls, query: str, page: int = 1) -> Dict:
        return cls._make_request("/search/movie", {'query': query, 'page': page})
    
    # Newly added method for movie details
    @classmethod
    def get_movie_details(cls, movie_id: int) -> Dict:
        return cls._make_request(f"/movie/{movie_id}", {'append_to_response': 'videos,credits'})

    #  Other existing methods
    @classmethod
    def get_trending(cls, time_window: str = 'week', page: int = 1) -> Dict:
        return cls._make_request(f"/trending/movie/{time_window}", {'page': page})

    # Newly added method for popular movies
    @classmethod
    def get_popular(cls, page: int = 1) -> Dict:
        return cls._make_request("/movie/popular", {'page': page})

    # Newly added method for now playing movies
    @classmethod
    def get_now_playing(cls, page: int = 1) -> Dict:

        return cls._make_request("/movie/now_playing", {'page': page})

    # Newly added method for top rated movies
    @classmethod
    def get_top_rated(cls, page: int = 1) -> Dict:
        return cls._make_request("/movie/top_rated", {'page': page})