#!/usr/bin/env python3
"""
Start script for Railway deployment
"""

import subprocess
import sys
import os

def main():
    print("🚀 Starting Telegram Affiliate Bot...")
    print("📋 Using bot_web.py for Railway deployment")
    
    # Check if bot_web.py exists
    if os.path.exists("bot_web.py"):
        print("✅ Found bot_web.py, starting web server version...")
        # Run bot_web.py
        result = subprocess.run([sys.executable, "bot_web.py"])
        sys.exit(result.returncode)
    else:
        print("❌ bot_web.py not found, falling back to bot.py...")
        # Fallback to bot.py
        result = subprocess.run([sys.executable, "bot.py"])
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
