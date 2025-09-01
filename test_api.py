#!/usr/bin/env python3

import asyncio
import aiohttp
import ssl
import json

# API Configuration
NFTPF_API_HOST = "nftpf-api-v0.p.rapidapi.com"
NFTPF_API_KEY = "7c50a84629msh50acacfc84ff5ebp1b3c3ajsn9fa81ab704f6"

async def test_projects_v2():
    """Test the projects-v2 endpoint"""
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects-v2"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            params = {
                'offset': 0,
                'limit': 10
            }
            
            print(f"Testing URL: {url}")
            print(f"Headers: {headers}")
            print(f"Params: {params}")
            
            async with session.get(url, headers=headers, params=params) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    print(f"First few characters: {str(data)[:200]}...")
                    return data
                else:
                    text = await response.text()
                    print(f"Error response: {text}")
                    return None
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

async def test_project_by_slug(slug="cryptopunks"):
    """Test the projects/{slug} endpoint"""
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects/{slug}"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            print(f"\nTesting URL: {url}")
            print(f"Headers: {headers}")
            
            async with session.get(url, headers=headers) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    print(f"First few characters: {str(data)[:200]}...")
                    return data
                else:
                    text = await response.text()
                    print(f"Error response: {text}")
                    return None
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

async def test_top_sales():
    """Test the projects/top-sales endpoint"""
    try:
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"https://{NFTPF_API_HOST}/projects/top-sales"
            headers = {
                'x-rapidapi-key': NFTPF_API_KEY,
                'x-rapidapi-host': NFTPF_API_HOST
            }
            
            print(f"\nTesting URL: {url}")
            print(f"Headers: {headers}")
            
            async with session.get(url, headers=headers) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    print(f"First few characters: {str(data)[:200]}...")
                    return data
                else:
                    text = await response.text()
                    print(f"Error response: {text}")
                    return None
    except Exception as e:
        print(f"Exception occurred: {e}")
        return None

async def main():
    print("Testing NFTPriceFloor API endpoints...")
    print("=" * 50)
    
    print("\n1. Testing projects-v2 endpoint:")
    await test_projects_v2()
    
    print("\n2. Testing projects/{slug} endpoint:")
    await test_project_by_slug()
    
    print("\n3. Testing projects/top-sales endpoint:")
    await test_top_sales()

if __name__ == "__main__":
    asyncio.run(main())