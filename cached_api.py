import asyncio
import logging
from typing import List, Dict, Any, Optional
from cache_manager import (
    projects_cache_key,
    project_cache_key,
    search_cache_key,
    top_sales_cache_key,
    rankings_cache_key
)
from api_client import fetch_nftpf_projects, fetch_top_sales
import aiohttp
import json

logger = logging.getLogger(__name__)

# Cache TTL configurations (in minutes)
CACHE_TTL = {
    'projects': 5,      # Projects list cache for 5 minutes
    'project': 10,      # Individual project cache for 10 minutes
    'search': 3,        # Search results cache for 3 minutes
    'top_sales': 2,     # Top sales cache for 2 minutes
    'rankings': 5       # Rankings cache for 5 minutes
}

async def fetch_nftpf_projects_cached(offset: int = 0, limit: int = 10) -> Optional[Dict[str, Any]]:
    """Fetch NFTPF projects with caching."""
    from cache_manager import init_cache
    import cache_manager as cm
    
    # Initialize cache if not already done
    await init_cache()
    
    cache_key = projects_cache_key(offset, limit)
    
    # Try to get from cache first
    cached_data = await cm.cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for projects (offset={offset}, limit={limit})")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug(f"Cache miss for projects (offset={offset}, limit={limit}) - fetching from API")
    try:
        projects = await fetch_nftpf_projects(offset, limit)
        
        # Cache the result
        await cm.cache_manager.set(cache_key, projects, CACHE_TTL['projects'])
        
        return projects
    except Exception as e:
        logger.error(f"Error fetching projects from API: {e}")
        # Return empty list on error
        return []

async def fetch_nftpf_project_by_slug_cached(slug: str) -> Optional[Dict[str, Any]]:
    """Fetch individual NFTPF project by slug with caching."""
    # Initialize cache manager if not already done
    from cache_manager import init_cache
    import cache_manager as cm
    await init_cache()
    
    cache_key = project_cache_key(slug)
    
    # Try to get from cache first
    cached_data = await cm.cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for project: {slug}")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug(f"Cache miss for project: {slug} - fetching from API")
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.nftpricefloor.com/v2/projects/{slug}"
            async with session.get(url) as response:
                if response.status == 200:
                    project_data = await response.json()
                    
                    # Cache the result
                    await cm.cache_manager.set(cache_key, project_data, CACHE_TTL['project'])
                    
                    return project_data
                else:
                    logger.warning(f"API returned status {response.status} for project {slug}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching project {slug} from API: {e}")
        return None

