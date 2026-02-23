import logging
import asyncio
from telethon import TelegramClient
from modules.config import API_ID, API_HASH, BOT_TOKEN
from modules.database import init_db
from modules.user_handlers import register_user_handlers
from modules.admin_handlers import register_admin_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("bot_main")

async def main():
    # Initialize Database
    await init_db()
    
    # Initialize Telethon Client
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    logger.info("Bot is running...")

    # Register modular handlers
    register_user_handlers(client)
    register_admin_handlers(client)

    # Run until disconnected
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())