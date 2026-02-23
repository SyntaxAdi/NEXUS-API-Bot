import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nexus_bot_db")

NEXUS_API_URLS = [
    "https://aadityapawarx1-nexus-api-1.hf.space",
    "https://aadityapawarx1-nexus-api-2.hf.space",
    "https://aadityapawarx1-nexus-api-3.hf.space",
    "https://aadityapawarx1-nexus-api-4.hf.space",
    "https://aadityapawarx1-nexus-api-5.hf.space",
    "https://aadityapawarx1-nexus-api-6.hf.space",
]
NEXUS_API_KEY = os.getenv("NEXUS_API_KEY", "")

# The owner/admin Telegram User ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))