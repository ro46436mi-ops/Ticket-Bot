"""
Setup Commands Cog - Initial setup and configuration commands
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from config import Config
from database.mongodb import Database

class SetupCommands(commands.Cog):
    """Setup and configuration commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
    
    @app_commands.command(name="setup", description="🎫 Setup the ticket system panel")
    @app_commands.describe(channel="Channel to send the ticket panel to")
    @app_commands.default_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Create the ticket panel in specified channel"""
        
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need administrator permissions to use this command!",
                ephemeral=True
            )
        
        # Create embed
        embed = discord.Embed(
            title="🎫 Ticket Support System",
            description="Click the button below to create a support ticket!\n\n**Available Categories:**",
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        # Add categories
        for category in Config.TICKET_TYPES:
            embed.add_field(
                name=f"{category['emoji']} {category['label']}",
                value=category['description'],
                inline=True
            )
        
        embed.set_footer(text="Support team will assist you shortly")
        
        # Create button
        view = discord.ui.View(timeout=None)
        
        button = discord.ui.Button(
            label="Create Ticket",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="create_ticket_panel"
        )
        
        async def button_callback(interaction: discord.Interaction):
            # Call the ticket command
            cmd = self.bot.tree.get_command('ticket')
            if cmd:
                await cmd.callback(interaction.client.get_cog('TicketSystem'), interaction)
        
        button.callback = button_callback
        view.add_item(button)
        
        # Send panel
        await channel.send(embed=embed, view=view)
        
        # Confirm
        embed = discord.Embed(
            title="✅ Setup Complete",
            description=f"Ticket panel created in {channel.mention}",
            color=Config.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log setup
        log_channel = interaction.guild.get_channel(Config.TICKET_LOG_CHANNEL)
        if log_channel:
            log_embed = discord.Embed(
                title="🛠️ Ticket System Setup",
                description=f"**Setup by:** {interaction.user.mention}\n"
                          f"**Panel channel:** {channel.mention}",
                color=Config.COLOR_INFO,
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=log_embed)
    
    @app_commands.command(name="panel", description="📋 Send the ticket panel (Admin only)")
    @app_commands.describe(channel="Channel to send the panel to")
    async def panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Alias for setup command"""
        await self.setup_panel(interaction, channel)

async def setup(bot):
    await bot.add_cog(SetupCommands(bot), guild=discord.Object(id=Config.GUILD_ID))
