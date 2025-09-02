#!/usr/bin/env python3
"""
Complete test for top sales functionality
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import fetch_top_sales
from cached_api import fetch_top_sales_cached
from bot import format_top_sales_message

async def test_complete_top_sales():
    print("=== Testing Complete Top Sales Functionality ===")
    
    # Test 1: Direct API call
    print("\n1. Testing direct API call...")
    try:
        api_data = await fetch_top_sales()
        if api_data:
            print(f"✅ API call successful, got {len(api_data) if isinstance(api_data, list) else 'unknown'} items")
            print(f"Data type: {type(api_data)}")
            if isinstance(api_data, list) and len(api_data) > 0:
                print(f"First item keys: {list(api_data[0].keys())}")
        else:
            print("❌ API call returned None")
            return
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return
    
    # Test 2: Cached API call
    print("\n2. Testing cached API call...")
    try:
        cached_data = await fetch_top_sales_cached()
        if cached_data:
            print(f"✅ Cached API call successful, got {len(cached_data) if isinstance(cached_data, list) else 'unknown'} items")
        else:
            print("❌ Cached API call returned None")
            return
    except Exception as e:
        print(f"❌ Cached API call failed: {e}")
        return
    
    # Test 3: Message formatting
    print("\n3. Testing message formatting...")
    try:
        # Use a dummy user_id for testing
        test_user_id = 12345
        formatted_message = await format_top_sales_message(cached_data, test_user_id)
        print(f"✅ Message formatting successful")
        print(f"Message length: {len(formatted_message)} characters")
        print("\n--- Formatted Message Preview ---")
        print(formatted_message[:500] + "..." if len(formatted_message) > 500 else formatted_message)
        print("--- End Preview ---")
    except Exception as e:
        print(f"❌ Message formatting failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 All tests passed! Top sales functionality should work correctly.")

if __name__ == "__main__":
    asyncio.run(test_complete_top_sales())