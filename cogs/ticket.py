import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import config
from utils.helpers import is_staff, get_transcript, create_transcript_file

class TicketButtons(discord.ui.View):
    """Ticket buttons view"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🙋 Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Claim ticket button handler"""
        if not is_staff(interaction.user, config.STAFF_ROLE_IDS):
            await interaction.response.send_message("❌ Sirf Staff claim kar sakta hai!", ephemeral=True)
            return
        
        await interaction.response.send_message(f"✅ Ticket claimed by {interaction.user.mention}")
    
    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket button handler"""
        if not is_staff(interaction.user, config.STAFF_ROLE_IDS):
            await interaction.response.send_message("❌ Sirf Staff close kar sakta hai!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Get transcript
        transcript = await get_transcript(interaction.channel)
        transcript_file = await create_transcript_file(transcript, interaction.channel.name)
        
        # Send to log channel
        log_channel = interaction.guild.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"Ticket closed by {interaction.user.mention}\nChannel: #{interaction.channel.name}",
                file=transcript_file
            )
        
        # Delete channel
        await interaction.channel.delete()

class TicketDropdown(discord.ui.Select):
    """Ticket category dropdown"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label=opt["label"],
                value=opt["value"]
            ) for opt in config.TICKET_OPTIONS
        ]
        super().__init__(
            placeholder="Select a ticket category...",
            options=options,
            custom_id="ticket_dropdown"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        category = interaction.guild.get_channel(config.TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("Ticket category not found!", ephemeral=True)
            return
        
        # Create ticket channel
        channel_name = f"ticket-{interaction.user.name.lower()}"
        
        # Set up permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        # Add staff role permissions
        for role_id in config.STAFF_ROLE_IDS:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        try:
            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket created by {interaction.user.name}"
            )
            
            # Send initial message with buttons
            embed = discord.Embed(
                title="Ticket Created",
                description="Your ticket is open! Staff will help soon.",
                color=0x00ff00
            )
            
            view = TicketButtons()
            await channel.send(f"{interaction.user.mention}", embed=embed, view=view)
            await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error creating ticket: {str(e)}", ephemeral=True)

class TicketSetupView(discord.ui.View):
    """Ticket setup view with dropdown"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

class TicketCog(commands.Cog):
    """Ticket system commands"""
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ticket-setup", description="Setup ticket system")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def ticket_setup(self, interaction: discord.Interaction):
        """Send ticket creation embed with dropdown"""
        
        embed = discord.Embed(
            title="🎟️ Create Ticket - SM GrowMart HQ",
            description="Select an option from the dropdown below to create a ticket",
            color=0x00ff00
        )
        
        view = TicketSetupView()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
