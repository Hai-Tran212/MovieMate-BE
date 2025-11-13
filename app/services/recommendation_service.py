"""
Recommendation Service - Content-Based Filtering Engine
Uses KNN algorithm and cosine similarity for movie recommendations
"""
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.movie_cache import MovieCache
from app.services.tmdb_service import TMDBService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Content-based recommendation engine using:
    - KNN (K-Nearest Neighbors) algorithm
    - Cosine similarity for feature matching
    - Genre, cast, crew, and keyword analysis
    """
    
    # Configuration constants (easy to modify)
    CACHE_EXPIRY_DAYS = 7           # Refresh cached data after 7 days
    MIN_CACHE_SIZE = 50             # Minimum movies needed for KNN
    DEFAULT_LIMIT = 20              # Default number of recommendations
    
    # Feature vector dimensions (for easy modification)
    GENRE_DIM = 5
    KEYWORD_DIM = 10
    CAST_DIM = 5
    CREW_DIM = 3
    
    # Weights for similarity calculation (can be tuned)
    GENRE_WEIGHT = 0.4
    KEYWORD_WEIGHT = 0.3
    CAST_WEIGHT = 0.2
    CREW_WEIGHT = 0.1

    @staticmethod
    def fetch_and_cache_movie(db: Session, movie_id: int) -> Optional[MovieCache]:
        """
        Fetch movie from TMDB API and store in local cache
        
        Process:
        1. Check if movie exists in cache and is recent (< 7 days old)
        2. If not, fetch from TMDB API
        3. Extract features (genres, keywords, cast, crew)
        4. Store in database for future use
        
        Args:
            db: Database session
            movie_id: TMDB movie ID
            
        Returns:
            MovieCache object or None if error
        """
        try:
            # Check cache first (avoid unnecessary API calls)
            cached = db.query(MovieCache).filter(
                and_(
                    MovieCache.tmdb_id == movie_id,
                    MovieCache.cached_at > datetime.now() - timedelta(days=RecommendationService.CACHE_EXPIRY_DAYS)
                )
            ).first()

            if cached:
                logger.info(f"Cache hit for movie {movie_id}")
                return cached

            logger.info(f"Cache miss for movie {movie_id}, fetching from TMDB...")
            
            # Fetch comprehensive movie data from TMDB
            movie_data = TMDBService.get_movie_details(movie_id)
            
            # Fetch additional data for recommendations
            keywords_data = TMDBService._make_request(f"/movie/{movie_id}/keywords")
            
            # Extract features for similarity calculation
            genres = [g['id'] for g in movie_data.get('genres', [])]
            keywords = [k['id'] for k in keywords_data.get('keywords', [])[:20]]  # Top 20 keywords
            
            # Extract cast and crew from credits (already in movie_data)
            credits = movie_data.get('credits', {})
            cast = [c['id'] for c in credits.get('cast', [])[:10]]  # Top 10 actors
            
            # Get key crew members (directors, writers, producers)
            crew_ids = [
                c['id'] for c in credits.get('crew', [])
                if c['job'] in ['Director', 'Writer', 'Screenplay', 'Producer']
            ][:5]  # Top 5 key crew members

            # Create or update cache entry
            new_cache = MovieCache(
                tmdb_id=movie_id,
                title=movie_data.get('title', 'Unknown'),
                overview=movie_data.get('overview', ''),
                release_date=movie_data.get('release_date', ''),
                poster_path=movie_data.get('poster_path'),
                backdrop_path=movie_data.get('backdrop_path'),
                vote_average=movie_data.get('vote_average', 0.0),
                popularity=movie_data.get('popularity', 0.0),
                genres=genres,
                keywords=keywords,
                cast=cast,
                crew=crew_ids
            )
            
            db.add(new_cache)
            db.commit()
            db.refresh(new_cache)
            
            logger.info(f"Successfully cached movie {movie_id}: {new_cache.title}")
            return new_cache
            
        except Exception as e:
            logger.error(f"Error fetching/caching movie {movie_id}: {str(e)}")
            db.rollback()
            return None

    @staticmethod
    def create_feature_vector(movie: MovieCache) -> np.ndarray:
        """
        Create numerical feature vector from movie attributes
        
        Feature Vector Structure:
        [genre_1, genre_2, ..., genre_5,      # 5 genre slots
         keyword_1, ..., keyword_10,           # 10 keyword slots
         cast_1, ..., cast_5,                  # 5 cast slots
         crew_1, crew_2, crew_3]               # 3 crew slots
        Total: 23 dimensions
        
        Padding/Truncation:
        - If movie has fewer features, pad with 0s
        - If movie has more features, truncate to limit
        
        Args:
            movie: MovieCache object
            
        Returns:
            numpy array of shape (23,)
        """
        features = []

        # Genres (pad or truncate to GENRE_DIM)
        genre_features = (movie.genres or [])[:RecommendationService.GENRE_DIM]
        genre_features += [0] * (RecommendationService.GENRE_DIM - len(genre_features))
        features.extend(genre_features)

        # Keywords (pad or truncate to KEYWORD_DIM)
        keyword_features = (movie.keywords or [])[:RecommendationService.KEYWORD_DIM]
        keyword_features += [0] * (RecommendationService.KEYWORD_DIM - len(keyword_features))
        features.extend(keyword_features)

        # Cast (pad or truncate to CAST_DIM)
        cast_features = (movie.cast or [])[:RecommendationService.CAST_DIM]
        cast_features += [0] * (RecommendationService.CAST_DIM - len(cast_features))
        features.extend(cast_features)

        # Crew (pad or truncate to CREW_DIM)
        crew_features = (movie.crew or [])[:RecommendationService.CREW_DIM]
        crew_features += [0] * (RecommendationService.CREW_DIM - len(crew_features))
        features.extend(crew_features)

        return np.array(features, dtype=float)

    @staticmethod
    def calculate_similarity_score(movie1: MovieCache, movie2: MovieCache) -> float:
        """
        Calculate weighted similarity score between two movies
        
        Uses multiple factors:
        - Genre overlap (40% weight)
        - Keyword similarity (30% weight)
        - Cast overlap (20% weight)
        - Crew overlap (10% weight)
        
        Args:
            movie1, movie2: Movies to compare
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        score = 0.0
        
        # Genre similarity
        genres1 = set(movie1.genres or [])
        genres2 = set(movie2.genres or [])
        if genres1 and genres2:
            genre_similarity = len(genres1 & genres2) / len(genres1 | genres2)
            score += genre_similarity * RecommendationService.GENRE_WEIGHT
        
        # Keyword similarity
        keywords1 = set(movie1.keywords or [])
        keywords2 = set(movie2.keywords or [])
        if keywords1 and keywords2:
            keyword_similarity = len(keywords1 & keywords2) / len(keywords1 | keywords2)
            score += keyword_similarity * RecommendationService.KEYWORD_WEIGHT
        
        # Cast similarity
        cast1 = set(movie1.cast or [])
        cast2 = set(movie2.cast or [])
        if cast1 and cast2:
            cast_similarity = len(cast1 & cast2) / len(cast1 | cast2)
            score += cast_similarity * RecommendationService.CAST_WEIGHT
        
        # Crew similarity
        crew1 = set(movie1.crew or [])
        crew2 = set(movie2.crew or [])
        if crew1 and crew2:
            crew_similarity = len(crew1 & crew2) / len(crew1 | crew2)
            score += crew_similarity * RecommendationService.CREW_WEIGHT
        
        return score

    @staticmethod
    def get_similar_movies(
        db: Session, 
        movie_id: int, 
        limit: int = DEFAULT_LIMIT,
        use_knn: bool = True
    ) -> List[Dict]:
        """
        Main recommendation method - get similar movies
        
        Algorithm:
        1. Fetch/cache target movie
        2. Check if enough cached movies exist for KNN
        3. If yes, use KNN algorithm
        4. If no, fall back to genre-based recommendations
        
        Args:
            db: Database session
            movie_id: Target movie TMDB ID
            limit: Number of recommendations to return
            use_knn: Whether to use KNN (True) or simple genre matching (False)
            
        Returns:
            List of dicts with movie info and similarity scores
        """
        # Fetch and cache target movie
        target_movie = RecommendationService.fetch_and_cache_movie(db, movie_id)
        if not target_movie:
            logger.error(f"Could not fetch movie {movie_id}")
            return []

        # Get all cached movies (excluding target)
        all_movies = db.query(MovieCache).filter(
            MovieCache.tmdb_id != movie_id
        ).all()

        # Check if we have enough data for KNN
        if len(all_movies) < RecommendationService.MIN_CACHE_SIZE or not use_knn:
            logger.info(f"Using genre-based recommendations (cache size: {len(all_movies)})")
            return RecommendationService.get_similar_by_genre(db, movie_id, limit)

        # Use KNN algorithm for better recommendations
        logger.info(f"Using KNN recommendations with {len(all_movies)} cached movies")
        
        # Create feature vectors for all movies
        target_vector = RecommendationService.create_feature_vector(target_movie).reshape(1, -1)
        movie_vectors = np.array([
            RecommendationService.create_feature_vector(m) for m in all_movies
        ])

        # Apply KNN algorithm
        # n_neighbors: find k+1 nearest (we'll exclude the target itself if present)
        n_neighbors = min(limit + 1, len(all_movies))
        knn = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
        knn.fit(movie_vectors)

        # Find nearest neighbors
        distances, indices = knn.kneighbors(target_vector)

        # Build results with similarity scores
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            movie = all_movies[idx]
            similarity = 1 - distance  # Convert distance to similarity (0 to 1)
            
            results.append({
                'tmdb_id': movie.tmdb_id,
                'title': movie.title,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'vote_average': movie.vote_average,
                'popularity': movie.popularity,
                'release_date': movie.release_date,
                'overview': movie.overview,
                'genres': movie.genres,
                'similarity_score': round(float(similarity), 3)
            })

        # Sort by similarity score (descending)
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return results[:limit]

    @staticmethod
    def get_similar_by_genre(
        db: Session, 
        movie_id: int, 
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """
        Fallback recommendation method using only genre matching
        
        Process:
        1. Get target movie's genres
        2. Find all movies sharing at least one genre
        3. Calculate genre overlap score
        4. Boost score with vote_average and popularity
        5. Return top N results
        
        Args:
            db: Database session
            movie_id: Target movie TMDB ID
            limit: Number of recommendations
            
        Returns:
            List of similar movies sorted by score
        """
        target_movie = db.query(MovieCache).filter(
            MovieCache.tmdb_id == movie_id
        ).first()

        if not target_movie or not target_movie.genres:
            logger.warning(f"Movie {movie_id} has no genres for matching")
            return []

        target_genres = set(target_movie.genres)

        # Find movies with genre overlap
        candidate_movies = db.query(MovieCache).filter(
            MovieCache.tmdb_id != movie_id,
            MovieCache.genres.isnot(None)
        ).all()

        scored_movies = []
        for movie in candidate_movies:
            movie_genres = set(movie.genres or [])
            
            # Calculate genre overlap
            if not movie_genres:
                continue
                
            overlap = len(target_genres & movie_genres)
            if overlap == 0:
                continue
            
            # Jaccard similarity for genres
            genre_similarity = overlap / len(target_genres | movie_genres)
            
            # Composite score: genre similarity + quality boost
            score = genre_similarity * 0.7 + (movie.vote_average / 10) * 0.2 + (min(movie.popularity, 100) / 100) * 0.1
            
            scored_movies.append({
                'tmdb_id': movie.tmdb_id,
                'title': movie.title,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'vote_average': movie.vote_average,
                'popularity': movie.popularity,
                'release_date': movie.release_date,
                'overview': movie.overview,
                'genres': movie.genres,
                'similarity_score': round(score, 3),
                'genre_overlap': overlap
            })

        # Sort by score
        scored_movies.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return scored_movies[:limit]

    @staticmethod
    def get_recommendations_by_genre_ids(
        db: Session,
        genre_ids: List[int],
        limit: int = DEFAULT_LIMIT,
        min_vote_average: float = 6.0
    ) -> List[Dict]:
        """
        Get movie recommendations based on genre IDs
        
        Use case: User browses by genre
        
        Args:
            db: Database session
            genre_ids: List of genre IDs to match
            limit: Number of results
            min_vote_average: Minimum rating filter
            
        Returns:
            List of movies matching genres, sorted by popularity
        """
        if not genre_ids:
            return []

        target_genres = set(genre_ids)

        # Find movies with matching genres
        movies = db.query(MovieCache).filter(
            MovieCache.genres.isnot(None),
            MovieCache.vote_average >= min_vote_average
        ).all()

        scored_movies = []
        for movie in movies:
            movie_genres = set(movie.genres or [])
            overlap = len(target_genres & movie_genres)
            
            if overlap == 0:
                continue
            
            # Score based on genre match and quality
            genre_score = overlap / len(target_genres)
            quality_score = (movie.vote_average / 10) * 0.5 + (min(movie.popularity, 100) / 100) * 0.5
            final_score = genre_score * 0.6 + quality_score * 0.4
            
            scored_movies.append({
                'tmdb_id': movie.tmdb_id,
                'title': movie.title,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'vote_average': movie.vote_average,
                'popularity': movie.popularity,
                'release_date': movie.release_date,
                'overview': movie.overview,
                'genres': movie.genres,
                'similarity_score': round(final_score, 3),
                'genre_matches': overlap
            })

        scored_movies.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored_movies[:limit]

    @staticmethod
    def populate_cache_from_popular(
        db: Session,
        pages: int = 5
    ) -> Dict[str, any]:
        """
        Populate cache with popular movies from TMDB
        
        This bootstraps the recommendation engine with data
        Should be run once during setup or periodically
        
        Args:
            db: Database session
            pages: Number of pages to fetch (20 movies per page)
            
        Returns:
            Dict with success/failure counts
        """
        logger.info(f"Populating cache with {pages} pages of popular movies...")
        
        success_count = 0
        error_count = 0
        skipped_count = 0

        for page in range(1, pages + 1):
            try:
                popular_data = TMDBService.get_popular(page)
                movies = popular_data.get('results', [])
                
                for movie in movies:
                    movie_id = movie['id']
                    
                    # Check if already cached
                    existing = db.query(MovieCache).filter(
                        MovieCache.tmdb_id == movie_id
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Fetch and cache
                    cached = RecommendationService.fetch_and_cache_movie(db, movie_id)
                    if cached:
                        success_count += 1
                    else:
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"Error fetching page {page}: {str(e)}")
                error_count += 20  # Approximate
                
        result = {
            'success': success_count,
            'errors': error_count,
            'skipped': skipped_count,
            'total_cached': db.query(MovieCache).count()
        }
        
        logger.info(f"Cache population complete: {result}")
        return result
