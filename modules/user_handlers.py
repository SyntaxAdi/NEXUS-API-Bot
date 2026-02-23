import asyncio
from datetime import datetime, timedelta
from telethon import events, TelegramClient
from telethon.tl.custom import Message
from modules.database import (
    get_user, create_user, handle_referral, check_and_reset_limits, 
    increment_search_usage, get_stats, keys_col, users_col
)
from modules.api_client import check_api_status, fetch_search_results, create_paste

# Global queue semaphore: Allows up to 10 concurrent searches to prevent overloading the backend.
search_queue_semaphore = asyncio.Semaphore(10)

async def check_premium_expiries(client: TelegramClient):
    """Background task to remind users 24h before premium expires."""
    while True:
        try:
            now = datetime.utcnow()
            alert_window = now + timedelta(days=1)
            
            # Find premium users expiring in < 24h who haven't been notified yet
            expiring_users = await users_col.find({
                "type": "premium",
                "premium_expiry": {"$gt": now, "$lte": alert_window},
                "notified_expiry": {"$ne": True}
            }).to_list(length=None)
            
            for user in expiring_users:
                try:
                    await client.send_message(
                        user["user_id"], 
                        "⚠️ **Reminder:** Your Premium access will expire in less than 24 hours!\n"
                        "Use `/account` to check your exact expiration time."
                    )
                    # Mark as notified
                    await users_col.update_one(
                        {"user_id": user["user_id"]},
                        {"$set": {"notified_expiry": True}}
                    )
                except Exception:
                    pass
                await asyncio.sleep(1)  # Spread out messages safely
        except Exception:
            pass
        
        await asyncio.sleep(3600)  # Check every hour

