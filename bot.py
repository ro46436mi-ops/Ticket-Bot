import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import random
import string
from datetime import datetime
from config import Config
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== HEALTH SERVER FOR RENDER (FINAL FIX) ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # SUPER SIMPLE - no special chars, no fancy styling
        self.wfile.write(b"<html><body><h1>Ticket Bot Online</h1><p>Status: Online</p><p>Use /setup in Discord</p></body></html>")
    
    def log_message(self, format, *args):
        return  # Disable logging

def run_health_server():
    try:
        port = int(os.getenv('PORT', 10000))  # Render ka PORT use karo
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        print(f"✅ Health server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health server error: {e}")

# Start health server in background
Thread(target=run_health_server, daemon=True).start()

# ========== MONGODB CONNECTION ==========
try:
    mongo_client = pymongo.MongoClient(Config.MONGODB_URI)
    db = mongo_client['ticket_bot']
    tickets_col = db['tickets']
    users_col = db['users']
    blacklist_col = db['blacklist']
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    db = None
    tickets_col = None
    blacklist_col = None

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ========== HELPER FUNCTIONS ==========
def generate_ticket_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_category_name(category_value):
    for cat in Config.CATEGORIES:
        if cat['value'] == category_value:
            return cat['name']
    return "Ticket"

# ========== TICKET CREATION FUNCTION ==========
async def create_ticket(interaction: discord.Interaction, category_value):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check blacklist
        if blacklist_col is not None:
            blacklisted = blacklist_col.find_one({"user_id": str(interaction.user.id)})
            if blacklisted:
                return await interaction.followup.send(f"⛔ You are blacklisted!\nReason: {blacklisted.get('reason', 'No reason')}", ephemeral=True)
        
        # Check existing tickets
        if tickets_col is not None:
            existing = tickets_col.find_one({"user_id": str(interaction.user.id), "status": "open"})
            if existing:
                return await interaction.followup.send("❌ You already have an open ticket!", ephemeral=True)
        
        cat_name = get_category_name(category_value)
        guild = interaction.guild
        category_channel = guild.get_channel(Config.TICKET_CATEGORY)
        support_role = guild.get_role(Config.SUPPORT_ROLE)
        
        if not category_channel:
            return await interaction.followup.send("❌ Ticket category not found! Contact admin.", ephemeral=True)
        
        ticket_id_str = generate_ticket_id()
        channel_name = f"ticket-{interaction.user.name[:10]}-{ticket_id_str[:4]}"
        
        # Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, manage_messages=True)
        
        # Create channel
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category_channel,
            overwrites=overwrites,
            topic=f"Ticket: {ticket_id_str} | User: {interaction.user} | Category: {cat_name}"
        )
        
        # Save to database
        if tickets_col is not None:
            tickets_col.insert_one({
                "ticket_id": ticket_id_str,
                "user_id": str(interaction.user.id),
                "channel_id": str(channel.id),
                "category": cat_name,
                "status": "open",
                "created_at": datetime.utcnow(),
                "messages": []
            })
        
        # Welcome embed
        embed = discord.Embed(
            title=f"🎫 New Ticket - {cat_name}",
            description=f"Welcome {interaction.user.mention}!\nSupport team will help you soon.\n\n**Please describe your issue in detail.**",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Ticket ID", value=f"`{ticket_id_str}`", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(datetime.utcnow(), 'R'), inline=True)
        embed.set_footer(text="Use buttons below to manage ticket")
        
        # Close button
        class CloseButton(discord.ui.View):
            @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
            async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Check permissions
                ticket_data = None
                if tickets_col is not None:
                    ticket_data = tickets_col.find_one({"channel_id": str(interaction.channel.id)})
                
                has_permission = (
                    interaction.user.guild_permissions.administrator or
                    any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles) or
                    (ticket_data and str(interaction.user.id) == ticket_data['user_id'])
                )
                
                if not has_permission:
                    return await interaction.response.send_message("❌ No permission!", ephemeral=True)
                
                # Confirm
                confirm_view = discord.ui.View()
                
                async def confirm(interaction: discord.Interaction):
                    await interaction.response.send_message("🔒 Closing in 5 seconds...")
                    if tickets_col is not None:
                        tickets_col.update_one(
                            {"channel_id": str(interaction.channel.id)},
                            {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
                        )
                    await asyncio.sleep(5)
                    await interaction.channel.delete()
                
                async def cancel(interaction: discord.Interaction):
                    await interaction.response.edit_message(content="✅ Close cancelled", view=None)
                
                confirm_button = discord.ui.Button(label="Yes, Close", style=discord.ButtonStyle.danger)
                cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
                confirm_button.callback = confirm
                cancel_button.callback = cancel
                confirm_view.add_item(confirm_button)
                confirm_view.add_item(cancel_button)
                
                await interaction.response.send_message("⚠️ Are you sure?", view=confirm_view, ephemeral=True)
        
        # Send messages
        await channel.send(content=f"{support_role.mention if support_role else '@Support'} • {interaction.user.mention}", embed=embed, view=CloseButton())
        info_msg = await channel.send("📌 **Ticket Information**\n• Describe your issue\n• Support will help you\n• Click Close when done")
        await info_msg.pin()
        
        # Log
        log_channel = guild.get_channel(Config.LOG_CHANNEL)
        if log_channel:
            log_embed = discord.Embed(title="✅ New Ticket", description=f"**User:** {interaction.user.mention}\n**Category:** {cat_name}\n**Channel:** {channel.mention}\n**ID:** `{ticket_id_str}`", color=0x00ff00)
            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"✅ Ticket created! {channel.mention}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        print(f"Error: {e}")

# ========== COMMANDS ==========

@bot.tree.command(name="setup", description="🎫 Create ticket panel", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin required!", ephemeral=True)
    
    await interaction.response.send_message("⏳ Creating panel...", ephemeral=True)
    
    try:
        embed = discord.Embed(title="🎫 Ticket Support System", description="Click dropdown to create ticket!", color=0x00ff00)
        
        cats_text = ""
        for cat in Config.CATEGORIES:
            cats_text += f"{cat['emoji']} **{cat['name']}**\n"
        embed.add_field(name="Categories", value=cats_text, inline=False)
        
        # Dropdown
        class TicketSelect(discord.ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label=cat['name'], value=cat['value'], emoji=cat['emoji']) for cat in Config.CATEGORIES]
                super().__init__(placeholder="Choose category...", options=options)
            
            async def callback(self, interaction: discord.Interaction):
                await create_ticket(interaction, self.values[0])
        
        view = discord.ui.View(timeout=None)
        view.add_item(TicketSelect())
        
        await channel.send(embed=embed, view=view)
        await interaction.edit_original_response(content=f"✅ Panel created in {channel.mention}!")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ Error: {str(e)}")

@bot.tree.command(name="ticket", description="🎫 Create ticket", guild=discord.Object(id=Config.GUILD_ID))
async def ticket_command(interaction: discord.Interaction):
    if blacklist_col is not None:
        blacklisted = blacklist_col.find_one({"user_id": str(interaction.user.id)})
        if blacklisted:
            return await interaction.response.send_message(f"⛔ Blacklisted! Reason: {blacklisted.get('reason', 'N/A')}", ephemeral=True)
    
    class QuickSelect(discord.ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=cat['name'], value=cat['value'], emoji=cat['emoji']) for cat in Config.CATEGORIES]
            super().__init__(placeholder="Select category...", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            await create_ticket(interaction, self.values[0])
    
    view = discord.ui.View()
    view.add_item(QuickSelect())
    await interaction.response.send_message("📋 Choose category:", view=view, ephemeral=True)

@bot.tree.command(name="close", description="🔒 Close ticket", guild=discord.Object(id=Config.GUILD_ID))
async def close(interaction: discord.Interaction):
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
    
    ticket_data = None
    if tickets_col is not None:
        ticket_data = tickets_col.find_one({"channel_id": str(interaction.channel.id)})
    
    has_permission = (
        interaction.user.guild_permissions.administrator or
        any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles) or
        (ticket_data and str(interaction.user.id) == ticket_data['user_id'])
    )
    
    if not has_permission:
        return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    
    # Simple confirm
    await interaction.response.send_message("🔒 Closing in 5 seconds...")
    if tickets_col is not None:
        tickets_col.update_one(
            {"channel_id": str(interaction.channel.id)},
            {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
        )
    await asyncio.sleep(5)
    await interaction.channel.delete()

@bot.tree.command(name="add", description="➕ Add user", guild=discord.Object(id=Config.GUILD_ID))
async def add_user(interaction: discord.Interaction, user: discord.Member):
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
    
    if not (interaction.user.guild_permissions.administrator or any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles)):
        return await interaction.response.send_message("❌ Support role required!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
    await interaction.response.send_message(f"✅ Added {user.mention}")

@bot.tree.command(name="remove", description="➖ Remove user", guild=discord.Object(id=Config.GUILD_ID))
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
    
    if not (interaction.user.guild_permissions.administrator or any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles)):
        return await interaction.response.send_message("❌ Support role required!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention}")

