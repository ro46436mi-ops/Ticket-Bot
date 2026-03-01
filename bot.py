import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import random
import string
from datetime import datetime
from config import Config

# MongoDB Connection
mongo_client = pymongo.MongoClient(Config.MONGODB_URI)
db = mongo_client['ticket_bot']
tickets_col = db['tickets']
users_col = db['users']

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
    
    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Config.GUILD_ID))
        print(f"✅ Commands synced!")

bot = TicketBot()

# Helper Functions
def ticket_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# /setup Command - Panel Banane Ke Liye
@bot.tree.command(name="setup", description="🎫 Create ticket panel", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin required!", ephemeral=True)
    
    embed = discord.Embed(
        title="🎫 Ticket Support System",
        description="Click below to create a ticket!",
        color=0x00ff00
    )
    
    # Categories
    cats = ""
    for cat in Config.CATEGORIES:
        cats += f"{cat['emoji']} **{cat['name']}**\n"
    embed.add_field(name="Categories", value=cats, inline=False)
    
    # Dropdown
    class TicketSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=cat['name'], value=cat['value'], emoji=cat['emoji'])
                for cat in Config.CATEGORIES
            ]
            super().__init__(placeholder="Choose category...", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            await create_ticket(interaction, self.values[0])
    
    class TicketView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(TicketSelect())
    
    await channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message(f"✅ Panel created in {channel.mention}!", ephemeral=True)

# Ticket Create Function
async def create_ticket(interaction: discord.Interaction, category):
    await interaction.response.defer(ephemeral=True)
    
    # Check existing tickets
    existing = tickets_col.find_one({
        "user_id": str(interaction.user.id),
        "status": "open"
    })
    
    if existing:
        return await interaction.followup.send("❌ You already have an open ticket!", ephemeral=True)
    
    # Get category name
    cat_name = next((c['name'] for c in Config.CATEGORIES if c['value'] == category), "Ticket")
    
    # Create channel
    ticket_id_str = ticket_id()
    channel_name = f"ticket-{interaction.user.name[:10]}-{ticket_id_str[:4]}"
    
    # Permissions
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.guild.get_role(Config.SUPPORT_ROLE): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    
    category_channel = interaction.guild.get_channel(Config.TICKET_CATEGORY)
    
    try:
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category_channel,
            overwrites=overwrites
        )
        
        # Save to database
        tickets_col.insert_one({
            "ticket_id": ticket_id_str,
            "user_id": str(interaction.user.id),
            "channel_id": str(channel.id),
            "category": cat_name,
            "status": "open",
            "created_at": datetime.utcnow()
        })
        
        # Welcome message
        embed = discord.Embed(
            title=f"🎫 {cat_name}",
            description=f"Welcome {interaction.user.mention}!\nSupport will help you soon.",
            color=0x00ff00
        )
        embed.add_field(name="Ticket ID", value=ticket_id_str)
        embed.set_footer(text="Use buttons below")
        
        # Buttons
        class TicketButtons(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
            async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("🔒 Closing in 5 seconds...")
                tickets_col.update_one(
                    {"ticket_id": ticket_id_str},
                    {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
                )
                await asyncio.sleep(5)
                await channel.delete()
        
        await channel.send(
            content=f"<@&{Config.SUPPORT_ROLE}> {interaction.user.mention}",
            embed=embed,
            view=TicketButtons()
        )
        
        # Log
        log_channel = interaction.guild.get_channel(Config.LOG_CHANNEL)
        if log_channel:
            log_embed = discord.Embed(
                title="✅ New Ticket",
                description=f"**User:** {interaction.user}\n**Category:** {cat_name}\n**Channel:** {channel.mention}",
                color=0x00ff00
            )
            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"✅ Ticket created! {channel.mention}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# /close Command
@bot.tree.command(name="close", description="🔒 Close ticket", guild=discord.Object(id=Config.GUILD_ID))
async def close(interaction: discord.Interaction):
    ticket = tickets_col.find_one({"channel_id": str(interaction.channel.id)})
    
    if not ticket:
        return await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
    
    if ticket['status'] == 'closed':
        return await interaction.response.send_message("❌ Ticket already closed!", ephemeral=True)
    
    # Check permissions
    if not (interaction.user.guild_permissions.administrator or 
            any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles) or
            str(interaction.user.id) == ticket['user_id']):
        return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    
    await interaction.response.send_message("🔒 Closing in 5 seconds...")
    
    tickets_col.update_one(
        {"ticket_id": ticket['ticket_id']},
        {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
    )
    
    await asyncio.sleep(5)
    await interaction.channel.delete()

# /add Command
@bot.tree.command(name="add", description="➕ Add user to ticket", guild=discord.Object(id=Config.GUILD_ID))
async def add_user(interaction: discord.Interaction, user: discord.Member):
    ticket = tickets_col.find_one({"channel_id": str(interaction.channel.id), "status": "open"})
    
    if not ticket:
        return await interaction.response.send_message("❌ Not an open ticket!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to ticket!")

# /remove Command
@bot.tree.command(name="remove", description="➖ Remove user from ticket", guild=discord.Object(id=Config.GUILD_ID))
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    ticket = tickets_col.find_one({"channel_id": str(interaction.channel.id), "status": "open"})
    
    if not ticket:
        return await interaction.response.send_message("❌ Not an open ticket!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from ticket!")

# /stats Command
@bot.tree.command(name="stats", description="📊 Ticket stats", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    total = tickets_col.count_documents({})
    open_tix = tickets_col.count_documents({"status": "open"})
    closed = tickets_col.count_documents({"status": "closed"})
    
    embed = discord.Embed(title="📊 Ticket Stats", color=0x00ff00)
    embed.add_field(name="Total", value=total)
    embed.add_field(name="Open", value=open_tix)
    embed.add_field(name="Closed", value=closed)
    
    await interaction.response.send_message(embed=embed)

# /blacklist Command
@bot.tree.command(name="blacklist", description="⛔ Blacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def blacklist(interaction: discord.Interaction, user: discord.User, reason: str = "No reason"):
    db['blacklist'].insert_one({
        "user_id": str(user.id),
        "reason": reason,
        "by": str(interaction.user.id),
        "at": datetime.utcnow()
    })
    await interaction.response.send_message(f"⛔ Blacklisted {user.mention}")

# /unblacklist Command
@bot.tree.command(name="unblacklist", description="✅ Unblacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def unblacklist(interaction: discord.Interaction, user: discord.User):
    db['blacklist'].delete_one({"user_id": str(user.id)})
    await interaction.response.send_message(f"✅ Unblacklisted {user.mention}")

# Check blacklist on ticket
@bot.tree.command(name="ticket", description="🎫 Create ticket", guild=discord.Object(id=Config.GUILD_ID))
async def ticket_command(interaction: discord.Interaction):
    # Check blacklist
    blacklisted = db['blacklist'].find_one({"user_id": str(interaction.user.id)})
    if blacklisted:
        return await interaction.response.send_message(f"⛔ You're blacklisted! Reason: {blacklisted['reason']}", ephemeral=True)
    
    # Show category select
    class QuickSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=cat['name'], value=cat['value'], emoji=cat['emoji'])
                for cat in Config.CATEGORIES
            ]
            super().__init__(placeholder="Select category...", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            await create_ticket(interaction, self.values[0])
    
    view = discord.ui.View()
    view.add_item(QuickSelect())
    
    await interaction.response.send_message("📋 Choose category:", view=view, ephemeral=True)

# Run Bot
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Guild ID: {Config.GUILD_ID}')
    print(f'✅ MongoDB Connected')
    print('='*40)

import asyncio
bot.run(Config.TOKEN)
