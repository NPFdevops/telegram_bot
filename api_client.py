import aiohttp
import ssl
import logging
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

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
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects-v2"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            params = {
                'offset': offset,
                'limit': limit
            }
            
            logger.info(f"Making request to {url} with params {params}")
            async with session.get(url, headers=headers, params=params) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Response data keys: {list(data.keys()) if data else 'None'}")
                    logger.info(f"Data type: {type(data)}")
                    if isinstance(data, dict) and 'data' in data:
                        logger.info(f"Number of projects in data: {len(data['data'])}")
                    return data
                else:
                    response_text = await response.text()
                    logger.warning(f"NFTPriceFloor API request failed with status {response.status}, response: {response_text}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching NFTPriceFloor data: {e}")
        return None