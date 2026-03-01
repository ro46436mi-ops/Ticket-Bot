import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot
    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID = int(os.getenv('GUILD_ID', 0))
    
    # Channels & Roles
    TICKET_CATEGORY = int(os.getenv('TICKET_CATEGORY_ID', 0))
    SUPPORT_ROLE = int(os.getenv('SUPPORT_ROLE_ID', 0))
    BOT_ROLE = int(os.getenv('BOT_ROLE_ID', 0))
    ADMIN_ROLE = int(os.getenv('ADMIN_ROLE_ID', 0))
    LOG_CHANNEL = int(os.getenv('LOG_CHANNEL_ID', 0))
    
    # MongoDB
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # Ticket Categories
    CATEGORIES = [
        {"name": "🎮 Free Fire Panel", "value": "ff_panel", "emoji": "🎮"},
        {"name": "🆔 Free Fire IDs", "value": "ff_ids", "emoji": "🆔"},
        {"name": "🔧 Root Service", "value": "root", "emoji": "🔧"},
        {"name": "⚙️ Other", "value": "other", "emoji": "⚙️"},
        {"name": "❓ Any Queries", "value": "general", "emoji": "❓"}
    ]
