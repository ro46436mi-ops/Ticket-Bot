"""
Admin Commands Cog - Administrative commands for ticket system
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import humanize

from config import Config
from database.mongodb import Database

class AdminCommands(commands.Cog):
    """Admin-only commands for managing the ticket system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin role"""
        if not any(role.id == Config.ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message(
                Config.NO_PERMISSION,
                ephemeral=True
            )
            return False
        return True
    
    @app_commands.command(name="stats", description="📊 View ticket system statistics")
    async def stats(self, interaction: discord.Interaction):
        """View detailed statistics"""
        if not await self.is_admin(interaction):
            return
        
        await interaction.response.defer()
        
        stats = await self.db.get_guild_stats(interaction.guild_id)
        
        embed = discord.Embed(
            title="📊 Ticket System Statistics",
            color=Config.COLOR_INFO,
            timestamp=datetime.utcnow()
        )
        
        # Overall stats
        embed.add_field(name="Total Tickets", value=stats.get('total_tickets', 0), inline=True)
        embed.add_field(name="Open Tickets", value=stats.get('open_tickets', 0), inline=True)
        embed.add_field(name="Closed Tickets", value=stats.get('closed_tickets', 0), inline=True)
        
        # Category breakdown
        categories = stats.get('categories', {})
        if categories:
            cat_text = "\n".join([
                f"• **{cat}:** {count}"
                for cat, count in categories.items()
            ])
            embed.add_field(name="📂 By Category", value=cat_text, inline=False)
        
        # Time stats
        embed.add_field(
            name="📈 Last 7 Days",
            value=f"**{stats.get('tickets_last_7_days', 0)}** new tickets",
            inline=True
        )
        
        avg_response = stats.get('avg_response_time')
        if avg_response:
            embed.add_field(
                name="⏱️ Avg Response",
                value=humanize.naturaldelta(timedelta(hours=avg_response)),
                inline=True
            )
        
        # User stats
        total_users = await self.db.users.count_documents({})
        blacklisted = await self.db.blacklist.count_documents({})
        
        embed.add_field(name="👥 Total Users", value=total_users, inline=True)
        embed.add_field(name="⛔ Blacklisted", value=blacklisted, inline=True)
        
        embed.set_footer(text=f"Guild ID: {interaction.guild_id}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="blacklist", description="⛔ Blacklist a user from creating tickets")
    @app_commands.describe(
        user="User to blacklist",
        reason="Reason for blacklisting"
    )
    async def blacklist(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        """Blacklist a user"""
        if not await self.is_admin(interaction):
            return
        
        await self.db.blacklist_user(str(user.id), reason, str(interaction.user.id))
        
        embed = discord.Embed(
            title="⛔ User Blacklisted",
            description=f"**User:** {user.mention}\n"
                      f"**Reason:** {reason}\n"
                      f"**By:** {interaction.user.mention}",
            color=Config.COLOR_ERROR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
        # Log to ticket log
        log_channel = interaction.guild.get_channel(Config.TICKET_LOG_CHANNEL)
        if log_channel:
            await log_channel.send(embed=embed)
    
    @app_commands.command(name="unblacklist", description="✅ Remove user from blacklist")
    @app_commands.describe(user="User to unblacklist")
    async def unblacklist(self, interaction: discord.Interaction, user: discord.User):
        """Remove user from blacklist"""
        if not await self.is_admin(interaction):
            return
        
        result = await self.db.unblacklist_user(str(user.id))
        
        if result:
            embed = discord.Embed(
                title="✅ User Unblacklisted",
                description=f"**User:** {user.mention}\n"
                          f"**By:** {interaction.user.mention}",
                color=Config.COLOR_SUCCESS,
                timestamp=datetime.utcnow()
            )
        else:
            embed = discord.Embed(
                title="❌ Not Found",
                description=f"{user.mention} is not blacklisted.",
                color=Config.COLOR_WARNING
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clean", description="🧹 Clean up old closed tickets")
    @app_commands.describe(days="Delete tickets older than X days (default: 7)")
    async def clean(self, interaction: discord.Interaction, days: int = 7):
        """Clean up old tickets"""
        if not await self.is_admin(interaction):
            return
        
        await interaction.response.defer()
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Find old tickets
        old_tickets = await self.db.tickets.find({
            "guild_id": interaction.guild_id,
            "status": "closed",
            "closed_at": {"$lt": cutoff}
        }).to_list(length=None)
        
        deleted_count = 0
        
        for ticket in old_tickets:
            # Delete Discord channel
            channel = interaction.guild.get_channel(int(ticket['channel_id']))
            if channel:
                try:
                    await channel.delete()
                    deleted_count += 1
                except:
                    pass
        
        # Delete from database
        db_result = await self.db.tickets.delete_many({
            "guild_id": interaction.guild_id,
            "status": "closed",
            "closed_at": {"$lt": cutoff}
        })
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Deleted **{deleted_count}** channels\n"
                      f"Removed **{db_result.deleted_count}** tickets from database",
            color=Config.COLOR_SUCCESS,
            timestamp=datetime.utcnow()
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="ticketlog", description="📝 View logs for a specific ticket")
    @app_commands.describe(ticket_id="Ticket ID to view logs for")
    async def ticket_logs(self, interaction: discord.Interaction, ticket_id: str):
        """View ticket logs"""
        if not await self.is_admin(interaction):
            return
        
        logs = await self.db.get_ticket_logs(ticket_id, limit=20)
        
        if not logs:
            return await interaction.response.send_message(
                f"❌ No logs found for ticket `{ticket_id}`",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title=f"📝 Ticket Logs - {ticket_id}",
            color=Config.COLOR_INFO,
            timestamp=datetime.utcnow()
        )
        
        log_text = ""
        for log in logs:
            timestamp = discord.utils.format_dt(log['timestamp'], 'R')
            action = log['action'].upper()
            user = f"<@{log['user_id']}>"
            log_text += f"`{timestamp}` **{action}** by {user}\n"
            
            if log.get('details'):
                log_text += f"└─ {log['details']}\n"
        
        if len(log_text) > 1024:
            log_text = log_text[:1000] + "..."
        
        embed.description = log_text
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="👤 View user ticket information")
    @app_commands.describe(user="User to get info for")
    async def user_info(self, interaction: discord.Interaction, user: discord.User):
        """View user information"""
        if not await self.is_admin(interaction):
            return
        
        stats = await self.db.get_user_stats(str(user.id))
        blacklisted = await self.db.is_blacklisted(str(user.id))
        
        embed = discord.Embed(
            title=f"👤 User Information - {user.name}",
            color=Config.COLOR_INFO,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        embed.add_field(name="User ID", value=user.id, inline=False)
        embed.add_field(name="Total Tickets", value=stats.get('total_tickets', 0), inline=True)
        embed.add_field(name="Open Tickets", value=stats.get('open_tickets', 0), inline=True)
        embed.add_field(name="Closed Tickets", value=stats.get('closed_tickets', 0), inline=True)
        
        status = "⛔ Blacklisted" if blacklisted else "✅ Allowed"
        embed.add_field(name="Status", value=status, inline=True)
        
        if stats.get('first_seen'):
            first_seen = discord.utils.format_dt(stats['first_seen'], 'R')
            embed.add_field(name="First Seen", value=first_seen, inline=True)
        
        if stats.get('last_ticket'):
            last_ticket = discord.utils.format_dt(stats['last_ticket'], 'R')
            embed.add_field(name="Last Ticket", value=last_ticket, inline=True)
        
        # Get user's recent tickets
        tickets = await self.db.get_user_tickets(str(user.id))
        if tickets:
            recent = "\n".join([
                f"• <#{t['channel_id']}> - {t['status']}"
                for t in tickets[:5]
            ])
            embed.add_field(name="Recent Tickets", value=recent, inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot), guild=discord.Object(id=Config.GUILD_ID))
