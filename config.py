import os
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

class Config:
    # Bot Configuration
    TOKEN = os.getenv('DISCORD_TOKEN')
    CLIENT_ID = int(os.getenv('DISCORD_CLIENT_ID', 0))
    CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '/')
    
    # Server Configuration
    GUILD_ID = int(os.getenv('GUILD_ID', 1344323930923601992))
    TICKET_CATEGORY = int(os.getenv('TICKET_CATEGORY_ID', 1446560952505073846))
    SUPPORT_ROLE = int(os.getenv('SUPPORT_ROLE_ID', 1446566572763381963))
    BOT_ROLE = int(os.getenv('BOT_ROLE_ID', 1446560280187244557))
    ADMIN_ROLE = int(os.getenv('ADMIN_ROLE_ID', 1396049500744847360))
    LOG_CHANNEL = int(os.getenv('LOG_CHANNEL_ID', 1446566574181056646))
    TICKET_LOG_CHANNEL = int(os.getenv('TICKET_LOG_CHANNEL_ID', 1446566574181056646))
    
    # Database
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    DB_NAME = 'ticket_bot'
    
    # Dashboard
    DASHBOARD_SECRET = os.getenv('DASHBOARD_SECRET', 'default-secret-change-this')
    PORT = int(os.getenv('PORT', 5000))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Ticket Categories (As per your requirement)
    TICKET_TYPES: List[Dict[str, Any]] = [
        {
            'label': 'Free Fire Panel',
            'value': 'freefire_panel',
            'description': 'Free Fire panel related issues and support',
            'emoji': '🎮',
            'color': 0xFF0000,  # Red
            'priority': 1
        },
        {
            'label': 'Free Fire IDs',
            'value': 'freefire_ids',
            'description': 'Free Fire ID related queries and problems',
            'emoji': '🆔',
            'color': 0x00FF00,  # Green
            'priority': 2
        },
        {
            'label': 'Root Service',
            'value': 'root_service',
            'description': 'Root service assistance and technical support',
            'emoji': '🔧',
            'color': 0x0000FF,  # Blue
            'priority': 3
        },
        {
            'label': 'Other',
            'value': 'other',
            'description': 'Other technical issues and problems',
            'emoji': '⚙️',
            'color': 0xFFFF00,  # Yellow
            'priority': 4
        },
        {
            'label': 'Any other queries',
            'value': 'general',
            'description': 'General questions and inquiries',
            'emoji': '❓',
            'color': 0xFF00FF,  # Purple
            'priority': 5
        }
    ]
    
    # Ticket Settings
    MAX_TICKETS_PER_USER = 1
    TICKET_NAME_FORMAT = "ticket-{username}-{ticket_id}"
    TICKET_CLAIM_PREFIX = "claimed"
    TICKET_TRANSCRIPT_ENABLED = True
    
    # Embed Colors
    COLOR_SUCCESS = 0x00FF00
    COLOR_ERROR = 0xFF0000
    COLOR_WARNING = 0xFFFF00
    COLOR_INFO = 0x0000FF
    
    # Messages
    WELCOME_MESSAGE = "Welcome {user}! Support team will be with you shortly.\nPlease describe your issue in detail."
    TICKET_CREATED = "✅ Ticket created! {channel}"
    TICKET_CLOSED = "🔒 Ticket closed by {user}"
    TICKET_CLAIMED = "🤚 Ticket claimed by {user}"
    NO_PERMISSION = "❌ You don't have permission to do that!"
    ALREADY_OPEN_TICKET = "❌ You already have an open ticket! Please close it first."
    BLACKLISTED = "❌ You are blacklisted from creating tickets!"
