from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from modules.config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users_col = db['users']
keys_col = db['keys']
stats_col = db['stats']

async def init_db():
    # Ensure stats document exists
    if not await stats_col.find_one({"_id": "bot_stats"}):
        await stats_col.insert_one({
            "_id": "bot_stats",
            "total_searches": 0,
            "total_results": 0
        })

async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})

async def create_user(user_id: int, referrer_id: int = None):
    user = {
        "user_id": user_id,
        "type": "free",  # 'free' or 'premium'
        "premium_expiry": None,
        "searches_today": 0,
        "last_reset": datetime.utcnow(),
        "referred_by": referrer_id,
        "referral_count": 0,
        "is_banned": False
    }
    await users_col.insert_one(user)
    return user

async def check_and_reset_limits(user):
    now = datetime.utcnow()
    # If 24 hours have passed since last reset, reset searches
    if now - user['last_reset'] >= timedelta(days=1):
        await users_col.update_one(
            {"user_id": user['user_id']},
            {"$set": {"searches_today": 0, "last_reset": now}}
        )
        return 0
    return user['searches_today']

async def increment_search_usage(user_id: int, results_count: int):
    await users_col.update_one({"user_id": user_id}, {"$inc": {"searches_today": 1}})
    await stats_col.update_one(
        {"_id": "bot_stats"},
        {"$inc": {"total_searches": 1, "total_results": results_count}}
    )

async def handle_referral(referrer_id: int):
    referrer = await get_user(referrer_id)
    if referrer:
        new_count = referrer.get('referral_count', 0) + 1
        updates = {"referral_count": new_count}
        
        # Every 5 users = 1 week premium
        if new_count % 5 == 0:
            current_expiry = referrer.get('premium_expiry') or datetime.utcnow()
            if current_expiry < datetime.utcnow():
                current_expiry = datetime.utcnow()
            
            updates['type'] = 'premium'
            updates['premium_expiry'] = current_expiry + timedelta(days=7)
            
        await users_col.update_one({"user_id": referrer_id}, {"$set": updates})
        return new_count % 5 == 0  # True if they just earned a reward
    return False

async def get_stats():
    stats = await stats_col.find_one({"_id": "bot_stats"})
    total_users = await users_col.count_documents({})
    free_users = await users_col.count_documents({"type": "free"})
    premium_users = await users_col.count_documents({"type": "premium"})
    
    return {
        "total_searches": stats.get("total_searches", 0),
        "total_results": stats.get("total_results", 0),
        "total_users": total_users,
        "free_users": free_users,
        "premium_users": premium_users
    }