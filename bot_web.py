#!/usr/bin/env python3
"""
Telegram Affiliate Link Bot - Web Server Version for Railway
"""

import asyncio
import json
import logging
import re
import os
import aiohttp
from datetime import datetime
from typing import List, Optional
from aiohttp import web

from telethon import TelegramClient, events
from telethon.tl.types import Message
import telegram


class TelegramAffiliateBot:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the bot with configuration."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        # Initialize Telethon client for monitoring
        self.client = TelegramClient(
            'sessions/bot_session',
            self.config['telegram']['api_id'],
            self.config['telegram']['api_hash'],
            device_model='Railway Bot',
            system_version='Linux',
            app_version='1.0.0',
            lang_code='en'
        )
        
        # Initialize python-telegram-bot for sending messages
        self.bot = telegram.Bot(token=self.config['telegram']['bot_token'])
        
        # Store processed message IDs to avoid duplicates
        self.processed_messages = set()
        
        self.logger.info("Telegram Affiliate Bot initialized successfully")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file or environment variables."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except FileNotFoundError:
            return self._load_from_env()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

    def _load_from_env(self) -> dict:
        """Load configuration from environment variables."""
        config = {
            "telegram": {
                "api_id": os.getenv("TELEGRAM_API_ID"),
                "api_hash": os.getenv("TELEGRAM_API_HASH"),
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
                "phone_number": os.getenv("TELEGRAM_PHONE_NUMBER")
            },
            "channels": {
                "source_channel_id": os.getenv("SOURCE_CHANNEL_ID", "@amazonindiaassociates"),
                "destination_channel_id": os.getenv("DESTINATION_CHANNEL_ID")
            },
            "affiliate": {
                "tag": os.getenv("AFFILIATE_TAG", "sharan013-21")
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO")
            }
        }
        
        required_vars = [
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_BOT_TOKEN", 
            "TELEGRAM_PHONE_NUMBER", "DESTINATION_CHANNEL_ID"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return config

    def _setup_logging(self):
        """Setup logging configuration for cloud deployment."""
        log_level = getattr(logging, self.config['logging']['level'])
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )

    # ... (rest of the bot methods remain the same as in bot.py)
    def extract_amazon_urls(self, text: str) -> List[str]:
        """Extract Amazon URLs from text."""
        amazon_patterns = [
            r'https?://(?:www\.)?amazon\.in/[^\s]+',
            r'https?://(?:www\.)?amzaff\.in/[^\s]+',
            r'https?://(?:www\.)?amzn\.to/[^\s]+',
            r'https?://(?:www\.)?amzn\.in/[^\s]+',
            r'https?://(?:www\.)?amazon\.com/[^\s]+',
            r'\bamzaff\.in/[^\s]+',
            r'\bamzn\.to/[^\s]+',
            r'\bamzn\.in/[^\s]+',
        ]
        
        urls = []
        for pattern in amazon_patterns:
            found_urls = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(found_urls)
        
        return urls

    async def follow_redirect_and_extract_product_id(self, short_url: str) -> Optional[str]:
        """Follow redirect for short Amazon links and extract product ID."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(short_url, allow_redirects=True) as response:
                    final_url = str(response.url)
                    return self.extract_product_id(final_url)
        except Exception as e:
            self.logger.warning(f"Could not follow redirect for {short_url}: {e}")
            return None

    def extract_product_id(self, amazon_url: str) -> Optional[str]:
        """Extract product ID from Amazon URL."""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/gp/product/([A-Z0-9]{10})',
            r'/product/([A-Z0-9]{10})',
            r'/d/([A-Z0-9]{10})',
            r'/([A-Z0-9]{10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, amazon_url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def create_affiliate_link(self, product_id: str) -> str:
        """Create affiliate link with the given product ID."""
        affiliate_tag = self.config['affiliate']['tag']
        return f"https://www.amazon.in/dp/{product_id}?tag={affiliate_tag}"

    async def replace_amazon_links(self, text: str) -> str:
        """Replace all Amazon links in text with affiliate links."""
        amazon_urls = self.extract_amazon_urls(text)
        
        for url in amazon_urls:
            product_id = None
            
            if url.startswith('amzaff.in/') or url.startswith('amzn.to/') or url.startswith('amzn.in/'):
                full_url = f"https://{url}"
            else:
                full_url = url
            
            if any(domain in full_url.lower() for domain in ['amzaff.in', 'amzn.to', 'amzn.in']):
                product_id = await self.follow_redirect_and_extract_product_id(full_url)
            else:
                product_id = self.extract_product_id(full_url)
            
            if product_id:
                affiliate_link = self.create_affiliate_link(product_id)
                text = text.replace(url, affiliate_link)
                self.logger.info(f"Replaced Amazon link: {url} -> {affiliate_link}")
            else:
                self.logger.warning(f"Could not extract product ID from URL: {url}")
        
        return text

    def reformat_message(self, text: str) -> str:
        """Reformat message text to make it more engaging and professional."""
        if not text:
            return text
        
        improvements = [
            (r'^([^🎉🔥⚡📱💻🎧📷📺])', r'🔥 \1'),
            (r'\b(deal|offer|sale)\b', r'🔥 \1'),
            (r'\b(amazing|great|best|top)\b', r'⭐ \1'),
            (r'\b(price|cost)\b', r'💰 \1'),
            (r'\b(discount|off|save)\b', r'💸 \1'),
            (r'\b(limited|hurry|quick)\b', r'⚡ \1'),
            (r'\b(quality|premium|exclusive)\b', r'✨ \1'),
            (r'\b(guarantee|warranty)\b', r'🛡️ \1'),
            (r'\b(free|bonus|extra)\b', r'🎁 \1'),
            (r'\b(new|latest|updated)\b', r'🆕 \1'),
        ]
        
        for pattern, replacement in improvements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        if not any(cta in text.lower() for cta in ['buy now', 'shop now', 'get it', 'grab it', 'order now', 'check out']):
            text += "\n\n🛒 **Shop Now & Save!**"
        
        if any(word in text.lower() for word in ['deal', 'offer', 'sale', 'discount', 'price']):
            if 'limited' not in text.lower() and 'hurry' not in text.lower():
                text += "\n⚡ **Limited Time Offer!**"
        
        if 'amazon' in text.lower():
            text += "\n✅ **Amazon Verified Product**"
        
        return text.strip()

    async def forward_message(self, message: Message):
        """Forward the modified message to destination channel."""
        try:
            if message.text:
                modified_text = await self.replace_amazon_links(message.text)
                reformatted_text = self.reformat_message(modified_text)
                
                await self.bot.send_message(
                    chat_id=self.config['channels']['destination_channel_id'],
                    text=reformatted_text,
                    parse_mode='Markdown'
                )
                
                self.logger.info(f"Forwarded reformatted message ID {message.id} to destination channel")
                
        except Exception as e:
            self.logger.error(f"Error forwarding message {message.id}: {e}")

    async def handle_new_message(self, event):
        """Handle new message event."""
        message = event.message
        
        if message.id in self.processed_messages:
            return
        
        if message.text and self.extract_amazon_urls(message.text):
            self.logger.info(f"New message with Amazon links detected: {message.id}")
            await self.forward_message(message)
        
        self.processed_messages.add(message.id)
        
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])

    async def start_monitoring(self):
        """Start monitoring the source channel."""
        try:
            # Try to start with existing session first
            try:
                await self.client.start(phone=self.config['telegram']['phone_number'])
                self.logger.info("Telegram client started successfully with existing session")
            except Exception as e:
                if "FloodWaitError" in str(e):
                    # Extract wait time from error
                    import re
                    wait_time = re.search(r'(\d+) seconds', str(e))
                    if wait_time:
                        wait_seconds = int(wait_time.group(1))
                        self.logger.warning(f"FloodWaitError: Waiting {wait_seconds} seconds before retry...")
                        await asyncio.sleep(wait_seconds + 10)  # Add 10 seconds buffer
                        await self.client.start(phone=self.config['telegram']['phone_number'])
                        self.logger.info("Telegram client started successfully after wait")
                    else:
                        raise e
                else:
                    raise e
            
            @self.client.on(events.NewMessage(chats=self.config['channels']['source_channel_id']))
            async def new_message_handler(event):
                await self.handle_new_message(event)
            
            self.logger.info(f"Started monitoring channel: {self.config['channels']['source_channel_id']}")
            
        except Exception as e:
            self.logger.error(f"Error in monitoring: {e}")
            raise

    async def stop(self):
        """Stop the bot and cleanup."""
        try:
            await self.client.disconnect()
            self.logger.info("Bot stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")


# Web server routes
async def health_check(request):
    """Health check endpoint for Railway."""
    return web.Response(text="OK", status=200)

async def status(request):
    """Status endpoint to show bot status."""
    return web.json_response({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "bot": "Telegram Affiliate Bot"
    })

async def start_bot_and_server():
    """Start both the bot and web server."""
    # Initialize bot
    bot = TelegramAffiliateBot()
    
    # Start bot monitoring in background
    asyncio.create_task(bot.start_monitoring())
    
    # Create web app
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/status', status)
    
    # Start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
    await site.start()
    
    print("🚀 Bot and web server started successfully!")
    print(f"🌐 Health check available at: http://localhost:{os.getenv('PORT', 8080)}/")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bot.stop()
        await runner.cleanup()


if __name__ == "__main__":
    print("🚀 Starting Telegram Affiliate Bot with Web Server...")
    print("📋 Checking environment variables...")
    
    # Debug environment variables
    print("\n🔍 Environment Variables Debug:")
    print("=" * 40)
    required_vars = [
        "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_BOT_TOKEN", 
        "TELEGRAM_PHONE_NUMBER", "DESTINATION_CHANNEL_ID"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:10]}..." if len(str(value)) > 10 else f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
    
    print("=" * 40)
    
    # Check for missing variables
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("📝 Please set these variables in your Railway dashboard")
        exit(1)
    
    print("✅ Environment variables validated")
    print("🤖 Initializing bot and web server...")
    
    # Start bot and web server
    asyncio.run(start_bot_and_server())
