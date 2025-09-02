#!/usr/bin/env python3

import asyncio
import aiohttp
import ssl
import os
import json
from dotenv import load_dotenv

load_dotenv()

NFTPF_API_HOST = os.getenv('NFTPF_API_HOST', 'nftpf-api-v0.p.rapidapi.com')
NFTPF_API_KEY = os.getenv('NFTPF_API_KEY')

async def test_top_sales_api():
    """Test the top sales API endpoint to see the response structure."""
    url = f"https://{NFTPF_API_HOST}/projects/top-sales/24h"
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            print(f"Testing API endpoint: {url}")
            print(f"Headers: {headers}")
            
            async with session.get(url, headers=headers) as response:
                print(f"Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Response data structure:")
                    print(json.dumps(data, indent=2)[:1000])  # First 1000 chars
                    
                    # Check what keys are available
                    if isinstance(data, dict):
                        print(f"\nTop-level keys: {list(data.keys())}")
                        
                        # Check if it has 'sales' or 'projects' key
                        if 'sales' in data:
                            print(f"Found 'sales' key with {len(data['sales'])} items")
                            if data['sales']:
                                print(f"First sale item keys: {list(data['sales'][0].keys())}")
                        elif 'projects' in data:
                            print(f"Found 'projects' key with {len(data['projects'])} items")
                            if data['projects']:
                                print(f"First project item keys: {list(data['projects'][0].keys())}")
                        else:
                            print("No 'sales' or 'projects' key found")
                    
                    return data
                else:
                    response_text = await response.text()
                    print(f"Error response: {response_text}")
                    return None
                    
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(test_top_sales_api())