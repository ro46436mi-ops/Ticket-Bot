import discord
from datetime import datetime
import io

def is_staff(member: discord.Member, staff_role_ids: list) -> bool:
    """Check if member has staff role or is admin/owner"""
    if member.guild_permissions.administrator:
        return True
    if member == member.guild.owner:
        return True
    return any(role.id in staff_role_ids for role in member.roles)

async def get_transcript(channel: discord.TextChannel) -> str:
    """Generate transcript of all messages in channel"""
    transcript = f"Ticket Transcript: #{channel.name}\n"
    transcript += f"Created: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript += f"Closed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript += "=" * 50 + "\n\n"
    
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        transcript += f"[{timestamp}] {message.author.name}: {message.content}\n"
        if message.attachments:
            transcript += f"  Attachments: {', '.join(a.url for a in message.attachments)}\n"
    
    return transcript

async def create_transcript_file(transcript: str, channel_name: str) -> discord.File:
    """Create a discord file from transcript"""
    return discord.File(
        io.BytesIO(transcript.encode()),
        filename=f"transcript-{channel_name}.txt"
    )
