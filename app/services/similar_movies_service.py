"""
Similar Movies Service - Real-time similarity based on movie attributes
No caching required - fetches fresh data from TMDB API
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.services.tmdb_service import TMDBService
import logging

logger = logging.getLogger(__name__)


class SimilarMoviesService:
    """
    Find similar movies based on current movie attributes
    - Uses TMDB's /movie/{id}/similar endpoint
    - Falls back to genre/keyword matching
    - No caching required - real-time data
    """
    
    @staticmethod
    def get_similar_movies(movie_id: int, limit: int = 20) -> List[Dict]:
        """
        Get similar movies using TMDB API
        
        Method 1: Use TMDB's built-in similar endpoint (recommended)
        Method 2: Fallback to genre-based matching
        
        Args:
            movie_id: TMDB movie ID
            limit: Number of results to return
            
        Returns:
            List of similar movies with metadata
        """
        try:
            # Method 1: Use TMDB's similar movies endpoint
            similar_data = TMDBService._make_request(
                f"/movie/{movie_id}/similar",
                params={"page": 1}
            )
            
            movies = similar_data.get('results', [])[:limit]
            
            # Transform to our format
            results = []
            for movie in movies:
                results.append({
                    'tmdb_id': movie.get('id'),
                    'title': movie.get('title'),
                    'overview': movie.get('overview'),
                    'poster_path': movie.get('poster_path'),
                    'backdrop_path': movie.get('backdrop_path'),
                    'vote_average': movie.get('vote_average', 0),
                    'release_date': movie.get('release_date', ''),
                    'popularity': movie.get('popularity', 0),
                    'genre_ids': movie.get('genre_ids', [])
                })
            
            logger.info(f"Found {len(results)} similar movies for movie {movie_id} using TMDB API")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching similar movies from TMDB: {str(e)}")
            # Fallback to genre-based matching
            return SimilarMoviesService._get_by_genre_fallback(movie_id, limit)
    
    @staticmethod
    def _get_by_genre_fallback(movie_id: int, limit: int) -> List[Dict]:
        """
        Fallback method: Find movies with same genres
        
        Args:
            movie_id: TMDB movie ID
            limit: Number of results
            
        Returns:
            List of movies sharing genres
        """
        try:
            # Get target movie details
            movie_data = TMDBService.get_movie_details(movie_id)
            genre_ids = [g['id'] for g in movie_data.get('genres', [])]
            
            if not genre_ids:
                logger.warning(f"No genres found for movie {movie_id}")
                return []
            
            # Find movies with same genres using discover endpoint
            discover_params = {
                'with_genres': ','.join(map(str, genre_ids)),
                'sort_by': 'popularity.desc',
                'page': 1
            }
            
            discover_data = TMDBService._make_request("/discover/movie", params=discover_params)
            movies = discover_data.get('results', [])
            
            # Filter out the original movie and limit results
            results = []
            for movie in movies:
                if movie.get('id') != movie_id and len(results) < limit:
                    results.append({
                        'tmdb_id': movie.get('id'),
                        'title': movie.get('title'),
                        'overview': movie.get('overview'),
                        'poster_path': movie.get('poster_path'),
                        'backdrop_path': movie.get('backdrop_path'),
                        'vote_average': movie.get('vote_average', 0),
                        'release_date': movie.get('release_date', ''),
                        'popularity': movie.get('popularity', 0),
                        'genre_ids': movie.get('genre_ids', [])
                    })
            
            logger.info(f"Found {len(results)} similar movies using genre fallback")
            return results
            
        except Exception as e:
            logger.error(f"Error in genre fallback: {str(e)}")
            return []
    
    @staticmethod
    def get_by_genre(genre_ids: List[int], limit: int = 20, min_rating: float = 6.0) -> List[Dict]:
        """
        Get movies by genre IDs
        
        Args:
            genre_ids: List of TMDB genre IDs
            limit: Number of results
            min_rating: Minimum vote average
            
        Returns:
            List of movies matching genres
        """
        try:
            params = {
                'with_genres': ','.join(map(str, genre_ids)),
                'vote_average.gte': min_rating,
                'sort_by': 'vote_average.desc',
                'page': 1
            }
            
            discover_data = TMDBService._make_request("/discover/movie", params=params)
            movies = discover_data.get('results', [])[:limit]
            
            results = []
            for movie in movies:
                results.append({
                    'tmdb_id': movie.get('id'),
                    'title': movie.get('title'),
                    'overview': movie.get('overview'),
                    'poster_path': movie.get('poster_path'),
                    'backdrop_path': movie.get('backdrop_path'),
                    'vote_average': movie.get('vote_average', 0),
                    'release_date': movie.get('release_date', ''),
                    'popularity': movie.get('popularity', 0),
                    'genre_ids': movie.get('genre_ids', [])
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error fetching movies by genre: {str(e)}")
            return []
