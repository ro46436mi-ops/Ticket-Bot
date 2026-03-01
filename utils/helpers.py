"""
Helper functions for the bot
"""

import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import discord

def create_ticket_id(length: int = 8) -> str:
    """Generate a unique ticket ID"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h"
    else:
        days = seconds // 86400
        return f"{days}d"

async def create_transcript(channel: discord.TextChannel) -> Optional[str]:
    """Create a transcript of a channel"""
    try:
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{message.author.name}#{message.author.discriminator}"
            
            content = message.clean_content
            if not content and message.attachments:
                content = f"[Attachment: {message.attachments[0].url}]"
            
            messages.append(f"[{timestamp}] {author}: {content}")
        
        transcript = "\n".join(messages)
        return transcript
    except Exception as e:
        return None

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parse duration string (e.g., '7d', '24h', '30m')"""
    if not duration_str:
        return None
    
    value = int(duration_str[:-1])
    unit = duration_str[-1].lower()
    
    if unit == 'd':
        return timedelta(days=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    else:
        return None

def truncate(text: str, max_length: int = 100) -> str:
    """Truncate text to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def get_ordinal(n: int) -> str:
    """Get ordinal suffix for number"""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"
