#!/usr/bin/env python3
"""
Debug script to check environment variables in Railway
"""

import os

def main():
    print("🔍 Environment Variables Debug")
    print("=" * 40)
    
    # Check all environment variables
    all_env = dict(os.environ)
    
    # Required variables
    required_vars = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH", 
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_PHONE_NUMBER",
        "DESTINATION_CHANNEL_ID"
    ]
    
    print("📋 All Environment Variables:")
    for key, value in all_env.items():
        if any(required in key for required in required_vars):
            print(f"  {key}: {value[:10]}..." if len(str(value)) > 10 else f"  {key}: {value}")
        else:
            print(f"  {key}: [hidden]")
    
    print("\n❌ Missing Required Variables:")
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"  - {var}")
    
    if not missing:
        print("  ✅ All required variables are set!")
    
    print("\n🔧 Railway Specific Variables:")
    railway_vars = [k for k in all_env.keys() if k.startswith('RAILWAY_')]
    for var in railway_vars:
        print(f"  {var}: {all_env[var]}")

if __name__ == "__main__":
    main()
