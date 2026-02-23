import asyncio
from telethon import events, TelegramClient
from telethon.tl.custom import Message
from modules.config import ADMIN_ID

def register_help_handlers(client: TelegramClient):

    @client.on(events.NewMessage(pattern=r'^/help'))
    async def help_cmd(event: Message):
        user_id = event.sender_id
        
        user_text = (
            "🤖 **Nexus Search Bot - Help Menu**\n\n"
            "**👤 User Commands:**\n"
            "🔹 `/start` - Start the bot and get your referral link\n"
            "🔹 `/search <query>` - Search the Nexus database (Free: 10 lines/file, Premium: 50 lines/file)\n"
            "🔹 `/account` - View your tier, referral stats, and exact premium expiration time\n"
            "🔹 `/redeem <key>` - Redeem a premium access key\n"
            "🔹 `/stats` - View global bot statistics\n"
            "\n"
            "🎁 **Premium & Referrals:**\n"
            "Every 5 users that join via your referral link automatically grant you 1 Week of Premium!\n"
            "Free users get 1 search per day. Premium users get 5 searches per day."
        )

        admin_text = (
            "\n\n**👑 Admin Commands:**\n"
            "🔸 `/genkey <days>` - Generate a new premium key valid for X days\n"
            "🔸 `/ban <user_id>` - Ban a user from using the bot\n"
            "🔸 `/unban <user_id>` - Unban a previously banned user\n"
            "🔸 `/broadcast <message>` - Send a message to all users safely"
        )

        # If the user is the admin, attach the admin commands to the help text
        if user_id == ADMIN_ID:
            await event.reply(user_text + admin_text)
        else:
            await event.reply(user_text)