@bot.tree.command(name="stats", description="📊 Statistics", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    if tickets_col is None:
        return await interaction.response.send_message("❌ DB not connected!", ephemeral=True)
    
    total = tickets_col.count_documents({})
    open_tix = tickets_col.count_documents({"status": "open"})
    closed = tickets_col.count_documents({"status": "closed"})
    
    embed = discord.Embed(title="📊 Ticket Stats", color=0x00ff00)
    embed.add_field(name="Total", value=total)
    embed.add_field(name="Open", value=open_tix)
    embed.add_field(name="Closed", value=closed)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="blacklist", description="⛔ Blacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def blacklist(interaction: discord.Interaction, user: discord.User, reason: str = "No reason"):
    if blacklist_col is None:
        return await interaction.response.send_message("❌ DB not connected!", ephemeral=True)
    
    blacklist_col.insert_one({
        "user_id": str(user.id),
        "reason": reason,
        "blacklisted_by": str(interaction.user.id),
        "blacklisted_at": datetime.utcnow()
    })
    
    await interaction.response.send_message(f"⛔ Blacklisted {user.mention}")

@bot.tree.command(name="unblacklist", description="✅ Unblacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def unblacklist(interaction: discord.Interaction, user: discord.User):
    if blacklist_col is None:
        return await interaction.response.send_message("❌ DB not connected!", ephemeral=True)
    
    result = blacklist_col.delete_one({"user_id": str(user.id)})
    if result.deleted_count > 0:
        await interaction.response.send_message(f"✅ Unblacklisted {user.mention}")
    else:
        await interaction.response.send_message(f"❌ Not blacklisted")

@bot.tree.command(name="help", description="📋 Show commands", guild=discord.Object(id=Config.GUILD_ID))
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Ticket Bot Commands", color=0x00ff00)
    embed.add_field(name="👤 User", value="`/ticket` - Create ticket\n`/close` - Close ticket", inline=False)
    embed.add_field(name="🛠️ Support", value="`/add @user` - Add user\n`/remove @user` - Remove user", inline=False)
    embed.add_field(name="⚙️ Admin", value="`/setup #channel` - Setup\n`/stats` - Stats\n`/blacklist @user` - Block\n`/unblacklist @user` - Unblock", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== EVENTS ==========

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Guild ID: {Config.GUILD_ID}')
    print(f'✅ MongoDB: {"Connected" if tickets_col is not None else "Disconnected"}')
    print('='*50)
    
    # Sync commands
    try:
        await bot.tree.sync(guild=discord.Object(id=Config.GUILD_ID))
        print("✅ Commands synced!")
    except Exception as e:
        print(f"❌ Command sync error: {e}")
    
    # Set status
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="🎫 Tickets"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Save messages
    if tickets_col is not None and message.channel.name and message.channel.name.startswith('ticket-'):
        tickets_col.update_one(
            {"channel_id": str(message.channel.id)},
            {"$push": {"messages": {
                "user_id": str(message.author.id),
                "content": message.content,
                "attachments": [a.url for a in message.attachments] if message.attachments else [],
                "timestamp": datetime.utcnow()
            }}}
        )
    
    await bot.process_commands(message)

# ========== RUN ==========
if __name__ == "__main__":
    try:
        bot.run(Config.TOKEN)
    except Exception as e:
        print(f"❌ Failed: {e}")
