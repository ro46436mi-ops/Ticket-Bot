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

# ========== HEALTH SERVER FOR RENDER ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Ticket Bot Online</h1><p>Status: Online</p><p>Bot is running!</p></body></html>")
    
    def log_message(self, format, *args):
        return

def run_health_server():
    try:
        port = int(os.getenv('PORT', 10000))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        print(f"✅ Health server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health server error: {e}")

# Start health server
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
    tickets_col = None
    blacklist_col = None

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
    
    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=Config.GUILD_ID))
        print(f"✅ Commands synced!")

bot = TicketBot()

# ========== HELPER FUNCTIONS ==========
def generate_ticket_id():
    """Generate unique ticket ID"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_category_name(category_value):
    """Get category name from value"""
    for cat in Config.CATEGORIES:
        if cat['value'] == category_value:
            return cat['name']
    return "Ticket"

# ========== TICKET CREATION FUNCTION ==========
async def create_ticket(interaction: discord.Interaction, category_value):
    """Create a new ticket channel"""
    
    # Defer response
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check blacklist
        if blacklist_col is not None:
            blacklisted = blacklist_col.find_one({"user_id": str(interaction.user.id)})
            if blacklisted:
                return await interaction.followup.send(
                    f"⛔ You are blacklisted!\nReason: {blacklisted.get('reason', 'No reason')}", 
                    ephemeral=True
                )
        
        # Check existing tickets
        if tickets_col is not None:
            existing = tickets_col.find_one({
                "user_id": str(interaction.user.id),
                "status": "open"
            })
            
            if existing:
                return await interaction.followup.send(
                    "❌ You already have an open ticket!", 
                    ephemeral=True
                )
        
        # Get category name
        cat_name = get_category_name(category_value)
        
        # Get guild and channels
        guild = interaction.guild
        category_channel = guild.get_channel(Config.TICKET_CATEGORY)
        support_role = guild.get_role(Config.SUPPORT_ROLE)
        
        if not category_channel:
            return await interaction.followup.send(
                "❌ Ticket category not found! Contact admin.", 
                ephemeral=True
            )
        
        # Generate IDs
        ticket_id_str = generate_ticket_id()
        channel_name = f"ticket-{interaction.user.name[:10]}-{ticket_id_str[:4]}"
        
        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True,
                read_message_history=True,
                attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True, 
                manage_channels=True,
                manage_messages=True
            )
        }
        
        # Add support role if exists
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )
        
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
        
        # Create welcome embed
        embed = discord.Embed(
            title=f"🎫 New Ticket - {cat_name}",
            description=f"Welcome {interaction.user.mention}!\nSupport team will help you soon.\n\n**Please describe your issue in detail.**",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Ticket ID", value=f"`{ticket_id_str}`", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(datetime.utcnow(), 'R'), inline=True)
        embed.set_footer(text="Use buttons below to manage ticket")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        # Create buttons view
        class TicketButtons(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
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
                
                # Confirm close
                class ConfirmView(discord.ui.View):
                    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
                    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
                        
                        if tickets_col is not None:
                            tickets_col.update_one(
                                {"channel_id": str(interaction.channel.id)},
                                {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
                            )
                        
                        await asyncio.sleep(5)
                        await interaction.channel.delete()
                    
                    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.edit_message(content="✅ Close cancelled", view=None)
                
                await interaction.response.send_message("⚠️ Are you sure you want to close this ticket?", view=ConfirmView(), ephemeral=True)
        
        # Send welcome message
        await channel.send(
            content=f"{support_role.mention if support_role else '@Support'} • {interaction.user.mention}",
            embed=embed,
            view=TicketButtons()
        )
        
        # Send info message and pin it
        info_msg = await channel.send(
            "📌 **Ticket Information**\n"
            "• Please describe your issue in detail\n"
            "• Support team will assist you shortly\n"
            "• Do not ping staff members unnecessarily\n"
            "• Click the Close button when done"
        )
        await info_msg.pin()
        
        # Log to log channel
        log_channel = guild.get_channel(Config.LOG_CHANNEL)
        if log_channel:
            log_embed = discord.Embed(
                title="✅ New Ticket Created",
                description=f"**User:** {interaction.user.mention}\n"
                          f"**Category:** {cat_name}\n"
                          f"**Channel:** {channel.mention}\n"
                          f"**Ticket ID:** `{ticket_id_str}`",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=log_embed)
        
        # Send success message
        await interaction.followup.send(
            f"✅ Ticket created! {channel.mention}", 
            ephemeral=True
        )
        
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to create channels! Check my permissions.", 
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error: {str(e)}", 
            ephemeral=True
        )
        print(f"Error in create_ticket: {e}")

# ========== COMMANDS ==========

# /setup Command
@bot.tree.command(name="setup", description="🎫 Create ticket panel", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    # Defer immediately - 15 minute timeout
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Create embed
        embed = discord.Embed(
            title="🎫 Ticket Support System",
            description="Click the dropdown below to create a support ticket!",
            color=0x00ff00
        )
        
        # Add categories
        cats_text = ""
        for cat in Config.CATEGORIES:
            cats_text += f"{cat['emoji']} **{cat['name']}**\n"
        embed.add_field(name="Available Categories", value=cats_text, inline=False)
        
        embed.set_footer(text="Support team will assist you shortly")
        embed.timestamp = datetime.utcnow()
        
        # Create dropdown
        class TicketSelect(discord.ui.Select):
            def __init__(self):
                options = []
                for cat in Config.CATEGORIES:
                    options.append(discord.SelectOption(
                        label=cat['name'], 
                        value=cat['value'], 
                        emoji=cat['emoji'],
                        description=f"Create {cat['name']} ticket"
                    ))
                super().__init__(
                    placeholder="📋 Choose ticket category...", 
                    options=options,
                    min_values=1,
                    max_values=1
                )
            
            async def callback(self, interaction: discord.Interaction):
                await create_ticket(interaction, self.values[0])
        
        # Create view with dropdown
        view = discord.ui.View(timeout=None)
        view.add_item(TicketSelect())
        
        # Send panel
        await channel.send(embed=embed, view=view)
        
        # Send success message
        await interaction.followup.send(f"✅ Ticket panel created in {channel.mention}!", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# /ticket Command
@bot.tree.command(name="ticket", description="🎫 Create a new ticket", guild=discord.Object(id=Config.GUILD_ID))
async def ticket_command(interaction: discord.Interaction):
    # Check blacklist
    if blacklist_col is not None:
        blacklisted = blacklist_col.find_one({"user_id": str(interaction.user.id)})
        if blacklisted:
            return await interaction.response.send_message(
                f"⛔ You're blacklisted! Reason: {blacklisted.get('reason', 'No reason')}", 
                ephemeral=True
            )
    
    # Create category selection
    class QuickSelect(discord.ui.Select):
        def __init__(self):
            options = []
            for cat in Config.CATEGORIES:
                options.append(discord.SelectOption(
                    label=cat['name'], 
                    value=cat['value'], 
                    emoji=cat['emoji']
                ))
            super().__init__(placeholder="Select category...", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            await create_ticket(interaction, self.values[0])
    
    view = discord.ui.View()
    view.add_item(QuickSelect())
    
    await interaction.response.send_message("📋 Choose category:", view=view, ephemeral=True)

# /close Command
@bot.tree.command(name="close", description="🔒 Close current ticket", guild=discord.Object(id=Config.GUILD_ID))
async def close(interaction: discord.Interaction):
    # Check if in ticket channel
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
    
    # Get ticket data
    ticket_data = None
    if tickets_col is not None:
        ticket_data = tickets_col.find_one({"channel_id": str(interaction.channel.id)})
    
    # Check permissions
    has_permission = (
        interaction.user.guild_permissions.administrator or
        any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles) or
        (ticket_data and str(interaction.user.id) == ticket_data['user_id'])
    )
    
    if not has_permission:
        return await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
    
    # Simple confirm
    await interaction.response.send_message("🔒 Closing in 5 seconds...")
    
    if tickets_col is not None:
        tickets_col.update_one(
            {"channel_id": str(interaction.channel.id)},
            {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
        )
    
    await asyncio.sleep(5)
    await interaction.channel.delete()

# /add Command
@bot.tree.command(name="add", description="➕ Add user to ticket", guild=discord.Object(id=Config.GUILD_ID))
async def add_user(interaction: discord.Interaction, user: discord.Member):
    # Check if in ticket channel
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
    
    # Check permissions
    if not (interaction.user.guild_permissions.administrator or 
            any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles)):
        return await interaction.response.send_message("❌ Support role required!", ephemeral=True)
    
    # Add user
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to ticket!")

# /remove Command
@bot.tree.command(name="remove", description="➖ Remove user from ticket", guild=discord.Object(id=Config.GUILD_ID))
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    # Check if in ticket channel
    if not interaction.channel.name.startswith('ticket-'):
        return await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
    
    # Check permissions
    if not (interaction.user.guild_permissions.administrator or 
            any(role.id == Config.SUPPORT_ROLE for role in interaction.user.roles)):
        return await interaction.response.send_message("❌ Support role required!", ephemeral=True)
    
    # Remove user
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from ticket!")

# /stats Command
@bot.tree.command(name="stats", description="📊 View ticket statistics", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    if tickets_col is None:
        return await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
    
    total = tickets_col.count_documents({})
    open_tix = tickets_col.count_documents({"status": "open"})
    closed = tickets_col.count_documents({"status": "closed"})
    
    embed = discord.Embed(
        title="📊 Ticket Statistics", 
        color=0x00ff00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Total Tickets", value=total, inline=True)
    embed.add_field(name="Open Tickets", value=open_tix, inline=True)
    embed.add_field(name="Closed Tickets", value=closed, inline=True)
    
    await interaction.response.send_message(embed=embed)

# /blacklist Command
@bot.tree.command(name="blacklist", description="⛔ Blacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def blacklist(interaction: discord.Interaction, user: discord.User, reason: str = "No reason"):
    if blacklist_col is None:
        return await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
    
    blacklist_col.insert_one({
        "user_id": str(user.id),
        "reason": reason,
        "blacklisted_by": str(interaction.user.id),
        "blacklisted_at": datetime.utcnow()
    })
    
    embed = discord.Embed(
        title="⛔ User Blacklisted",
        description=f"**User:** {user.mention}\n**Reason:** {reason}",
        color=0xff0000
    )
    await interaction.response.send_message(embed=embed)

# /unblacklist Command
@bot.tree.command(name="unblacklist", description="✅ Unblacklist user", guild=discord.Object(id=Config.GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def unblacklist(interaction: discord.Interaction, user: discord.User):
    if blacklist_col is None:
        return await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
    
    result = blacklist_col.delete_one({"user_id": str(user.id)})
    
    if result.deleted_count > 0:
        await interaction.response.send_message(f"✅ Unblacklisted {user.mention}")
    else:
        await interaction.response.send_message(f"❌ {user.mention} is not blacklisted")

# /help Command
@bot.tree.command(name="help", description="📋 Show all commands", guild=discord.Object(id=Config.GUILD_ID))
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📋 Ticket Bot Commands",
        description="Here are all available commands:",
        color=0x00ff00
    )
    
    embed.add_field(
        name="👤 User Commands",
        value="`/ticket` - Create a new ticket\n`/close` - Close your ticket",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Support Commands",
        value="`/add @user` - Add user to ticket\n`/remove @user` - Remove user from ticket",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin Commands",
        value="`/setup #channel` - Create ticket panel\n`/stats` - View statistics\n`/blacklist @user` - Blacklist user\n`/unblacklist @user` - Unblacklist user",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== EVENT HANDLERS ==========

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'✅ Bot ID: {bot.user.id}')
    print(f'✅ Guild ID: {Config.GUILD_ID}')
    print('='*50)
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🎫 Tickets | /setup"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Save messages in ticket channels
    if tickets_col is not None and message.channel.name and message.channel.name.startswith('ticket-'):
        tickets_col.update_one(
            {"channel_id": str(message.channel.id)},
            {
                "$push": {
                    "messages": {
                        "user_id": str(message.author.id),
                        "content": message.content,
                        "attachments": [a.url for a in message.attachments] if message.attachments else [],
                        "timestamp": datetime.utcnow()
                    }
                }
            }
        )
    
    await bot.process_commands(message)

# ========== RUN BOT ==========
if __name__ == "__main__":
    try:
        bot.run(Config.TOKEN)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
