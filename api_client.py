import aiohttp
import ssl
import logging
import os
import asyncio
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from error_handler import handle_api_error, log_api_request

load_dotenv()

logger = logging.getLogger(__name__)

# API Configuration
NFTPF_API_HOST = os.getenv('NFTPF_API_HOST', 'nftpf-api-v0.p.rapidapi.com')
NFTPF_API_KEY = os.getenv('NFTPF_API_KEY')
if not NFTPF_API_KEY:
    raise ValueError("NFTPF_API_KEY environment variable is required")

async def fetch_nftpf_projects(offset: int = 0, limit: int = 10) -> Optional[Dict[str, Any]]:
    """
    Fetch NFT projects data from NFTPriceFloor API.
    """
    url = f"https://{NFTPF_API_HOST}/projects-v2"
    params = {'offset': offset, 'limit': limit}
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            log_api_request(url, params)
            
            async with session.get(url, headers=headers, params=params) as response:
                log_api_request(url, params, response.status)
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully fetched {len(data.get('data', []))} projects")
                    return data
                elif response.status == 429:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429,
                        message="Rate limit exceeded"
                    )
                elif response.status == 404:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=404,
                        message="Endpoint not found"
                    )
                elif 500 <= response.status < 600:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Server error: {response_text[:200]}"
                    )
                else:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"API error: {response_text[:200]}"
                    )
                    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        success, error_type = await handle_api_error(e, "fetch_nftpf_projects")
        return None
    except Exception as e:
        success, error_type = await handle_api_error(e, "fetch_nftpf_projects")
        return None


async def fetch_nftpf_project_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific NFT project by slug from NFTPriceFloor API.
    Uses the /projects/{slug} endpoint to get detailed project information.
    """
    url = f"https://{NFTPF_API_HOST}/projects/{slug}"
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            log_api_request(url)
            
            async with session.get(url, headers=headers) as response:
                log_api_request(url, None, response.status)
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully fetched project data for slug: {slug}")
                    return data
                elif response.status == 429:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429,
                        message="Rate limit exceeded"
                    )
                elif response.status == 404:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=404,
                        message="Project not found"
                    )
                elif 500 <= response.status < 600:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Server error: {response_text[:200]}"
                    )
                else:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"API error: {response_text[:200]}"
                    )
                    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        success, error_type = await handle_api_error(e, "fetch_nftpf_project_by_slug")
        return None
    except Exception as e:
        success, error_type = await handle_api_error(e, "fetch_nftpf_project_by_slug")
        return None


async def fetch_top_sales() -> Optional[Dict[str, Any]]:
    """
    Fetch top NFT sales data from NFTPriceFloor API.
    Uses the 24h endpoint to get recent top sales.
    """
    url = f"https://{NFTPF_API_HOST}/projects/top-sales/24h"
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            log_api_request(url)
            
            async with session.get(url, headers=headers) as response:
                log_api_request(url, None, response.status)
                
                if response.status == 200:
                    data = await response.json()
                    # Handle both list and dict formats
                    if isinstance(data, list):
                        sales_count = len(data)
                        logger.info(f"Successfully fetched {sales_count} top sales")
                    elif isinstance(data, dict):
                        projects_count = len(data.get('projects', []))
                        logger.info(f"Successfully fetched {projects_count} top sales")
                    else:
                        logger.info("Successfully fetched top sales data")
                    return data
                elif response.status == 429:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429,
                        message="Rate limit exceeded"
                    )
                elif response.status == 404:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=404,
                        message="Endpoint not found"
                    )
                elif 500 <= response.status < 600:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Server error: {response_text[:200]}"
                    )
                else:
                    response_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"API error: {response_text[:200]}"
                    )
                    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        success, error_type = await handle_api_error(e, "fetch_top_sales")
        return None
    except Exception as e:
        success, error_type = await handle_api_error(e, "fetch_top_sales")
        return None