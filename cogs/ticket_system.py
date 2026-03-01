"""
Ticket System Cog - Fixed Version with Error Handling
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import string
from datetime import datetime
import logging
import traceback

from config import Config
from database.mongodb import Database
from utils.helpers import create_ticket_id, format_duration, create_transcript

logger = logging.getLogger(__name__)

class TicketView(discord.ui.View):
    """View with ticket control buttons"""
    
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🤚", custom_id="claim_ticket")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Claim ticket button"""
        await interaction.response.defer(ephemeral=True)
        await interaction.client.get_cog('TicketSystem').handle_claim(interaction, self.ticket_id)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket button"""
        await interaction.response.defer(ephemeral=True)
        await interaction.client.get_cog('TicketSystem').handle_close(interaction, self.ticket_id)
    
    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript_ticket")
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Generate transcript button"""
        await interaction.response.defer(ephemeral=True)
        await interaction.client.get_cog('TicketSystem').handle_transcript(interaction, self.ticket_id)

class CategorySelect(discord.ui.Select):
    """Category selection dropdown"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label=cat['label'],
                description=cat['description'][:50] if len(cat['description']) > 50 else cat['description'],
                value=cat['value'],
                emoji=cat['emoji']
            ) for cat in Config.TICKET_TYPES
        ]
        super().__init__(
            placeholder="📋 Select ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="category_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        await interaction.response.defer(ephemeral=True)
        await interaction.client.get_cog('TicketSystem').create_ticket_channel(
            interaction, self.values[0]
        )

class TicketSystem(commands.Cog):
    """Main ticket system cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.active_tickets = {}
    
    @app_commands.command(name="ticket", description="🎫 Create a new support ticket")
    async def create_ticket(self, interaction: discord.Interaction):
        """Create a new ticket command"""
        
        # IMMEDIATELY defer the response to prevent timeout
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # Check blacklist
            if await self.db.is_blacklisted(str(interaction.user.id)):
                embed = discord.Embed(
                    title="⛔ Access Denied",
                    description="You are blacklisted from creating tickets!",
                    color=Config.COLOR_ERROR
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Check existing tickets
            user_tickets = await self.db.get_user_tickets(str(interaction.user.id), "open")
            
            if len(user_tickets) >= Config.MAX_TICKETS_PER_USER:
                embed = discord.Embed(
                    title="❌ Maximum Tickets Reached",
                    description=f"You already have {len(user_tickets)} open ticket(s).\n"
                              f"Please close your existing ticket before creating a new one.",
                    color=Config.COLOR_WARNING
                )
                
                # Add list of existing tickets
                if user_tickets:
                    ticket_list = "\n".join([
                        f"• <#{t['channel_id']}> ({t['category']})"
                        for t in user_tickets[:5]
                    ])
                    embed.add_field(name="Your Open Tickets", value=ticket_list, inline=False)
                
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Show category selection
            view = discord.ui.View(timeout=60)
            view.add_item(CategorySelect())
            
            embed = discord.Embed(
                title="🎫 Create a Ticket",
                description="Please select a category for your ticket:",
                color=Config.COLOR_INFO
            )
            
            # Add category descriptions
            for cat in Config.TICKET_TYPES:
                embed.add_field(
                    name=f"{cat['emoji']} {cat['label']}",
                    value=cat['description'][:50] + "..." if len(cat['description']) > 50 else cat['description'],
                    inline=True
                )
            
            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in create_ticket: {e}\n{traceback.format_exc()}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=Config.COLOR_ERROR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def create_ticket_channel(self, interaction: discord.Interaction, category_value: str):
        """Create the actual ticket channel"""
        
        try:
            # Get category info
            category_info = next(
                (cat for cat in Config.TICKET_TYPES if cat['value'] == category_value),
                Config.TICKET_TYPES[0]
            )
            
            # Get guild and roles
            guild = interaction.guild
            if not guild:
                return await interaction.followup.send("❌ Guild not found!", ephemeral=True)
            
            category = guild.get_channel(Config.TICKET_CATEGORY)
            if not category:
                logger.error(f"Category not found! ID: {Config.TICKET_CATEGORY}")
                return await interaction.followup.send(
                    "❌ Ticket category not found! Contact admin.", 
                    ephemeral=True
                )
            
            support_role = guild.get_role(Config.SUPPORT_ROLE)
            bot_role = guild.get_role(Config.BOT_ROLE)
            
            # Generate ticket ID
            ticket_id = create_ticket_id()
            
            # Create channel name
            username = interaction.user.name.lower().replace(' ', '-')[:20]
            channel_name = f"ticket-{username}-{ticket_id[:4]}"
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
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
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            
            # Add bot role if exists
            if bot_role:
                overwrites[bot_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True
                )
            
            # Create channel
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket: {ticket_id} | User: {interaction.user} | Category: {category_info['label']}"
            )
            
            # Save to database
            await self.db.create_ticket(
                ticket_id=ticket_id,
                user_id=str(interaction.user.id),
                channel_id=str(channel.id),
                category=category_value,
                guild_id=guild.id
            )
            
            # Create welcome embed
            embed = discord.Embed(
                title=f"🎫 New Ticket - {category_info['label']}",
                description=f"Welcome {interaction.user.mention}! Support team will be with you shortly.\n\nPlease describe your issue in detail.",
                color=category_info['color'],
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Ticket ID", value=f"`{ticket_id}`", inline=True)
            embed.add_field(name="Category", value=f"{category_info['emoji']} {category_info['label']}", inline=True)
            embed.add_field(name="Created", value=discord.utils.format_dt(datetime.utcnow(), 'R'), inline=True)
            
            embed.set_footer(text="Use the buttons below to manage this ticket")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # Send welcome message with buttons
            view = TicketView(ticket_id)
            
            # Send main message
            await channel.send(
                content=f"{support_role.mention if support_role else '@Support'} • {interaction.user.mention}",
                embed=embed,
                view=view
            )
            
            # Send info message and pin it
            info_msg = await channel.send(
                "📌 **Ticket Information**\n"
                "• Please describe your issue in detail\n"
                "• Support team will assist you shortly\n"
                "• Do not ping staff members unnecessarily\n"
                "• Use the buttons below to manage this ticket"
            )
            await info_msg.pin()
            
            # Log to ticket log channel
            log_channel = guild.get_channel(Config.TICKET_LOG_CHANNEL)
            if log_channel:
                log_embed = discord.Embed(
                    title="🎫 Ticket Created",
                    description=f"**User:** {interaction.user.mention}\n"
                              f"**Category:** {category_info['emoji']} {category_info['label']}\n"
                              f"**Channel:** {channel.mention}\n"
                              f"**Ticket ID:** `{ticket_id}`",
                    color=Config.COLOR_SUCCESS,
                    timestamp=datetime.utcnow()
                )
                log_embed.set_footer(text=f"User ID: {interaction.user.id}")
                await log_channel.send(embed=log_embed)
            
            # Update interaction
            embed = discord.Embed(
                title="✅ Ticket Created",
                description=f"Your ticket has been created: {channel.mention}",
                color=Config.COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            logger.error("Bot lacks permissions to create channel")
            await interaction.followup.send(
                "❌ I don't have permission to create channels! Please check my permissions.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating ticket: {e}\n{traceback.format_exc()}")
            await interaction.followup.send(
                "❌ Failed to create ticket. Please try again later.",
                ephemeral=True
            )
    
    async def handle_claim(self, interaction: discord.Interaction, ticket_id: str):
        """Handle ticket claiming"""
        
        try:
            # Check permissions
            if not any(role.id in [Config.SUPPORT_ROLE, Config.ADMIN_ROLE] for role in interaction.user.roles):
                embed = discord.Embed(
                    description="❌ You don't have permission to claim tickets!",
                    color=Config.COLOR_ERROR
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Check if already claimed
            ticket = await self.db.get_ticket(ticket_id)
            if ticket and ticket.get('claimed_by'):
                embed = discord.Embed(
                    description=f"❌ This ticket is already claimed by <@{ticket['claimed_by']}>",
                    color=Config.COLOR_WARNING
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Claim the ticket
            await self.db.claim_ticket(ticket_id, str(interaction.user.id))
            
            # Update channel permissions
            await interaction.channel.set_permissions(
                interaction.user,
                read_messages=True,
                send_messages=True,
                manage_messages=True
            )
            
            # Rename channel
            if not interaction.channel.name.startswith('claimed-'):
                await interaction.channel.edit(name=f"claimed-{interaction.channel.name}")
            
            embed = discord.Embed(
                description=f"✅ Ticket claimed by {interaction.user.mention}",
                color=Config.COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed)
            
            # Log the claim
            log_channel = interaction.guild.get_channel(Config.TICKET_LOG_CHANNEL)
            if log_channel:
                log_embed = discord.Embed(
                    title="🤚 Ticket Claimed",
                    description=f"**Ticket:** {interaction.channel.mention}\n"
                              f"**Claimed by:** {interaction.user.mention}",
                    color=Config.COLOR_INFO,
                    timestamp=datetime.utcnow()
                )
                await log_channel.send(embed=log_embed)
                
        except Exception as e:
            logger.error(f"Error claiming ticket: {e}")
            await interaction.followup.send("❌ Error claiming ticket", ephemeral=True)
    
    async def handle_close(self, interaction: discord.Interaction, ticket_id: str):
        """Handle ticket closing"""
        
        try:
            # Check permissions
            ticket = await self.db.get_ticket(ticket_id)
            if not ticket:
                return await interaction.followup.send("❌ Ticket not found!", ephemeral=True)
            
            has_permission = (
                any(role.id in [Config.SUPPORT_ROLE, Config.ADMIN_ROLE] for role in interaction.user.roles) or
                str(interaction.user.id) == ticket['user_id']
            )
            
            if not has_permission:
                embed = discord.Embed(
                    description="❌ You don't have permission to close this ticket!",
                    color=Config.COLOR_ERROR
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create confirmation view
            view = discord.ui.View(timeout=30)
            
            async def confirm_callback(interaction: discord.Interaction):
                try:
                    # Generate transcript if enabled
                    transcript = None
                    if Config.TICKET_TRANSCRIPT_ENABLED:
                        transcript = await create_transcript(interaction.channel)
                    
                    # Close ticket in database
                    await self.db.close_ticket(ticket_id, str(interaction.user.id), transcript)
                    
                    # Send closing message
                    embed = discord.Embed(
                        description="🔒 Closing ticket in 5 seconds...",
                        color=Config.COLOR_WARNING
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
                    
                    # Log closure
                    log_channel = interaction.guild.get_channel(Config.TICKET_LOG_CHANNEL)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🔒 Ticket Closed",
                            description=f"**Ticket:** {interaction.channel.mention}\n"
                                      f"**Closed by:** {interaction.user.mention}\n"
                                      f"**User:** <@{ticket['user_id']}>",
                            color=Config.COLOR_INFO,
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=log_embed)
                    
                    # Delete channel after delay
                    await asyncio.sleep(5)
                    await interaction.channel.delete()
                    
                except Exception as e:
                    logger.error(f"Error in confirm close: {e}")
            
            async def cancel_callback(interaction: discord.Interaction):
                embed = discord.Embed(
                    description="✅ Close cancelled",
                    color=Config.COLOR_SUCCESS
                )
                await interaction.response.edit_message(embed=embed, view=None)
            
            confirm_button = discord.ui.Button(label="Yes, Close Ticket", style=discord.ButtonStyle.danger, emoji="✅")
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            
            view.add_item(confirm_button)
            view.add_item(cancel_button)
            
            embed = discord.Embed(
                title="⚠️ Confirm Close",
                description="Are you sure you want to close this ticket?",
                color=Config.COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            await interaction.followup.send("❌ Error closing ticket", ephemeral=True)
    
    async def handle_transcript(self, interaction: discord.Interaction, ticket_id: str):
        """Generate and send ticket transcript"""
        
        try:
            transcript = await create_transcript(interaction.channel)
            
            if transcript:
                # Create a file from transcript
                filename = f"transcript_{ticket_id}.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(transcript)
                
                file = discord.File(filename, filename=filename)
                await interaction.followup.send("📄 Here's the ticket transcript:", file=file, ephemeral=True)
                
                # Clean up
                import os
                os.remove(filename)
            else:
                await interaction.followup.send("❌ Failed to generate transcript", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error generating transcript: {e}")
            await interaction.followup.send("❌ Error generating transcript", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Save messages in ticket channels"""
        
        if message.author.bot:
            return
        
        # Check if in ticket channel
        try:
            ticket = await self.db.get_ticket_by_channel(str(message.channel.id))
            if ticket:
                attachment_url = None
                if message.attachments:
                    attachment_url = message.attachments[0].url
                
                await self.db.add_message_to_ticket(
                    ticket['ticket_id'],
                    str(message.author.id),
                    message.content,
                    attachment_url
                )
        except Exception as e:
            logger.error(f"Error saving message: {e}")

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
