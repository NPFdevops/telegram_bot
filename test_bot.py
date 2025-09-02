#!/usr/bin/env python3
"""
Simple test script to verify the Telegram bot is working
"""

import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("Error: BOT_TOKEN not found in environment variables")
    exit(1)

def test_bot_connection():
    """Test if the bot token is valid and bot is accessible"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('ok'):
            bot_info = data.get('result', {})
            print("✅ Bot connection successful!")
            print(f"Bot username: @{bot_info.get('username')}")
            print(f"Bot name: {bot_info.get('first_name')}")
            print(f"Bot ID: {bot_info.get('id')}")
            return True
        else:
            print("❌ Bot connection failed!")
            print(f"Error: {data.get('description')}")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to bot: {e}")
        return False

def test_webhook_info():
    """Check webhook configuration"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('ok'):
            webhook_info = data.get('result', {})
            print("\n📡 Webhook Information:")
            print(f"URL: {webhook_info.get('url', 'Not set')}")
            print(f"Has custom certificate: {webhook_info.get('has_custom_certificate', False)}")
            print(f"Pending update count: {webhook_info.get('pending_update_count', 0)}")
            
            if webhook_info.get('last_error_date'):
                print(f"⚠️  Last error: {webhook_info.get('last_error_message')}")
                print(f"Last error date: {webhook_info.get('last_error_date')}")
            else:
                print("✅ No webhook errors")
                
            return True
        else:
            print(f"❌ Failed to get webhook info: {data.get('description')}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")
        return False

if __name__ == "__main__":
    print("🤖 Testing Telegram Bot...\n")
    
    # Test bot connection
    if test_bot_connection():
        # Test webhook info
        test_webhook_info()
        print("\n✅ Bot tests completed successfully!")
        print("\n💡 To test the bot manually:")
        print("1. Open Telegram")
        print("2. Search for your bot")
        print("3. Send /start command")
        print("4. Try other commands like /help, /price, /rankings")
    else:
        print("\n❌ Bot tests failed. Please check your configuration.")