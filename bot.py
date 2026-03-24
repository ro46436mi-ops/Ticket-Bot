import discord
from discord.ext import commands
from datetime import datetime
import config
from utils.helpers import is_staff, get_transcript

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user}")
    print(f"📡 Guild ID: {config.GUILD_ID}")
    print(f"👥 Staff Roles: {config.STAFF_ROLE_IDS}")
    
    # Sync commands
    await bot.tree.sync(guild=discord.Object(id=config.GUILD_ID))
    print("✅ Commands synced!")
    
    # Load cogs
    await bot.load_extension("cogs.ticket")
    print("✅ Ticket cog loaded!")

@bot.event
async def on_member_remove(member: discord.Member):
    """Send goodbye embed when member leaves"""
    if member.guild.id != config.GUILD_ID:
        return
    
    channel = bot.get_channel(config.LEAVE_CHANNEL_ID)
    if not channel:
        return
    
    # Get current member count
    member_count = member.guild.member_count
    
    # Create timestamp
    timestamp = int(datetime.now().timestamp())
    
    embed = discord.Embed(
        title="GOODBYE FROM SM GrowMart HQ!",
        description=f"<@{member.id}> just Ek Randi Ke Bachche Left server. <a:FuckedbyDigamber:1398951734671442071>",
        color=0xff0000
    )
    
    embed.add_field(
        name="• Last Seen",
        value=f"<t:{timestamp}> (<t:{timestamp}:R>)",
        inline=False
    )
    embed.add_field(
        name="• Members Left",
        value=str(member_count),
        inline=False
    )
    
    embed.set_footer(text=f"Powered by Digamber fuckner 👺 | {datetime.now().strftime('%m/%d/%Y')}")
    
    await channel.send(embed=embed)

# ===== RUN BOT =====
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        print("❌ Error: BOT_TOKEN not found in .env file!")
        exit(1)
    
    bot.run(TOKEN)
