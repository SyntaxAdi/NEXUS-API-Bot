import asyncio
import uuid
from telethon import events, TelegramClient
from telethon.tl.custom import Message
from modules.config import ADMIN_ID
from modules.database import keys_col, users_col

def register_admin_handlers(client: TelegramClient):

    @client.on(events.NewMessage(pattern=r'^/genkey (\d+)'))
    async def genkey_cmd(event: Message):
        if event.sender_id != ADMIN_ID:
            return
            
        days = int(event.pattern_match.group(1))
        new_key = f"NEXUS-{str(uuid.uuid4()).upper()[:8]}"
        
        await keys_col.insert_one({
            "key_string": new_key,
            "duration_days": days,
            "is_used": False
        })
        
        await event.reply(f"✅ Key generated for {days} days:\n\n`{new_key}`")

    @client.on(events.NewMessage(pattern=r'^/ban (\d+)'))
    async def ban_cmd(event: Message):
        if event.sender_id != ADMIN_ID:
            return
            
        target_id = int(event.pattern_match.group(1))
        result = await users_col.update_one({"user_id": target_id}, {"$set": {"is_banned": True}})
        
        if result.modified_count > 0:
            await event.reply(f"✅ User {target_id} has been banned.")
        else:
            await event.reply("❌ User not found in database.")

    @client.on(events.NewMessage(pattern=r'^/unban (\d+)'))
    async def unban_cmd(event: Message):
        if event.sender_id != ADMIN_ID:
            return
            
        target_id = int(event.pattern_match.group(1))
        result = await users_col.update_one({"user_id": target_id}, {"$set": {"is_banned": False}})
        
        if result.modified_count > 0:
            await event.reply(f"✅ User {target_id} has been unbanned.")
        else:
            await event.reply("❌ User not found in database.")

    @client.on(events.NewMessage(pattern=r'^/broadcast ([\s\S]+)'))
    async def broadcast_cmd(event: Message):
        if event.sender_id != ADMIN_ID:
            return
            
        message_text = event.pattern_match.group(1)
        users = await users_col.find({}).to_list(length=None)
        total_users = len(users)
        
        if total_users == 0:
            return await event.reply("❌ No users to broadcast to.")
            
        # Spread broadcast dynamically to avoid rate limits
        await event.reply(f"📣 Starting broadcast to {total_users} users. Sending at a safe rate of ~1 message per 1.5s to avoid flood limits.")
        
        stats = {"success": 0}
        
        # Background task
        async def run_broadcast():
            for i, user in enumerate(users):
                try:
                    await client.send_message(user['user_id'], message_text)
                    stats["success"] += 1
                except Exception:
                    pass
                
                # Sleep briefly between every message 
                await asyncio.sleep(1.5)
                
                # Take a slightly longer pause every 50 messages to appease Telegram's flood limits
                if (i + 1) % 50 == 0:
                    await asyncio.sleep(10)
                
            try:
                await client.send_message(ADMIN_ID, f"✅ Broadcast finished. Reached {stats['success']}/{total_users} users.")
            except:
                pass

        # Dispatch task to not block the admin's current session loop
        asyncio.create_task(run_broadcast())