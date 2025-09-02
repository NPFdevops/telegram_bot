#!/usr/bin/env python3
"""
Test script to verify the Telegram bot webhook is working correctly.
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("Error: BOT_TOKEN not found in environment variables")
    exit(1)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def test_webhook_info():
    """Test webhook configuration"""
    print("\n=== Testing Webhook Configuration ===")
    
    response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
    if response.status_code == 200:
        webhook_info = response.json()
        if webhook_info['ok']:
            result = webhook_info['result']
            print(f"✅ Webhook URL: {result.get('url', 'Not set')}")
            print(f"✅ Pending updates: {result.get('pending_update_count', 0)}")
            
            if 'last_error_date' in result:
                print(f"⚠️  Last error: {result.get('last_error_message', 'Unknown')}")
                return False
            else:
                print("✅ No webhook errors detected")
                return True
        else:
            print(f"❌ API Error: {webhook_info.get('description', 'Unknown error')}")
            return False
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        return False

def test_bot_info():
    """Test bot basic info"""
    print("\n=== Testing Bot Information ===")
    
    response = requests.get(f"{TELEGRAM_API_URL}/getMe")
    if response.status_code == 200:
        bot_info = response.json()
        if bot_info['ok']:
            result = bot_info['result']
            print(f"✅ Bot Username: @{result.get('username', 'Unknown')}")
            print(f"✅ Bot Name: {result.get('first_name', 'Unknown')}")
            print(f"✅ Bot ID: {result.get('id', 'Unknown')}")
            print(f"✅ Can Join Groups: {result.get('can_join_groups', False)}")
            print(f"✅ Can Read All Group Messages: {result.get('can_read_all_group_messages', False)}")
            return True
        else:
            print(f"❌ API Error: {bot_info.get('description', 'Unknown error')}")
            return False
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        return False

def main():
    print("🤖 Testing Telegram Bot Webhook Configuration")
    print("=" * 50)
    
    # Test bot info
    bot_test = test_bot_info()
    
    # Test webhook
    webhook_test = test_webhook_info()
    
    print("\n=== Test Summary ===")
    if bot_test and webhook_test:
        print("✅ All tests passed! Bot should be working correctly.")
        print("\n📱 To test manually:")
        print("1. Open Telegram")
        print("2. Search for your bot")
        print("3. Send /start command")
        print("4. Try other commands like /help, /price, /rankings")
    else:
        print("❌ Some tests failed. Check the errors above.")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()