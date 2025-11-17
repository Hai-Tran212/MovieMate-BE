"""
Caching Utilities
=================
Provides caching decorators and utilities for improving performance.

Features:
- In-memory cache with TTL (Time To Live)
- Cache invalidation
- LRU (Least Recently Used) eviction
- Simple decorator pattern for easy integration

Usage:
    from app.utils.cache import cache, invalidate_cache
    
    @cache(ttl=300)  # Cache for 5 minutes
    def expensive_function(arg1, arg2):
        # Your expensive computation here
        return result
    
    # Invalidate specific cache
    invalidate_cache(expensive_function, arg1, arg2)
    
    # Clear all cache
    clear_all_cache()
"""
from functools import wraps
from typing import Any, Callable, Optional
from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheStore:
    """
    Simple in-memory cache with TTL and LRU eviction.
    For production with multiple workers, use Redis instead.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize cache store.
        
        Args:
            max_size: Maximum number of items in cache (LRU eviction)
        """
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Create a unique cache key from function name and arguments.
        
        Args:
            func_name: Name of the function
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Unique cache key as string
        """
        # Convert args and kwargs to a stable string representation
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        
        # Create hash for complex objects
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None
        
        value, expiry = self._cache[key]
        
        # Check if expired
        if expiry and datetime.now() > expiry:
            del self._cache[key]
            self._misses += 1
            return None
        
        # Move to end (LRU)
        self._cache.move_to_end(key)
        self._hits += 1
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
        """
        # Calculate expiry time
        expiry = datetime.now() + timedelta(seconds=ttl) if ttl else None
        
        # Add to cache
        self._cache[key] = (value, expiry)
        self._cache.move_to_end(key)
        
        # Evict oldest if over max_size (LRU)
        if len(self._cache) > self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Evicted cache key: {oldest_key}")
    
    def delete(self, key: str) -> None:
        """Delete a specific cache key."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.2f}%"
        }


# Global cache instance
_cache_store = CacheStore(max_size=1000)


def cache(ttl: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default: 300 = 5 minutes)
    
    Usage:
        @cache(ttl=600)  # Cache for 10 minutes
        def get_popular_movies(page: int = 1):
            # Expensive TMDB API call
            return movies
    
    Note:
        - Only works with hashable arguments
        - For production with multiple workers, use Redis
        - Cache is per-process (not shared across workers)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = _cache_store._make_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_value = _cache_store.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # Call function and cache result
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            _cache_store.set(cache_key, result, ttl)
            
            return result
        
        # Attach invalidation method to function
        wrapper.invalidate = lambda *args, **kwargs: invalidate_cache(func, *args, **kwargs)
        wrapper.clear = lambda: clear_function_cache(func)
        
        return wrapper
    
    return decorator


def invalidate_cache(func: Callable, *args, **kwargs) -> None:
    """
    Invalidate a specific cache entry.
    
    Args:
        func: The cached function
        *args: Function arguments
        **kwargs: Function keyword arguments
    
    Usage:
        invalidate_cache(get_popular_movies, page=1)
    """
    cache_key = _cache_store._make_key(func.__name__, args, kwargs)
    _cache_store.delete(cache_key)
    logger.debug(f"Invalidated cache for {func.__name__}")


def clear_function_cache(func: Callable) -> None:
    """
    Clear all cache entries for a specific function.
    
    Args:
        func: The cached function
    """
    # This is a simple implementation - clears all cache
    # For more sophisticated filtering, enhance CacheStore
    logger.warning(f"Clearing all cache (specific function cache not implemented)")
    _cache_store.clear()


def clear_all_cache() -> None:
    """Clear all cache entries."""
    _cache_store.clear()
    logger.info("All cache cleared")


def get_cache_stats() -> dict:
    """
    Get cache statistics.
    
    Returns:
        Dictionary with cache performance metrics
    """
    return _cache_store.get_stats()


# Cache warming utilities
def warm_cache(func: Callable, param_sets: list) -> None:
    """
    Pre-populate cache with common queries.
    
    Args:
        func: The cached function
        param_sets: List of (args, kwargs) tuples to pre-cache
    
    Usage:
        warm_cache(get_popular_movies, [
            ((), {'page': 1}),
            ((), {'page': 2}),
        ])
    """
    logger.info(f"Warming cache for {func.__name__} with {len(param_sets)} entries")
    
    for args, kwargs in param_sets:
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error warming cache for {func.__name__}: {str(e)}")
    
    logger.info(f"Cache warming complete for {func.__name__}")