async def search_nftpf_collection_cached(collection_name: str, user_id: int = None, 
                                       filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Search NFTPF collections with caching."""
    # Initialize cache manager if not already done
    from cache_manager import init_cache
    import cache_manager as cm
    await init_cache()
    
    # Generate cache key based on search parameters (excluding user_id for shared cache)
    cache_key = search_cache_key(collection_name, filters)
    
    # Try to get from cache first
    cached_data = await cm.cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for search: {collection_name}")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug(f"Cache miss for search: {collection_name} - fetching from API")
    try:
        # Fetch all projects and filter locally (for now)
        projects_data = await fetch_nftpf_projects_cached(0, 1000)  # Get more projects for search
        
        # Extract projects list from the response
        if not projects_data or 'projects' not in projects_data:
            return []
        
        all_projects = projects_data['projects']
        
        # Filter projects by name
        matching_projects = []
        search_term = collection_name.lower()
        
        for project in all_projects:
            project_name = project.get('name', '').lower()
            project_slug = project.get('slug', '').lower()
            
            # Check for exact or partial matches
            if (search_term == project_name or 
                search_term == project_slug or 
                search_term in project_name or 
                search_term in project_slug):
                matching_projects.append(project)
        
        # Apply filters if provided
        if filters:
            matching_projects = _apply_search_filters_cached(matching_projects, filters)
        
        # Cache the result
        await cm.cache_manager.set(cache_key, matching_projects, CACHE_TTL['search'])
        
        return matching_projects
    except Exception as e:
        logger.error(f"Error searching collections: {e}")
        return []

def _apply_search_filters_cached(projects: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply search filters to project list."""
    filtered_projects = projects.copy()
    
    # Filter by category
    if filters.get('category'):
        category = filters['category'].lower()
        filtered_projects = [
            p for p in filtered_projects 
            if p.get('category', '').lower() == category
        ]
    
    # Filter by price range
    if filters.get('min_price') or filters.get('max_price'):
        min_price = filters.get('min_price', 0)
        max_price = filters.get('max_price', float('inf'))
        
        filtered_projects = [
            p for p in filtered_projects 
            if min_price <= p.get('floor_price', 0) <= max_price
        ]
    
    # Filter by volume range
    if filters.get('min_volume') or filters.get('max_volume'):
        min_volume = filters.get('min_volume', 0)
        max_volume = filters.get('max_volume', float('inf'))
        
        filtered_projects = [
            p for p in filtered_projects 
            if min_volume <= p.get('volume_24h', 0) <= max_volume
        ]
    
    # Filter trending projects
    if filters.get('trending'):
        # Sort by volume and take top projects
        filtered_projects.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
        filtered_projects = filtered_projects[:50]  # Top 50 trending
    
    # Filter blue chip projects (high floor price and volume)
    if filters.get('blue_chip'):
        filtered_projects = [
            p for p in filtered_projects 
            if p.get('floor_price', 0) > 1.0 and p.get('volume_24h', 0) > 100
        ]
    
    # Filter new projects (created recently)
    if filters.get('new_projects'):
        # This would require creation date from API
        # For now, filter by lower floor prices as proxy for newer projects
        filtered_projects = [
            p for p in filtered_projects 
            if p.get('floor_price', 0) < 1.0
        ]
    
    return filtered_projects

async def fetch_top_sales_cached() -> List[Dict[str, Any]]:
    """Fetch top sales with caching."""
    # Initialize cache manager if not already done
    from cache_manager import init_cache
    import cache_manager as cm
    await init_cache()
    
    cache_key = top_sales_cache_key()
    
    # Try to get from cache first
    cached_data = await cm.cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug("Cache hit for top sales")
        return cached_data
    
    # Cache miss - fetch from API
    logger.debug("Cache miss for top sales - fetching from API")
    try:
        top_sales = await fetch_top_sales()
        
        if top_sales is None:
            return None
            
        # Cache the result
        await cm.cache_manager.set(cache_key, top_sales, CACHE_TTL['top_sales'])
        
        return top_sales
    except Exception as e:
        logger.error(f"Error fetching top sales from API: {e}")
        return None

async def fetch_rankings_cached(offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch rankings with caching (using projects data sorted by volume)."""
    # Initialize cache manager if not already done
    from cache_manager import init_cache
    import cache_manager as cm
    await init_cache()
    
    cache_key = rankings_cache_key(offset, limit)
    
    # Try to get from cache first
    cached_data = await cm.cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for rankings (offset={offset}, limit={limit})")
        return cached_data
    
    # Cache miss - fetch and sort
    logger.debug(f"Cache miss for rankings (offset={offset}, limit={limit}) - generating from projects")
    try:
        # Get all projects and sort by volume
        projects_data = await fetch_nftpf_projects_cached(0, 1000)
        
        # Extract projects list from the response
        if not projects_data or 'projects' not in projects_data:
            return []
        
        all_projects = projects_data['projects']
        
        # Sort by 24h volume (descending)
        sorted_projects = sorted(
            all_projects, 
            key=lambda x: x.get('volume_24h', 0), 
            reverse=True
        )
        
        # Apply pagination
        rankings = sorted_projects[offset:offset + limit]
        
        # Cache the result
        await cm.cache_manager.set(cache_key, rankings, CACHE_TTL['rankings'])
        
        return rankings
    except Exception as e:
        logger.error(f"Error generating rankings: {e}")
        return []

# Cache warming functions
async def warm_cache():
    """Pre-populate cache with commonly requested data."""
    logger.info("Starting cache warming...")
    
    try:
        # Warm up projects cache
        await fetch_nftpf_projects_cached(0, 100)
        
        # Warm up rankings cache
        await fetch_rankings_cached(0, 20)
        
        # Warm up top sales cache
        await fetch_top_sales_cached()
        
        logger.info("Cache warming completed successfully")
    except Exception as e:
        logger.error(f"Error during cache warming: {e}")

# Cache statistics and monitoring
async def get_cache_stats() -> Dict[str, Any]:
    """Get comprehensive cache statistics."""
    return cache_manager.get_stats()

async def get_cache_info() -> Dict[str, Any]:
    """Get detailed cache information."""
    return cache_manager.get_cache_info()

# Cache management functions
async def clear_cache():
    """Clear all cached data."""
    await cache_manager.clear()
    logger.info("All cache data cleared")

async def clear_cache_by_type(cache_type: str):
    """Clear cache entries of a specific type."""
    if cache_type not in CACHE_TTL:
        logger.warning(f"Unknown cache type: {cache_type}")
        return
    
    # Get all cache keys and filter by type
    keys_to_delete = [
        key for key in cache_manager.cache.keys() 
        if key.startswith(f"{cache_type}:")
    ]
    
    for key in keys_to_delete:
        await cache_manager.delete(key)
    
    logger.info(f"Cleared {len(keys_to_delete)} {cache_type} cache entries")