def register_user_handlers(client: TelegramClient):
    
    # Start the background checker
    asyncio.create_task(check_premium_expiries(client))

    @client.on(events.NewMessage(pattern=r'^/start(?: (.*))?'))
    async def start_cmd(event: Message):
        user_id = event.sender_id
        user = await get_user(user_id)
        
        if not user:
            # Handle referral logic
            ref_id_str = event.pattern_match.group(1)
            referrer_id = None
            if ref_id_str and ref_id_str.isdigit() and int(ref_id_str) != user_id:
                referrer_id = int(ref_id_str)
                reward_earned = await handle_referral(referrer_id)
                if reward_earned:
                    try:
                        await client.send_message(referrer_id, "🎉 Congratulations! 5 users joined via your link. You've earned 1 week of Premium!")
                    except:
                        pass
            
            await create_user(user_id, referrer_id)
            
        bot_me = await client.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
        await event.reply(
            f"Welcome to Nexus Search Bot!\n\n"
            f"🔍 Use `/search <query>` to find data.\n"
            f"🎁 Share your referral link to earn premium: `{ref_link}`\n"
            f"(5 Referrals = 1 Week Premium)"
        )

    @client.on(events.NewMessage(pattern=r'^/search (.*)'))
    async def search_cmd(event: Message):
        user_id = event.sender_id
        query = event.pattern_match.group(1).strip()
        
        user = await get_user(user_id)
        if not user:
            user = await create_user(user_id)
            
        if user.get("is_banned"):
            return await event.reply("🚫 You are banned from using this bot.")
            
        # Check premium expiry status
        if user['type'] == 'premium':
            if user['premium_expiry'] and user['premium_expiry'] < datetime.utcnow():
                await users_col.update_one({"user_id": user_id}, {"$set": {"type": "free"}})
                user['type'] = 'free'

        # Check Limits
        limit = 5 if user['type'] == 'premium' else 1
        searches_today = await check_and_reset_limits(user)
        
        if searches_today >= limit:
            return await event.reply(f"⚠️ You have reached your daily limit of {limit} search(es). Please wait 24 hours or upgrade to premium.")

        # Check API Status
        is_ready, status_msg = await check_api_status()
        if not is_ready:
            return await event.reply(f"⏳ Backend is not ready. {status_msg} Please try again in a minute.")

        # Determine how many matches per file to request based on tier
        result_limit = 50 if user['type'] == 'premium' else 10

        wait_msg = await event.reply("🔎 You have been added to the queue. Processing...")

        # Process Queue
        async with search_queue_semaphore:
            await wait_msg.edit("🔎 Processing your query across the cluster...")
            results = await fetch_search_results(query, limit=result_limit)
            
            if not results:
                await wait_msg.edit("❌ No results found globally for your query.")
            elif all("Error" in r or "Failed" in r for r in results):
                # If everything returned was an error
                await wait_msg.edit(f"⚠️ {results[0]}")
            else:
                # Always safely paste the output securely to prevent message limit issues 
                # and to obscure data from being logged directly in Telegram chat history.
                await wait_msg.edit("📝 Generating a secure paste for your results...")
                full_text = "\n".join(results)
                paste_url = await create_paste(full_text)
                
                if paste_url:
                    await wait_msg.edit(
                        f"✅ **Found {len(results)} result(s)**\n\n"
                        f"🔗 [View Full Results Securely]({paste_url})\n\n"
                        f"⚠️ **Note:** This link will permanently self-destruct after it is opened once.", 
                        link_preview=False
                    )
                else:
                    # Fallback if pastebin fails
                    result_text = "\n".join(results[:15])
                    if len(results) > 15:
                        result_text += f"\n\n... and {len(results)-15} more lines."
                    await wait_msg.edit(f"✅ **Found {len(results)} result(s)**\n_(Pastebin upload failed)_\n\n`{result_text}`")
                
                # Update usage stats
                await increment_search_usage(user_id, len(results))

    @client.on(events.NewMessage(pattern=r'^/redeem (.*)'))
    async def redeem_cmd(event: Message):
        user_id = event.sender_id
        key_str = event.pattern_match.group(1).strip()
        
        key_doc = await keys_col.find_one({"key_string": key_str, "is_used": False})
        if not key_doc:
            return await event.reply("❌ Invalid or already used key.")
            
        # Update key
        await keys_col.update_one({"_id": key_doc["_id"]}, {"$set": {"is_used": True, "used_by": user_id}})
        
        # Apply premium to user
        user = await get_user(user_id)
        if not user:
            user = await create_user(user_id)
            
        current_expiry = user.get('premium_expiry') or datetime.utcnow()
        if current_expiry < datetime.utcnow():
            current_expiry = datetime.utcnow()
            
        new_expiry = current_expiry + timedelta(days=key_doc['duration_days'])
        
        await users_col.update_one(
            {"user_id": user_id}, 
            {"$set": {"type": "premium", "premium_expiry": new_expiry, "notified_expiry": False}}
        )
        
        await event.reply(f"✅ Successfully redeemed! You now have Premium access for {key_doc['duration_days']} days.")

    @client.on(events.NewMessage(pattern=r'^/account'))
    async def account_cmd(event: Message):
        user_id = event.sender_id
        user = await get_user(user_id)
        if not user:
            user = await create_user(user_id)
            
        referral_count = user.get('referral_count', 0)
        
        msg = f"👤 **Account Info**\n\n"
        msg += f"**ID:** `{user_id}`\n"
        msg += f"**Tier:** `{'💎 Premium' if user['type'] == 'premium' else '🆓 Free'}`\n"
        msg += f"**Referrals:** `{referral_count}` (Need {5 - (referral_count % 5)} more for 1 week Premium!)\n"
        
        if user['type'] == 'premium' and user.get('premium_expiry'):
            now = datetime.utcnow()
            expiry = user['premium_expiry']
            if expiry > now:
                diff = expiry - now
                days = diff.days
                hours, remainder = divmod(diff.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                time_left = f"{days}d {hours}h {minutes}m"
                msg += f"**Premium Ends In:** `{time_left}`\n"
            else:
                msg += "**Premium Ends In:** `Expired`\n"
        
        # Add their unique link
        bot_me = await client.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
        msg += f"\n🎁 **Referral Link:**\n`{ref_link}`"
        
        await event.reply(msg)

    @client.on(events.NewMessage(pattern=r'^/stats'))
    async def stats_cmd(event: Message):
        stats = await get_stats()
        msg = (
            "📊 **Bot Statistics**\n\n"
            f"👥 **Total Users:** {stats['total_users']}\n"
            f"🆓 **Free Users:** {stats['free_users']}\n"
            f"💎 **Premium Users:** {stats['premium_users']}\n\n"
            f"🔍 **Total Searches:** {stats['total_searches']}\n"
            f"📝 **Results Fetched:** {stats['total_results']}"
        )
        await event.reply(msg)