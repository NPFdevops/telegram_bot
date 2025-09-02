import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, asdict
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Represents a cache entry with data and metadata."""
    data: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return datetime.now() >= self.expires_at
    
    def access(self) -> Any:
        """Access the cached data and update access metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now()
        return self.data

class CacheManager:
    """Advanced cache manager with TTL, LRU eviction, and statistics."""
    
    def __init__(self, max_size: int = 1000, default_ttl_minutes: int = 5):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl_minutes = default_ttl_minutes
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired_removals': 0
        }
        self._cleanup_task = None
        self._initialized = False
    
    def _start_cleanup_task(self):
        """Start background cleanup task."""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        except RuntimeError:
            # No event loop running, will start during initialization
            pass
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate a consistent cache key from parameters."""
        # Sort kwargs to ensure consistent key generation
        sorted_params = sorted(kwargs.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        key_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        return f"{prefix}:{key_hash}:{params_str}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get data from cache."""
        if key not in self.cache:
            self.stats['misses'] += 1
            return None
        
        entry = self.cache[key]
        
        if entry.is_expired():
            del self.cache[key]
            self.stats['expired_removals'] += 1
            self.stats['misses'] += 1
            return None
        
        self.stats['hits'] += 1
        return entry.access()
    
    async def set(self, key: str, data: Any, ttl_minutes: Optional[int] = None) -> None:
        """Set data in cache with optional TTL."""
        if ttl_minutes is None:
            ttl_minutes = self.default_ttl_minutes
        
        now = datetime.now()
        expires_at = now + timedelta(minutes=ttl_minutes)
        
        # Check if we need to evict entries
        if len(self.cache) >= self.max_size and key not in self.cache:
            await self._evict_lru()
        
        self.cache[key] = CacheEntry(
            data=data,
            created_at=now,
            expires_at=expires_at
        )
        
        logger.debug(f"Cached data with key: {key[:50]}... (TTL: {ttl_minutes}m)")
    
    async def _evict_lru(self):
        """Evict least recently used entry."""
        if not self.cache:
            return
        
        # Find the least recently used entry
        lru_key = min(self.cache.keys(), 
                     key=lambda k: self.cache[k].last_accessed)
        
        del self.cache[lru_key]
        self.stats['evictions'] += 1
        logger.debug(f"Evicted LRU entry: {lru_key[:50]}...")
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries and return count removed."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items() 
            if entry.expires_at <= now
        ]
        
        for key in expired_keys:
            del self.cache[key]
            self.stats['expired_removals'] += 1
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    async def delete(self, key: str) -> bool:
        """Delete a specific cache entry."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests,
            **self.stats
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information."""
        now = datetime.now()
        entries_info = []
        
        for key, entry in list(self.cache.items())[:10]:  # Show first 10 entries
            entries_info.append({
                'key': key[:50] + '...' if len(key) > 50 else key,
                'created_at': entry.created_at.isoformat(),
                'expires_in_minutes': round((entry.expires_at - now).total_seconds() / 60, 1),
                'access_count': entry.access_count,
                'last_accessed': entry.last_accessed.isoformat()
            })
        
        return {
            'stats': self.get_stats(),
            'sample_entries': entries_info
        }
    
    async def shutdown(self):
        """Shutdown the cache manager and cleanup tasks."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await self.clear()
        logger.info("Cache manager shutdown complete")

# Global cache manager instance
cache_manager = None

# Cache key generators for different data types
def projects_cache_key(offset: int = 0, limit: int = 10) -> str:
    """Generate cache key for projects data."""
    return cache_manager._generate_key('projects', offset=offset, limit=limit)

def project_cache_key(slug: str) -> str:
    """Generate cache key for individual project data."""
    return cache_manager._generate_key('project', slug=slug)

def search_cache_key(collection_name: str, filters: Dict[str, Any] = None) -> str:
    """Generate cache key for search results."""
    return cache_manager._generate_key('search', 
                                     collection_name=collection_name.lower(),
                                     filters=filters or {})

def top_sales_cache_key() -> str:
    """Generate cache key for top sales data."""
    return cache_manager._generate_key('top_sales')

def rankings_cache_key(offset: int = 0, limit: int = 10) -> str:
    """Generate cache key for rankings data."""
    return cache_manager._generate_key('rankings', offset=offset, limit=limit)

# Cleanup function for graceful shutdown
async def cleanup_cache():
    """Cleanup cache on application shutdown."""
    await cache_manager.shutdown()
    logger.info("Cache cleanup completed")

# Initialize cache
async def init_cache():
    """Initialize cache manager."""
    global cache_manager
    if cache_manager is None:
        cache_manager = CacheManager(max_size=1000, default_ttl_minutes=5)
    
    # Start cleanup task now that we have an event loop
    if not cache_manager._initialized:
        cache_manager._start_cleanup_task()
        cache_manager._initialized = True
    
    logger.info("Cache manager initialized")
    return cache_manager