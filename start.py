#!/usr/bin/env python3
"""
Start script for Railway deployment
"""

import os
import sys

def main():
    print("🚀 Starting Telegram Affiliate Bot...")
    print("📋 Using bot_web.py for Railway deployment")
    
    # Check if bot_web.py exists
    if os.path.exists("bot_web.py"):
        print("✅ Found bot_web.py, starting web server version...")
        # Import and run bot_web.py directly
        try:
            import bot_web
            print("✅ bot_web.py imported successfully")
        except Exception as e:
            print(f"❌ Error importing bot_web.py: {e}")
            print("🔄 Falling back to bot.py...")
            import bot
    else:
        print("❌ bot_web.py not found, falling back to bot.py...")
        import bot

if __name__ == "__main__":
    main()
