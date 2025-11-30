"""
Collaborative Filtering Service
User-based collaborative filtering for movie recommendations
"""
from typing import List, Dict, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.rating import Rating
from app.models.user import User
from app.models.movie_cache import MovieCache
import logging

logger = logging.getLogger(__name__)


class CollaborativeService:
    """
    User-based Collaborative Filtering using cosine similarity
    
    Key Features:
    - User-item rating matrix construction
    - User similarity calculation
    - Rating prediction for unrated movies
    - Configurable parameters for easy tuning
    """
    
    # Configuration constants (easy to modify)
    MIN_RATINGS_FOR_CF = 10         # Minimum ratings needed for CF
    DEFAULT_K_NEIGHBORS = 10        # Number of similar users to consider
    MIN_PREDICTED_RATING = 6.0      # Minimum predicted rating threshold
    MAX_CANDIDATE_MOVIES = 100      # Candidates for prediction
    
    # Cache for performance
    _user_item_matrix_cache: Optional[Tuple[np.ndarray, Dict, Dict]] = None
    _cache_timestamp: Optional[float] = None
    CACHE_TTL_SECONDS = 300  # 5 minutes cache
    
    @staticmethod
    def _is_cache_valid() -> bool:
        """Check if cached matrix is still valid"""
        if CollaborativeService._cache_timestamp is None:
            return False
        import time
        return (time.time() - CollaborativeService._cache_timestamp) < CollaborativeService.CACHE_TTL_SECONDS
    
    @staticmethod
    def build_user_item_matrix(db: Session, force_refresh: bool = False) -> Tuple[Optional[np.ndarray], Optional[Dict], Optional[Dict]]:
        """
        Build user-item rating matrix for collaborative filtering
        
        Args:
            db: Database session
            force_refresh: Force rebuild cache
            
        Returns:
            Tuple of (matrix, user_to_idx, movie_to_idx) or (None, None, None) if insufficient data
        """
        # Check cache first
        if not force_refresh and CollaborativeService._is_cache_valid():
            return CollaborativeService._user_item_matrix_cache
        
        try:
            # Get all ratings
            ratings = db.query(Rating).all()
            
            if len(ratings) < CollaborativeService.MIN_RATINGS_FOR_CF:
                logger.info(f"Insufficient ratings for CF: {len(ratings)} < {CollaborativeService.MIN_RATINGS_FOR_CF}")
                return None, None, None
            
            # Create user and movie ID mappings
            user_ids = list(set(r.user_id for r in ratings))
            movie_ids = list(set(r.movie_id for r in ratings))
            
            user_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}
            movie_to_idx = {mid: idx for idx, mid in enumerate(movie_ids)}
            
            # Initialize matrix with zeros
            matrix = np.zeros((len(user_ids), len(movie_ids)))
            
            # Fill matrix with ratings
            for rating in ratings:
                u_idx = user_to_idx[rating.user_id]
                m_idx = movie_to_idx[rating.movie_id]
                matrix[u_idx][m_idx] = rating.rating
            
            # Cache the result
            import time
            CollaborativeService._user_item_matrix_cache = (matrix, user_to_idx, movie_to_idx)
            CollaborativeService._cache_timestamp = time.time()
            
            logger.info(f"Built user-item matrix: {matrix.shape[0]} users x {matrix.shape[1]} movies")
            return matrix, user_to_idx, movie_to_idx
            
        except Exception as e:
            logger.error(f"Error building user-item matrix: {e}")
            return None, None, None
    
    @staticmethod
    def get_user_similarity(
        matrix: np.ndarray, 
        user_idx: int, 
        k: int = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find k most similar users using cosine similarity
        
        Args:
            matrix: User-item rating matrix
            user_idx: Index of target user
            k: Number of similar users (default: DEFAULT_K_NEIGHBORS)
            
        Returns:
            Tuple of (similar_user_indices, similarity_scores)
        """
        if k is None:
            k = CollaborativeService.DEFAULT_K_NEIGHBORS
            
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Get user's rating vector
            user_vector = matrix[user_idx].reshape(1, -1)
            
            # Calculate similarity with all users
            similarities = cosine_similarity(user_vector, matrix)[0]
            
            # Get top k similar users (excluding self)
            # argsort returns indices in ascending order, so reverse it
            similar_indices = np.argsort(similarities)[::-1][1:k+1]
            
            return similar_indices, similarities[similar_indices]
            
        except Exception as e:
            logger.error(f"Error calculating user similarity: {e}")
            return np.array([]), np.array([])
    
    @staticmethod
    def predict_ratings_collaborative(
        db: Session,
        user_id: int,
        movie_ids: List[int],
        k: int = None
    ) -> Dict[int, float]:
        """
        Predict ratings using user-based collaborative filtering
        
        Args:
            db: Database session
            user_id: Target user ID
            movie_ids: List of movie IDs to predict ratings for
            k: Number of similar users to consider
            
        Returns:
            Dict mapping movie_id -> predicted_rating
        """
        if k is None:
            k = CollaborativeService.DEFAULT_K_NEIGHBORS
            
        # Build user-item matrix
        matrix, user_to_idx, movie_to_idx = CollaborativeService.build_user_item_matrix(db)
        
        if matrix is None:
            logger.info("Cannot predict ratings: insufficient data for CF")
            return {}
        
        # Check if user exists in matrix
        if user_id not in user_to_idx:
            logger.info(f"User {user_id} not found in rating matrix")
            return {}
        
        user_idx = user_to_idx[user_id]
        
        # Find similar users
        similar_users, similarities = CollaborativeService.get_user_similarity(matrix, user_idx, k)
        
        if len(similar_users) == 0:
            logger.info(f"No similar users found for user {user_id}")
            return {}
        
        predictions = {}
        
        for movie_id in movie_ids:
            if movie_id not in movie_to_idx:
                continue
            
            movie_idx = movie_to_idx[movie_id]
            
            # Skip if user already rated this movie
            if matrix[user_idx][movie_idx] > 0:
                predictions[movie_id] = float(matrix[user_idx][movie_idx])
                continue
            
            # Predict based on similar users' ratings
            numerator = 0.0
            denominator = 0.0
            
            for sim_idx, similarity in zip(similar_users, similarities):
                sim_rating = matrix[sim_idx][movie_idx]
                if sim_rating > 0:  # Only consider users who rated this movie
                    numerator += similarity * sim_rating
                    denominator += abs(similarity)
            
            # Calculate predicted rating
            if denominator > 0:
                predicted_rating = numerator / denominator
                predictions[movie_id] = float(predicted_rating)
        
        return predictions
    
    @staticmethod
    def get_collaborative_recommendations(
        db: Session,
        user_id: int,
        limit: int = 20,
        k: int = None
    ) -> List[Dict]:
        """
        Get movie recommendations using collaborative filtering
        
        Args:
            db: Database session
            user_id: Target user ID
            limit: Number of recommendations
            k: Number of similar users to consider
            
        Returns:
            List of recommended movies with predicted ratings
        """
        try:
            # Get movies user hasn't rated
            user_ratings = db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
            rated_movie_ids = {r.movie_id for r in user_ratings}
            
            # Get candidate movies (popular ones user hasn't rated)
            candidate_movies = db.query(MovieCache).filter(
                ~MovieCache.id.in_(rated_movie_ids)
            ).order_by(
                MovieCache.popularity.desc()
            ).limit(CollaborativeService.MAX_CANDIDATE_MOVIES).all()
            
            if not candidate_movies:
                logger.info(f"No candidate movies found for user {user_id}")
                return []
            
            candidate_ids = [m.id for m in candidate_movies]
            
            # Predict ratings for candidates
            predictions = CollaborativeService.predict_ratings_collaborative(
                db, user_id, candidate_ids, k
            )
            
            if not predictions:
                logger.info(f"No predictions generated for user {user_id}")
                return []
            
            # Build recommendations list
            recommendations = []
            for movie_id, predicted_rating in predictions.items():
                # Only recommend if predicted rating is high enough
                if predicted_rating >= CollaborativeService.MIN_PREDICTED_RATING:
                    movie = next((m for m in candidate_movies if m.id == movie_id), None)
                    if movie:
                        recommendations.append({
                            'id': movie.id,
                            'tmdb_id': movie.tmdb_id,
                            'title': movie.title,
                            'predicted_rating': float(predicted_rating),
                            'vote_average': float(movie.vote_average) if movie.vote_average else 0.0,
                            'genres': movie.genres or [],
                            'release_date': movie.release_date.isoformat() if movie.release_date else None,
                            'poster_path': movie.poster_path,
                            'overview': movie.overview
                        })
            
            # Sort by predicted rating
            recommendations.sort(key=lambda x: x['predicted_rating'], reverse=True)
            
            logger.info(f"Generated {len(recommendations)} collaborative recommendations for user {user_id}")
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error in collaborative recommendations: {e}")
            return []
    
    @staticmethod
    def clear_cache():
        """Clear the cached user-item matrix"""
        CollaborativeService._user_item_matrix_cache = None
        CollaborativeService._cache_timestamp = None
        logger.info("Collaborative filtering cache cleared")
