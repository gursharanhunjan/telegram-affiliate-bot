#!/usr/bin/env python3
"""
Telegram Affiliate Link Bot - Production Version

This script monitors a source Telegram channel for new messages containing Amazon links,
replaces them with affiliate links, and forwards the modified messages to a destination channel.

Features:
- Environment variable support for cloud deployment
- Enhanced Amazon link detection (amzaff.in, amzn.to, amzn.in)
- Automatic message reformatting for better engagement
- Robust error handling and logging
- Duplicate message prevention
"""

import asyncio
import json
import logging
import re
import os
import aiohttp
from datetime import datetime
from typing import List, Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message
import telegram


class TelegramAffiliateBot:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the bot with configuration."""
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        # Initialize Telethon client for monitoring
        self.client = TelegramClient(
            'bot_session',
            self.config['telegram']['api_id'],
            self.config['telegram']['api_hash']
        )
        
        # Initialize python-telegram-bot for sending messages
        self.bot = telegram.Bot(token=self.config['telegram']['bot_token'])
        
        # Store processed message IDs to avoid duplicates
        self.processed_messages = set()
        
        self.logger.info("Telegram Affiliate Bot initialized successfully")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file or environment variables."""
        # Try to load from config file first
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger = logging.getLogger(__name__)
                return config
        except FileNotFoundError:
            # Load from environment variables for cloud deployment
            self.logger = logging.getLogger(__name__)
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
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "file": os.getenv("LOG_FILE", "bot.log")
            }
        }
        
        # Validate required environment variables
        required_vars = [
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_BOT_TOKEN", 
            "TELEGRAM_PHONE_NUMBER", "DESTINATION_CHANNEL_ID"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return config

    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = self.config['logging']
        
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler()
            ]
        )

    def extract_amazon_urls(self, text: str) -> List[str]:
        """Extract Amazon URLs from text."""
        # Enhanced pattern to match various Amazon URL formats
        amazon_patterns = [
            r'https?://(?:www\.)?amazon\.in/[^\s]+',  # Standard amazon.in
            r'https?://(?:www\.)?amzaff\.in/[^\s]+',  # Amazon affiliate links
            r'https?://(?:www\.)?amzn\.to/[^\s]+',    # Amazon short links
            r'https?://(?:www\.)?amzn\.in/[^\s]+',    # Amazon India short links
            r'https?://(?:www\.)?amazon\.com/[^\s]+', # Amazon.com (in case)
            # Short links without protocol
            r'\bamzaff\.in/[^\s]+',  # Short amzaff.in links
            r'\bamzn\.to/[^\s]+',    # Short amzn.to links
            r'\bamzn\.in/[^\s]+',    # Short amzn.in links
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
        # Enhanced patterns for various Amazon URL formats
        patterns = [
            r'/dp/([A-Z0-9]{10})',  # Standard product ID format
            r'/gp/product/([A-Z0-9]{10})',  # Alternative format
            r'/product/([A-Z0-9]{10})',  # Another format
            r'/d/([A-Z0-9]{10})',  # Short format
            r'/([A-Z0-9]{10})',  # Direct product ID
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
            
            # Add https:// if missing for short links
            if url.startswith('amzaff.in/') or url.startswith('amzn.to/') or url.startswith('amzn.in/'):
                full_url = f"https://{url}"
            else:
                full_url = url
            
            # For short links, always try to follow redirect to get product ID
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
        
        # Common improvements
        improvements = [
            # Add engaging emojis and formatting
            (r'^([^🎉🔥⚡📱💻🎧📷📺])', r'🔥 \1'),  # Add fire emoji to start if not present
            (r'\b(deal|offer|sale)\b', r'🔥 \1'),  # Emphasize deals
            (r'\b(amazing|great|best|top)\b', r'⭐ \1'),  # Emphasize positive words
            (r'\b(price|cost)\b', r'💰 \1'),  # Add money emoji
            (r'\b(discount|off|save)\b', r'💸 \1'),  # Add savings emoji
            (r'\b(limited|hurry|quick)\b', r'⚡ \1'),  # Add urgency
            (r'\b(quality|premium|exclusive)\b', r'✨ \1'),  # Add premium feel
            (r'\b(guarantee|warranty)\b', r'🛡️ \1'),  # Add trust
            (r'\b(free|bonus|extra)\b', r'🎁 \1'),  # Add gift emoji
            (r'\b(new|latest|updated)\b', r'🆕 \1'),  # Add new indicator
            (r'\b(review|rating|star)\b', r'⭐ \1'),  # Add star for reviews
            (r'\b(camera|photo|video)\b', r'📸 \1'),  # Add camera emoji
            (r'\b(audio|sound|music)\b', r'🎵 \1'),  # Add music emoji
            (r'\b(gaming|game)\b', r'🎮 \1'),  # Add gaming emoji
            (r'\b(fitness|health|workout)\b', r'💪 \1'),  # Add fitness emoji
            (r'\b(beauty|skincare|makeup)\b', r'💄 \1'),  # Add beauty emoji
            (r'\b(kitchen|cooking|food)\b', r'🍳 \1'),  # Add kitchen emoji
            (r'\b(home|house|living)\b', r'🏠 \1'),  # Add home emoji
            (r'\b(travel|vacation|trip)\b', r'✈️ \1'),  # Add travel emoji
            (r'\b(tech|technology|smart)\b', r'🤖 \1'),  # Add tech emoji
        ]
        
        # Apply improvements
        for pattern, replacement in improvements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Add call-to-action if not present
        if not any(cta in text.lower() for cta in ['buy now', 'shop now', 'get it', 'grab it', 'order now', 'check out']):
            text += "\n\n🛒 **Shop Now & Save!**"
        
        # Add urgency if price-related words are present
        if any(word in text.lower() for word in ['deal', 'offer', 'sale', 'discount', 'price']):
            if 'limited' not in text.lower() and 'hurry' not in text.lower():
                text += "\n⚡ **Limited Time Offer!**"
        
        # Add trust indicators
        if 'amazon' in text.lower():
            text += "\n✅ **Amazon Verified Product**"
        
        # Format product lists better
        if re.search(r'\d+\.', text):
            text = re.sub(r'(\d+\.)', r'\n\1', text)
        
        # Add line breaks for better readability
        text = re.sub(r'(\*\*[^*]+\*\*)', r'\n\1', text)
        
        return text.strip()

    async def forward_message(self, message: Message):
        """Forward the modified message to destination channel."""
        try:
            # Get message text
            if message.text:
                # First replace Amazon links
                modified_text = await self.replace_amazon_links(message.text)
                
                # Then reformat the message for better engagement
                reformatted_text = self.reformat_message(modified_text)
                
                # Send the reformatted message
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
        
        # Skip if message already processed
        if message.id in self.processed_messages:
            return
        
        # Check if message contains Amazon links
        if message.text and self.extract_amazon_urls(message.text):
            self.logger.info(f"New message with Amazon links detected: {message.id}")
            await self.forward_message(message)
        
        # Mark message as processed
        self.processed_messages.add(message.id)
        
        # Keep only last 1000 processed messages to prevent memory issues
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])

    async def start_monitoring(self):
        """Start monitoring the source channel."""
        try:
            # Start the client
            await self.client.start(phone=self.config['telegram']['phone_number'])
            self.logger.info("Telegram client started successfully")
            
            # Register event handler for new messages
            @self.client.on(events.NewMessage(chats=self.config['channels']['source_channel_id']))
            async def new_message_handler(event):
                await self.handle_new_message(event)
            
            self.logger.info(f"Started monitoring channel: {self.config['channels']['source_channel_id']}")
            
            # Keep the client running
            await self.client.run_until_disconnected()
            
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


async def main():
    """Main function to run the bot."""
    bot = None
    try:
        bot = TelegramAffiliateBot()
        await bot.start_monitoring()
    except KeyboardInterrupt:
        print("\nBot interrupted by user")
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        if bot:
            await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
