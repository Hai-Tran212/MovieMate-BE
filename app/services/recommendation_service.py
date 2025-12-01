"""
Recommendation Service - Content-Based & Hybrid Filtering Engine
Uses KNN algorithm, cosine similarity, and collaborative filtering for movie recommendations
"""
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.movie_cache import MovieCache
from app.models.rating import Rating
from app.services.tmdb_service import TMDBService
from datetime import datetime, timedelta
import logging
import zlib
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Hybrid recommendation engine combining:
    - Content-based filtering (KNN, cosine similarity)
    - Collaborative filtering (user-based)
    - Genre, cast, crew, and keyword analysis
    """

    FEATURE_VECTOR_CACHE: Dict[int, np.ndarray] = {}
    MOOD_BASE_CACHE: Dict[str, Dict[str, Any]] = {}
    MOOD_CACHE_TTL_SECONDS = 900
    
    # Configuration constants (easy to modify)
    CACHE_EXPIRY_DAYS = 7           # Refresh cached data after 7 days
    MIN_CACHE_SIZE = 30             # Minimum movies needed for KNN (reduced for production)
    DEFAULT_LIMIT = 20              # Default number of recommendations
    
    # Feature vector hashed bucket dimensions
    GENRE_BUCKETS = 32
    KEYWORD_BUCKETS = 96
    CAST_BUCKETS = 96
    CREW_BUCKETS = 32
    FEATURE_VECTOR_SIZE = GENRE_BUCKETS + KEYWORD_BUCKETS + CAST_BUCKETS + CREW_BUCKETS
    
    # Weights for similarity calculation (can be tuned)
    GENRE_WEIGHT = 0.4
    KEYWORD_WEIGHT = 0.3
    CAST_WEIGHT = 0.2
    CREW_WEIGHT = 0.1

    # Similar-movie specific thresholds (for KNN pre-filtering)
    SIMILAR_MIN_RATING = 5.5
    SIMILAR_MAX_CANDIDATES = 1000
    
    # Hybrid recommendation weights (easy to tune)
    HYBRID_CONTENT_WEIGHT = 0.7      # 70% content-based
    HYBRID_COLLABORATIVE_WEIGHT = 0.3 # 30% collaborative
    HYBRID_MIN_CONTENT_SCORE = 0.3   # Minimum content score to consider
    HYBRID_MIN_COLLAB_SCORE = 0.3    # Minimum collaborative score to consider
    
    # Mood-based recommendation mappings
    # Updated with better genre combinations and exclusions
    MOOD_TO_GENRES = {
        'happy': {
            'include': [35, 10751, 16, 10402],      # Comedy, Family, Animation, Music
            'exclude': [27, 53, 80],                 # Exclude Horror, Thriller, Crime
            'keywords_boost': ['feel-good', 'friendship', 'hope', 'celebration', 'fun', 'comedy'],
            'keywords_penalty': ['dark', 'death', 'murder', 'violence', 'tragedy']
        },
        'sad': {
            'include': [18, 10749],                  # Drama, Romance
            'exclude': [35, 28, 27],                 # Exclude Comedy, Action, Horror
            'keywords_boost': ['loss', 'tragedy', 'emotional', 'tear-jerker', 'heartbreak', 'melancholy'],
            'keywords_penalty': ['comedy', 'action', 'superhero', 'adventure']
        },
        'excited': {
            'include': [28, 12, 878, 14],            # Action, Adventure, Sci-Fi, Fantasy
            'exclude': [10749, 99],                  # Exclude Romance, Documentary
            'keywords_boost': ['action', 'adventure', 'epic', 'battle', 'superhero', 'chase', 'explosion'],
            'keywords_penalty': ['slow-paced', 'romantic', 'quiet', 'documentary']
        },
        'relaxed': {
            'include': [35, 10751, 16],              # Comedy, Family, Animation
            'exclude': [27, 53, 10752],              # Exclude Horror, Thriller, War
            'keywords_boost': ['light-hearted', 'easy-watching', 'feel-good', 'gentle', 'peaceful'],
            'keywords_penalty': ['intense', 'dark', 'violent', 'disturbing']
        },
        'scared': {
            'include': [27, 53],                     # Horror, Thriller
            'exclude': [35, 10751, 16],              # Exclude Comedy, Family, Animation
            'keywords_boost': ['horror', 'suspense', 'terror', 'scary', 'psychological', 'thriller'],
            'keywords_penalty': ['comedy', 'family-friendly', 'light-hearted']
        },
        'thoughtful': {
            'include': [18, 9648, 36, 99, 878],     # Drama, Mystery, History, Documentary, Sci-Fi
            'exclude': [35, 27],                     # Exclude Comedy, Horror
            'keywords_boost': ['thought-provoking', 'philosophical', 'complex', 'intelligent', 'mystery'],
            'keywords_penalty': ['mindless', 'simple', 'comedy', 'slasher']
        },
        'romantic': {
            'include': [10749, 35, 18],              # Romance, Comedy, Drama
            'exclude': [27, 28, 10752],              # Exclude Horror, Action, War
            'keywords_boost': ['romance', 'love', 'relationship', 'heartwarming', 'couple'],
            'keywords_penalty': ['horror', 'violence', 'war', 'action-packed']
        }
    }
    
    MOOD_RUNTIME_PREFS = {
        'happy': (80, 120),
        'sad': (90, 150),
        'excited': (90, 150),
        'relaxed': (80, 110),
        'scared': (80, 120),
        'thoughtful': (100, 180),
        'romantic': (90, 130)
    }
    
    # Minimum vote count for mood recommendations (avoid obscure/low-quality films)
    MOOD_MIN_VOTE_COUNT = 100
    MOOD_MIN_RATING = 6.0
    # Hard cap on number of candidate movies per mood query (for performance)
    MOOD_MAX_CANDIDATES = 800

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
            keyword_items = keywords_data.get('keywords', []) if isinstance(keywords_data, dict) else []
            # Top 20 keyword IDs and names (lowercased)
            keywords = [k.get('id') for k in keyword_items[:20] if isinstance(k, dict) and 'id' in k]
            keyword_names = [
                str(k.get('name', '')).lower()
                for k in keyword_items[:20]
                if isinstance(k, dict) and k.get('name')
            ]
            
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
                keyword_names=keyword_names,
                cast=cast,
                crew=crew_ids
            )
            
            db.add(new_cache)
            db.commit()
            db.refresh(new_cache)

            # Invalidate feature vector cache for this movie
            RecommendationService.FEATURE_VECTOR_CACHE.pop(movie_id, None)
            
            logger.info(f"Successfully cached movie {movie_id}: {new_cache.title}")
            return new_cache
            
        except HTTPException as http_err:
            logger.warning(f"TMDB fetch failed for movie {movie_id}: {http_err.detail}")
            db.rollback()
            return None
        except Exception as e:
            logger.error(f"Error fetching/caching movie {movie_id}: {str(e)}")
            db.rollback()
            return None

    @staticmethod
    def _stable_hash(value: Any) -> int:
        """Create a deterministic hash for any value."""
        if value is None:
            value = ""
        return zlib.crc32(str(value).encode("utf-8"))

    @staticmethod
    def _encode_sparse_feature(
        vector: np.ndarray,
        values: Optional[List[Any]],
        bucket_count: int,
        offset: int,
        weight: float
    ) -> None:
        """Project arbitrary IDs into a fixed-size bucketed representation."""
        if not values:
            return

        normalized_values = []
        for val in values:
            if val is None:
                continue
            normalized_values.append(val if isinstance(val, str) else str(val))

        if not normalized_values:
            return

        unique_values = list(dict.fromkeys(normalized_values))
        norm = weight / len(unique_values)

        for val in unique_values:
            bucket = RecommendationService._stable_hash(val) % bucket_count
            vector[offset + bucket] += norm

    @staticmethod
    def create_feature_vector(movie: MovieCache) -> np.ndarray:
        """
        Create numerical feature vector from movie attributes using hashed multi-hot encoding.

        Each attribute family (genres / keywords / cast / crew) is projected into a fixed number
        of buckets so vector size remains constant while still capturing set overlap semantics.
        """
        vector = np.zeros(RecommendationService.FEATURE_VECTOR_SIZE, dtype=float)
        offset = 0

        RecommendationService._encode_sparse_feature(
            vector=vector,
            values=movie.genres if isinstance(movie.genres, list) else [],
            bucket_count=RecommendationService.GENRE_BUCKETS,
            offset=offset,
            weight=RecommendationService.GENRE_WEIGHT
        )
        offset += RecommendationService.GENRE_BUCKETS

        keyword_source = None
        if isinstance(movie.keyword_names, list) and movie.keyword_names:
            keyword_source = movie.keyword_names
        elif isinstance(movie.keywords, list):
            keyword_source = movie.keywords

        RecommendationService._encode_sparse_feature(
            vector=vector,
            values=keyword_source,
            bucket_count=RecommendationService.KEYWORD_BUCKETS,
            offset=offset,
            weight=RecommendationService.KEYWORD_WEIGHT
        )
        offset += RecommendationService.KEYWORD_BUCKETS

        RecommendationService._encode_sparse_feature(
            vector=vector,
            values=movie.cast if isinstance(movie.cast, list) else [],
            bucket_count=RecommendationService.CAST_BUCKETS,
            offset=offset,
            weight=RecommendationService.CAST_WEIGHT
        )
        offset += RecommendationService.CAST_BUCKETS

        RecommendationService._encode_sparse_feature(
            vector=vector,
            values=movie.crew if isinstance(movie.crew, list) else [],
            bucket_count=RecommendationService.CREW_BUCKETS,
            offset=offset,
            weight=RecommendationService.CREW_WEIGHT
        )

        return vector

    @staticmethod
    def _get_feature_vector(movie: MovieCache) -> np.ndarray:
        cached = RecommendationService.FEATURE_VECTOR_CACHE.get(movie.tmdb_id)
        if cached is not None:
            return cached
        vector = RecommendationService.create_feature_vector(movie)
        RecommendationService.FEATURE_VECTOR_CACHE[movie.tmdb_id] = vector
        return vector

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
        # Note: These fields are JSON columns that return lists when queried
        genres1 = set(movie1.genres if isinstance(movie1.genres, list) else [])
        genres2 = set(movie2.genres if isinstance(movie2.genres, list) else [])
        if genres1 and genres2:
            genre_similarity = len(genres1 & genres2) / len(genres1 | genres2)
            score += genre_similarity * RecommendationService.GENRE_WEIGHT
        
        # Keyword similarity
        keywords1 = set(movie1.keywords if isinstance(movie1.keywords, list) else [])
        keywords2 = set(movie2.keywords if isinstance(movie2.keywords, list) else [])
        if keywords1 and keywords2:
            keyword_similarity = len(keywords1 & keywords2) / len(keywords1 | keywords2)
            score += keyword_similarity * RecommendationService.KEYWORD_WEIGHT
        
        # Cast similarity
        cast1 = set(movie1.cast if isinstance(movie1.cast, list) else [])
        cast2 = set(movie2.cast if isinstance(movie2.cast, list) else [])
        if cast1 and cast2:
            cast_similarity = len(cast1 & cast2) / len(cast1 | cast2)
            score += cast_similarity * RecommendationService.CAST_WEIGHT
        
        # Crew similarity
        crew1 = set(movie1.crew if isinstance(movie1.crew, list) else [])
        crew2 = set(movie2.crew if isinstance(movie2.crew, list) else [])
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

        # Ensure target movie has genres for similarity
        target_genres_raw = target_movie.genres if isinstance(target_movie.genres, list) else None
        if not target_genres_raw:
            logger.warning(f"Movie {movie_id} has no genres; falling back to genre-based recommendations")
            return RecommendationService.get_similar_by_genre(db, movie_id, limit)

        target_genres = set(target_genres_raw)

        # Pre-filter candidate movies in SQL for performance:
        # - Exclude target movie
        # - Require non-null genres
        # - Require minimum rating
        # - Prioritize popular movies and cap total candidates
        base_query = db.query(MovieCache).filter(
            MovieCache.tmdb_id != movie_id,
            MovieCache.genres.isnot(None),
            MovieCache.vote_average >= RecommendationService.SIMILAR_MIN_RATING
        ).order_by(MovieCache.popularity.desc())

        candidates = base_query.limit(RecommendationService.SIMILAR_MAX_CANDIDATES).all()

        # Further filter in Python: require at least one shared genre with target
        all_movies = []
        for movie in candidates:
            movie_genres_raw = movie.genres if isinstance(movie.genres, list) else []
            if not movie_genres_raw:
                continue
            movie_genres = set(movie_genres_raw)
            if not movie_genres.intersection(target_genres):
                continue
            all_movies.append(movie)

        # Check if we have enough data for KNN
        if len(all_movies) < RecommendationService.MIN_CACHE_SIZE or not use_knn:
            logger.info(f"Using genre-based recommendations (candidate size: {len(all_movies)})")
            return RecommendationService.get_similar_by_genre(db, movie_id, limit)

        # Use KNN algorithm for better recommendations
        logger.info(f"Using KNN recommendations with {len(all_movies)} cached movies")
        
        # Create feature vectors for all movies
        target_vector = RecommendationService._get_feature_vector(target_movie).reshape(1, -1)
        movie_vectors = np.array([
            RecommendationService._get_feature_vector(m) for m in all_movies
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
                'tmdb_id': movie.tmdb_id,  # type: ignore
                'title': movie.title,  # type: ignore
                'poster_path': movie.poster_path,  # type: ignore
                'backdrop_path': movie.backdrop_path,  # type: ignore
                'vote_average': movie.vote_average,  # type: ignore
                'popularity': movie.popularity,  # type: ignore
                'release_date': movie.release_date,  # type: ignore
                'overview': movie.overview,  # type: ignore
                'genres': movie.genres if isinstance(movie.genres, list) else [],  # type: ignore
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

        # Check target movie exists and has genres
        target_genres_raw = target_movie.genres if target_movie else None
        if not target_movie or target_genres_raw is None or not isinstance(target_genres_raw, list):
            logger.warning(f"Movie {movie_id} has no genres for matching")
            return []

        target_genres = set(target_genres_raw)

        # Find movies with genre overlap
        candidate_movies = db.query(MovieCache).filter(
            MovieCache.tmdb_id != movie_id,
            MovieCache.genres.isnot(None)
        ).all()

        scored_movies = []
        for movie in candidate_movies:
            # Safe extraction of genres from JSON column
            movie_genres_raw = movie.genres if isinstance(movie.genres, list) else []
            movie_genres = set(movie_genres_raw)
            
            # Calculate genre overlap
            if not movie_genres:
                continue
                
            overlap = len(target_genres & movie_genres)
            if overlap == 0:
                continue
            
            # Jaccard similarity for genres
            genre_similarity = overlap / len(target_genres | movie_genres)
            
            # Composite score: genre similarity + quality boost
            vote_avg = float(movie.vote_average) if movie.vote_average is not None else 0.0  # type: ignore
            popularity = float(movie.popularity) if movie.popularity is not None else 0.0  # type: ignore
            score = genre_similarity * 0.7 + (vote_avg / 10) * 0.2 + (min(popularity, 100) / 100) * 0.1
            
            scored_movies.append({
                'tmdb_id': movie.tmdb_id,  # type: ignore
                'title': movie.title,  # type: ignore
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'vote_average': vote_avg,
                'popularity': popularity,
                'release_date': movie.release_date,
                'overview': movie.overview,
                'genres': movie_genres_raw,
                'similarity_score': round(float(score), 3),
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
            movie_genres_raw = movie.genres if isinstance(movie.genres, list) else []  # type: ignore
            movie_genres = set(movie_genres_raw)
            overlap = len(target_genres & movie_genres)
            
            if overlap == 0:
                continue
            
            # Score based on genre match and quality
            vote_avg = float(movie.vote_average) if movie.vote_average is not None else 0.0  # type: ignore
            popularity = float(movie.popularity) if movie.popularity is not None else 0.0  # type: ignore
            
            genre_score = overlap / len(target_genres)
            quality_score = (vote_avg / 10) * 0.5 + (min(popularity, 100) / 100) * 0.5
            final_score = genre_score * 0.6 + quality_score * 0.4
            
            scored_movies.append({
                'tmdb_id': movie.tmdb_id,  # type: ignore
                'title': movie.title,  # type: ignore
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'vote_average': vote_avg,
                'popularity': popularity,
                'release_date': movie.release_date,
                'overview': movie.overview,
                'genres': movie_genres_raw,
                'similarity_score': round(float(final_score), 3),
                'genre_matches': overlap
            })

        scored_movies.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored_movies[:limit]

    @staticmethod
    def populate_cache_from_popular(
        db: Session,
        pages: int = 5
    ) -> Dict[str, Any]:
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
    
    @staticmethod
    def get_mood_based_recommendations(
        db: Session,
        user_id: int,
        mood: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get recommendations based on user's current mood
        
        Args:
            db: Database session
            user_id: User ID for personalization
            mood: One of: happy, sad, excited, relaxed, scared, thoughtful, romantic
            limit: Number of recommendations to return
            
        Returns:
            List of recommended movies with mood scores
        """
        mood = mood.lower()
        
        if mood not in RecommendationService.MOOD_TO_GENRES:
            raise ValueError(f"Invalid mood. Choose from: {list(RecommendationService.MOOD_TO_GENRES.keys())}")
        
        # Get mood configuration
        mood_config = RecommendationService.MOOD_TO_GENRES[mood]
        preferred_genres = mood_config['include']
        excluded_genres = mood_config.get('exclude', [])
        boost_keywords = mood_config.get('keywords_boost', [])
        penalty_keywords = mood_config.get('keywords_penalty', [])
        runtime_range = RecommendationService.MOOD_RUNTIME_PREFS.get(mood, (80, 150))
        
        # Get user's rating history to personalize
        from app.models.rating import Rating
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        
        # Calculate user's average rating for personalization
        user_avg_rating: float = 7.0  # Default
        rated_movie_ids = set()
        
        if user_ratings:
            # Safely extract numeric ratings (handle possible Column/InstrumentedAttribute types)
            rating_values = [
                float(getattr(r, 'rating')) for r in user_ratings
                if getattr(r, 'rating', None) is not None
            ]
            if rating_values:
                user_avg_rating = sum(rating_values) / len(rating_values)
            rated_movie_ids = {getattr(r, 'movie_id') for r in user_ratings}
        
        # Dynamic minimum rating per mood (slightly stricter for some moods)
        min_rating_for_mood = RecommendationService.MOOD_MIN_RATING
        if mood in ('sad', 'thoughtful', 'romantic'):
            min_rating_for_mood += 0.5
        
        query = db.query(MovieCache).filter(
            MovieCache.vote_average >= min_rating_for_mood,
            MovieCache.genres.isnot(None)
        ).order_by(MovieCache.popularity.desc())

        candidate_movies = query.limit(RecommendationService.MOOD_MAX_CANDIDATES).all()

        if not candidate_movies:
            logger.warning("No movies in cache for mood recommendations")
            return []

        candidate_signature = tuple(sorted(movie.tmdb_id for movie in candidate_movies))

        base_scores = RecommendationService._get_mood_base_scores(
            mood=mood,
            candidate_movies=candidate_movies,
            preferred_genres=set(preferred_genres),
            excluded_genres_set=set(excluded_genres),
            boost_keywords=boost_keywords,
            penalty_keywords=penalty_keywords,
            candidate_signature=candidate_signature
        )

        scored_movies = []
        for base_movie in base_scores:
            if base_movie['tmdb_id'] in rated_movie_ids:
                continue

            movie_entry = base_movie.copy()

            if user_ratings and isinstance(movie_entry.get('vote_average'), (int, float)):
                rating_diff = abs(float(movie_entry['vote_average']) - user_avg_rating)
                personalized_score = movie_entry['mood_score']
                if rating_diff < 1.5:
                    personalized_score *= 1.3
                elif rating_diff > 3.0:
                    personalized_score *= 0.8
                movie_entry['mood_score'] = round(float(personalized_score), 3)

            scored_movies.append(movie_entry)

        scored_movies.sort(key=lambda x: x['mood_score'], reverse=True)
        
        # Add diversity - don't return all from same year/genre combination
        diverse_results = []
        seen_years = set()
        seen_primary_genres = set()
        
        for movie in scored_movies:
            if len(diverse_results) >= limit:
                break
            
            # Extract year from release_date
            year = movie['release_date'][:4] if movie['release_date'] else 'unknown'
            
            # Get primary genre (first in list)
            primary_genre = movie['genres'][0] if movie['genres'] else None
            
            # Diversity check: limit movies from same year + same primary genre
            year_genre_combo = f"{year}_{primary_genre}"
            
            # Allow max 2 movies with same year+genre combo
            if diverse_results:
                same_combo_count = sum(1 for m in diverse_results 
                                      if (m['release_date'][:4] if m['release_date'] else 'unknown') == year 
                                      and (m['genres'][0] if m['genres'] else None) == primary_genre)
                
                if same_combo_count >= 2:
                    continue
            
            diverse_results.append(movie)
        
        # Fallback: If not enough recommendations, lower thresholds and add more
        if len(diverse_results) < limit:
            logger.info(f"Mood results insufficient ({len(diverse_results)}), adding fallback movies")
            
            # Get IDs already in results
            existing_ids = {m['tmdb_id'] for m in diverse_results}
            
            # Try with lower minimum rating (reduce by 0.5)
            fallback_query = db.query(MovieCache).filter(
                MovieCache.vote_average >= max(5.5, min_rating_for_mood - 0.5),
                MovieCache.genres.isnot(None),
                ~MovieCache.tmdb_id.in_(rated_movie_ids | existing_ids)
            ).order_by(MovieCache.popularity.desc())
            
            fallback_movies = fallback_query.limit(limit * 2).all()
            
            for movie in fallback_movies:
                if len(diverse_results) >= limit:
                    break
                
                movie_genres = set(movie.genres) if isinstance(movie.genres, list) else set()
                
                # Check if at least one genre matches mood
                if not movie_genres.intersection(preferred_genres):
                    continue
                
                # Skip excluded genres
                if movie_genres.intersection(set(excluded_genres)):
                    continue
                
                diverse_results.append({
                    "tmdb_id": movie.tmdb_id,
                    "title": movie.title,
                    "poster_path": movie.poster_path,
                    "backdrop_path": movie.backdrop_path,
                    "vote_average": movie.vote_average,
                    "popularity": movie.popularity,
                    "release_date": movie.release_date,
                    "overview": movie.overview,
                    "genres": movie.genres,
                    "mood_score": 0.5,  # Lower score for fallback
                    "genre_overlap": len(movie_genres.intersection(preferred_genres)),
                })
        
        logger.info(f"Mood recommendations for '{mood}': {len(diverse_results)} movies")
        return diverse_results

    @staticmethod
    def _get_mood_base_scores(
        mood: str,
        candidate_movies: List[MovieCache],
        preferred_genres: set,
        excluded_genres_set: set,
        boost_keywords: List[str],
        penalty_keywords: List[str],
        candidate_signature: Tuple[int, ...]
    ) -> List[Dict]:
        cache_entry = RecommendationService.MOOD_BASE_CACHE.get(mood)
        now = datetime.now()

        if (
            cache_entry
            and cache_entry.get("signature") == candidate_signature
            and (now - cache_entry.get("timestamp", now)) < timedelta(seconds=RecommendationService.MOOD_CACHE_TTL_SECONDS)
        ):
            return cache_entry["data"]

        scored_movies: List[Dict] = []

        for movie in candidate_movies:
            rating_value = getattr(movie, "vote_average", 0)
            if isinstance(rating_value, (int, float)) and float(rating_value) < RecommendationService.MOOD_MIN_RATING:
                continue

            genres_value = getattr(movie, "genres", None)
            if not isinstance(genres_value, (list, tuple)) or not genres_value:
                continue

            movie_genres = set(genres_value)
            if mood == "romantic" and 10749 not in movie_genres:
                continue
            if movie_genres.intersection(excluded_genres_set):
                continue

            genre_overlap = len(movie_genres.intersection(preferred_genres))
            if genre_overlap == 0:
                continue

            genre_score = genre_overlap / len(preferred_genres)

            keyword_boost = 1.0
            keywords_value = getattr(movie, "keyword_names", None) or getattr(movie, "keywords", None)

            if isinstance(keywords_value, (list, tuple)):
                movie_keywords_lower = [str(k).lower() for k in keywords_value]

                for boost_kw in boost_keywords:
                    if any(boost_kw.lower() in mk for mk in movie_keywords_lower):
                        keyword_boost += 0.3

                for penalty_kw in penalty_keywords:
                    if any(penalty_kw.lower() in mk for mk in movie_keywords_lower):
                        keyword_boost -= 0.4

                keyword_boost = max(0.1, keyword_boost)

            rating_boost = 1 + (float(rating_value) / 10.0) if isinstance(rating_value, (int, float)) else 1.0

            popularity_value = getattr(movie, "popularity", None)
            popularity_boost = 1 + (float(popularity_value) / 1000.0 * 0.2) if isinstance(popularity_value, (int, float)) else 1.0

            base_score = genre_score * keyword_boost * rating_boost * popularity_boost

            scored_movies.append(
                {
                    "tmdb_id": movie.tmdb_id,
                    "title": movie.title,
                    "poster_path": movie.poster_path,
                    "backdrop_path": movie.backdrop_path,
                    "vote_average": movie.vote_average,
                    "popularity": movie.popularity,
                    "release_date": movie.release_date,
                    "overview": movie.overview,
                    "genres": movie.genres,
                    "mood_score": round(float(base_score), 3),
                    "genre_overlap": genre_overlap,
                }
            )

        scored_movies.sort(key=lambda x: x["mood_score"], reverse=True)

        RecommendationService.MOOD_BASE_CACHE[mood] = {
            "timestamp": now,
            "signature": candidate_signature,
            "data": scored_movies,
        }

        return scored_movies

    # ==================== HYBRID RECOMMENDATION METHODS ====================
    
    @staticmethod
    def get_hybrid_recommendations(
        db: Session,
        user_id: int,
        movie_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get hybrid recommendations combining content-based and collaborative filtering
        
        Algorithm:
        - 70% content-based (similar movies or user preferences)
        - 30% collaborative filtering (similar users' ratings)
        - Normalized scores combined with configurable weights
        
        Args:
            db: Database session
            user_id: Target user ID for personalization
            movie_id: Optional movie ID for similarity-based recommendations
            limit: Number of recommendations to return
            
        Returns:
            List of recommended movies with hybrid scores
        """
        try:
            from app.services.collaborative_service import CollaborativeService
            
            content_weight = RecommendationService.HYBRID_CONTENT_WEIGHT
            collaborative_weight = RecommendationService.HYBRID_COLLABORATIVE_WEIGHT
            
            # Step 1: Get content-based recommendations
            content_recs = []
            if movie_id:
                # Use similar movies if movie_id provided
                content_recs = RecommendationService.get_similar_movies(
                    db=db, 
                    movie_id=movie_id, 
                    limit=limit * 2,
                    use_knn=True
                )
            else:
                # Use user's rating history for content-based
                user_ratings = db.query(Rating).filter(
                    Rating.user_id == user_id
                ).order_by(Rating.rating.desc()).limit(10).all()
                
                if user_ratings:
                    # Get recommendations based on highly rated movies (lowered threshold for more results)
                    high_rated = [r for r in user_ratings if r.rating >= 7.0]
                    if not high_rated and user_ratings:
                        # If no movies rated >= 7.0, use top 3 highest rated movies
                        high_rated = sorted(user_ratings, key=lambda r: r.rating, reverse=True)[:3]
                    
                    if high_rated:
                        # Use best rated movie for content similarity
                        content_recs = RecommendationService.get_similar_movies(
                            db=db,
                            movie_id=high_rated[0].movie_id,
                            limit=limit * 2,
                            use_knn=True
                        )
                
                # Fallback to popular movies if no user history
                if not content_recs:
                    popular_movies = db.query(MovieCache).filter(
                        MovieCache.vote_average >= 7.0,
                        MovieCache.vote_count >= 100
                    ).order_by(
                        MovieCache.popularity.desc()
                    ).limit(limit * 2).all()
                    
                    content_recs = [{
                        'id': m.id,
                        'tmdb_id': m.tmdb_id,
                        'title': m.title,
                        'similarity_score': 1.0,  # Default score
                        'vote_average': float(m.vote_average) if m.vote_average else 0.0,
                        'genres': m.genres or [],
                        'release_date': m.release_date.isoformat() if m.release_date else None,
                        'poster_path': m.poster_path,
                        'overview': m.overview
                    } for m in popular_movies]
            
            # Step 2: Get collaborative filtering recommendations
            collab_recs = CollaborativeService.get_collaborative_recommendations(
                db=db,
                user_id=user_id,
                limit=limit * 2
            )
            
            # Step 3: Normalize scores to 0-1 range
            # Normalize content scores
            if content_recs:
                max_content = max(
                    r.get('similarity_score', r.get('score', 0.0)) 
                    for r in content_recs
                )
                if max_content > 0:
                    for rec in content_recs:
                        score = rec.get('similarity_score', rec.get('score', 0.0))
                        rec['normalized_content_score'] = float(score) / max_content
                else:
                    for rec in content_recs:
                        rec['normalized_content_score'] = 0.0
            
            # Normalize collaborative scores
            if collab_recs:
                max_collab = max(r.get('predicted_rating', 0.0) for r in collab_recs)
                if max_collab > 0:
                    for rec in collab_recs:
                        rec['normalized_collab_score'] = float(rec.get('predicted_rating', 0.0)) / max_collab
                else:
                    for rec in collab_recs:
                        rec['normalized_collab_score'] = 0.0
            
            # Step 4: Combine recommendations with hybrid scoring
            movie_scores = {}
            
            # Add content-based scores
            for rec in content_recs:
                movie_key = rec.get('id') or rec.get('tmdb_id')
                content_score = rec.get('normalized_content_score', 0.0)
                
                movie_scores[movie_key] = {
                    'id': rec.get('id'),
                    'tmdb_id': rec.get('tmdb_id'),
                    'title': rec.get('title', 'Unknown'),
                    'content_score': content_score,
                    'collab_score': 0.0,
                    'hybrid_score': content_weight * content_score,
                    'vote_average': rec.get('vote_average', 0.0),
                    'genres': rec.get('genres', []),
                    'release_date': rec.get('release_date'),
                    'poster_path': rec.get('poster_path'),
                    'overview': rec.get('overview', '')
                }
            
            # Add collaborative scores
            for rec in collab_recs:
                movie_key = rec.get('id') or rec.get('tmdb_id')
                collab_score = rec.get('normalized_collab_score', 0.0)
                
                if movie_key in movie_scores:
                    # Movie already in content-based, add collaborative score
                    movie_scores[movie_key]['collab_score'] = collab_score
                    movie_scores[movie_key]['hybrid_score'] += collaborative_weight * collab_score
                else:
                    # New movie from collaborative filtering only
                    movie_scores[movie_key] = {
                        'id': rec.get('id'),
                        'tmdb_id': rec.get('tmdb_id'),
                        'title': rec.get('title', 'Unknown'),
                        'content_score': 0.0,
                        'collab_score': collab_score,
                        'hybrid_score': collaborative_weight * collab_score,
                        'vote_average': rec.get('vote_average', 0.0),
                        'genres': rec.get('genres', []),
                        'release_date': rec.get('release_date'),
                        'poster_path': rec.get('poster_path'),
                        'overview': rec.get('overview', '')
                    }
            
            # Step 5: Sort by hybrid score and remove duplicates
            results = list(movie_scores.values())
            results.sort(key=lambda x: x['hybrid_score'], reverse=True)
            
            # Get user's rated movie IDs to exclude them from recommendations
            user_rated_movie_ids = set()
            user_ratings_for_exclusion = db.query(Rating).filter(Rating.user_id == user_id).all()
            for r in user_ratings_for_exclusion:
                user_rated_movie_ids.add(r.movie_id)
            
            # Remove None/invalid entries, exclude rated movies, and limit results
            final_results = []
            seen_ids = set()
            
            for rec in results:
                movie_key = rec.get('id') or rec.get('tmdb_id')
                # Skip if already seen or user has already rated this movie
                if movie_key and movie_key not in seen_ids and movie_key not in user_rated_movie_ids:
                    seen_ids.add(movie_key)
                    final_results.append(rec)
                    if len(final_results) >= limit:
                        break
            
            # Fallback: If not enough recommendations, add popular movies user hasn't rated
            if len(final_results) < limit:
                logger.info(f"Hybrid results insufficient ({len(final_results)}), adding popular fallback")
                popular_fallback = db.query(MovieCache).filter(
                    MovieCache.vote_average >= 7.0,
                    ~MovieCache.tmdb_id.in_(user_rated_movie_ids | seen_ids)
                ).order_by(
                    MovieCache.popularity.desc()
                ).limit(limit - len(final_results)).all()
                
                for m in popular_fallback:
                    final_results.append({
                        'id': m.id,
                        'tmdb_id': m.tmdb_id,
                        'title': m.title,
                        'content_score': 0.5,
                        'collab_score': 0.0,
                        'hybrid_score': 0.35,  # Lower score for fallback
                        'vote_average': float(m.vote_average) if m.vote_average else 0.0,
                        'genres': m.genres or [],
                        'release_date': m.release_date,
                        'poster_path': m.poster_path,
                        'overview': m.overview
                    })
            
            logger.info(
                f"Hybrid recommendations: {len(final_results)} movies "
                f"({len(content_recs)} content + {len(collab_recs)} collaborative)"
            )
            
            return final_results
            
        except Exception as e:
            logger.error(f"Error generating hybrid recommendations: {e}")
            # Fallback to content-based only
            if movie_id:
                return RecommendationService.get_similar_movies(db, movie_id, limit)
            else:
                return []
    
    @staticmethod
    def get_personalized_recommendations(
        db: Session,
        user_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get personalized recommendations for a user using hybrid algorithm
        
        This is a convenience wrapper around get_hybrid_recommendations
        that doesn't require a specific movie_id
        
        Args:
            db: Database session
            user_id: Target user ID
            limit: Number of recommendations
            
        Returns:
            List of personalized movie recommendations
        """
        return RecommendationService.get_hybrid_recommendations(
            db=db,
            user_id=user_id,
            movie_id=None,
            limit=limit
        )
