#!/usr/bin/env python3
"""
Discord Ticket Bot - Professional Edition
Main entry point for the bot application
"""

import asyncio
import logging
import sys
from typing import NoReturn

import discord
from discord.ext import commands

from config import Config
from database.mongodb import Database
from dashboard.server import start_dashboard
from utils.logger import setup_logger

# Setup logging
logger = setup_logger()

class TicketBot(commands.Bot):
    """Main bot class with custom initialization"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=Config.BOT_PREFIX,
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🎫 Tickets | /setup"
            ),
            status=discord.Status.online
        )
        
        self.db = None
        self.start_time = None
        self.ready = False
    
    async def setup_hook(self) -> None:
        """Async initialization hook"""
        # Initialize database
        self.db = Database()
        await self.db.connect()
        logger.info("✅ Database connected")
        
        # Load cogs
        cogs = [
            'cogs.setup_commands',
            'cogs.ticket_system',
            'cogs.admin_commands'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load cog {cog}: {e}")
        
        # Sync commands
        await self.tree.sync(guild=discord.Object(id=Config.GUILD_ID))
        logger.info("✅ Commands synced")
        
        self.start_time = discord.utils.utcnow()
        self.ready = True
    
    async def on_ready(self) -> None:
        """Called when bot is ready"""
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"✅ Connected to {len(self.guilds)} guilds")
        logger.info("=" * 50)
    
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        logger.error(f"Command error: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)}")

async def run_bot() -> NoReturn:
    """Run the Discord bot"""
    async with TicketBot() as bot:
        await bot.start(Config.TOKEN)

async def main() -> NoReturn:
    """Main entry point - runs both bot and dashboard"""
    logger.info("🚀 Starting Ticket Bot...")
    logger.info("=" * 50)
    
    # Start both services concurrently
    await asyncio.gather(
        run_bot(),
        start_dashboard()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
