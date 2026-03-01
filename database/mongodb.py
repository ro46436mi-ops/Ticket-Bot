"""
MongoDB Database Handler for Ticket Bot
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from config import Config
from database.models import Ticket, User, TicketLog

logger = logging.getLogger(__name__)

class Database:
    """Main database handler class"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        # Collections
        self.tickets = None
        self.users = None
        self.blacklist = None
        self.logs = None
        self.settings = None
    
    async def connect(self) -> None:
        """Establish database connection"""
        try:
            self.client = AsyncIOMotorClient(Config.MONGODB_URI)
            self.db = self.client[Config.DB_NAME]
            
            # Initialize collections
            self.tickets = self.db.tickets
            self.users = self.db.users
            self.blacklist = self.db.blacklist
            self.logs = self.db.logs
            self.settings = self.db.settings
            
            # Create indexes
            await self._create_indexes()
            
            logger.info("✅ MongoDB connected successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    async def _create_indexes(self) -> None:
        """Create database indexes for performance"""
        
        # Tickets collection indexes
        await self.tickets.create_index("ticket_id", unique=True)
        await self.tickets.create_index("user_id")
        await self.tickets.create_index("status")
        await self.tickets.create_index("created_at")
        await self.tickets.create_index([("user_id", 1), ("status", 1)])
        
        # Users collection indexes
        await self.users.create_index("user_id", unique=True)
        await self.users.create_index("total_tickets")
        
        # Blacklist collection indexes
        await self.blacklist.create_index("user_id", unique=True)
        await self.blacklist.create_index("blacklisted_at")
        
        # Logs collection indexes
        await self.logs.create_index("ticket_id")
        await self.logs.create_index("timestamp")
        await self.logs.create_index([("ticket_id", 1), ("timestamp", -1)])
        
        # Settings collection
        await self.settings.create_index("guild_id", unique=True)
    
    # ========== Ticket Operations ==========
    
    async def create_ticket(self, ticket_id: str, user_id: str, channel_id: str, 
                           category: str, guild_id: int) -> Dict[str, Any]:
        """Create a new ticket"""
        ticket = Ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            channel_id=channel_id,
            category=category,
            guild_id=guild_id,
            status="open",
            created_at=datetime.utcnow()
        )
        
        await self.tickets.insert_one(ticket.to_dict())
        
        # Update user stats
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"total_tickets": 1, "open_tickets": 1},
                "$set": {"last_ticket": datetime.utcnow()},
                "$setOnInsert": {"first_seen": datetime.utcnow()}
            },
            upsert=True
        )
        
        # Log the action
        await self.log_action(
            ticket_id=ticket_id,
            action="created",
            user_id=user_id,
            details=f"Category: {category}"
        )
        
        return ticket.to_dict()
    
    async def get_user_tickets(self, user_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get tickets for a user"""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        cursor = self.tickets.find(query).sort("created_at", -1)
        return await cursor.to_list(length=None)
    
    async def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        """Get a specific ticket by ID"""
        return await self.tickets.find_one({"ticket_id": ticket_id})
    
    async def get_ticket_by_channel(self, channel_id: str) -> Optional[Dict]:
        """Get ticket by channel ID"""
        return await self.tickets.find_one({"channel_id": channel_id})
    
    async def close_ticket(self, ticket_id: str, closed_by: str, 
                          transcript: Optional[str] = None) -> bool:
        """Close a ticket"""
        result = await self.tickets.update_one(
            {"ticket_id": ticket_id},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "closed_by": closed_by,
                    "transcript": transcript
                }
            }
        )
        
        if result.modified_count:
            ticket = await self.get_ticket(ticket_id)
            
            # Update user stats
            await self.users.update_one(
                {"user_id": ticket["user_id"]},
                {"$inc": {"open_tickets": -1, "closed_tickets": 1}}
            )
            
            # Log the action
            await self.log_action(
                ticket_id=ticket_id,
                action="closed",
                user_id=closed_by
            )
            
            return True
        
        return False
    
    async def claim_ticket(self, ticket_id: str, claimed_by: str) -> bool:
        """Claim a ticket"""
        result = await self.tickets.update_one(
            {"ticket_id": ticket_id},
            {
                "$set": {
                    "claimed_by": claimed_by,
                    "claimed_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count:
            await self.log_action(
                ticket_id=ticket_id,
                action="claimed",
                user_id=claimed_by
            )
            return True
        
        return False
    
    async def add_message_to_ticket(self, ticket_id: str, user_id: str, 
                                   content: str, attachment: Optional[str] = None) -> None:
        """Add a message to ticket history"""
        message = {
            "user_id": user_id,
            "content": content,
            "attachment": attachment,
            "timestamp": datetime.utcnow()
        }
        
        await self.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$push": {"messages": message}}
        )
    
    # ========== User Operations ==========
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        user = await self.users.find_one({"user_id": user_id})
        
        if not user:
            return {
                "total_tickets": 0,
                "open_tickets": 0,
                "closed_tickets": 0,
                "first_seen": None,
                "last_ticket": None
            }
        
        return user
    
    # ========== Blacklist Operations ==========
    
    async def blacklist_user(self, user_id: str, reason: str, 
                            blacklisted_by: str) -> None:
        """Blacklist a user"""
        await self.blacklist.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "reason": reason,
                    "blacklisted_by": blacklisted_by,
                    "blacklisted_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        # Close any open tickets
        await self.tickets.update_many(
            {"user_id": user_id, "status": "open"},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "closed_by": "system_blacklist"
                }
            }
        )
    
    async def unblacklist_user(self, user_id: str) -> bool:
        """Remove user from blacklist"""
        result = await self.blacklist.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    async def is_blacklisted(self, user_id: str) -> bool:
        """Check if user is blacklisted"""
        blacklisted = await self.blacklist.find_one({"user_id": user_id})
        return blacklisted is not None
    
    # ========== Log Operations ==========
    
    async def log_action(self, ticket_id: str, action: str, 
                        user_id: str, details: Optional[str] = None) -> None:
        """Log a ticket action"""
        log = TicketLog(
            ticket_id=ticket_id,
            action=action,
            user_id=user_id,
            details=details,
            timestamp=datetime.utcnow()
        )
        
        await self.logs.insert_one(log.to_dict())
    
    async def get_ticket_logs(self, ticket_id: str, limit: int = 50) -> List[Dict]:
        """Get logs for a specific ticket"""
        cursor = self.logs.find(
            {"ticket_id": ticket_id}
        ).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    # ========== Statistics ==========
    
    async def get_guild_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get statistics for a guild"""
        pipeline = [
            {"$match": {"guild_id": guild_id}},
            {"$group": {
                "_id": None,
                "total_tickets": {"$sum": 1},
                "open_tickets": {
                    "$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}
                },
                "closed_tickets": {
                    "$sum": {"$cond": [{"$eq": ["$status", "closed"]}, 1, 0]}
                }
            }}
        ]
        
        result = await self.tickets.aggregate(pipeline).to_list(length=1)
        
        # Category breakdown
        category_pipeline = [
            {"$match": {"guild_id": guild_id}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }}
        ]
        
        categories = await self.tickets.aggregate(category_pipeline).to_list(length=None)
        
        stats = result[0] if result else {
            "total_tickets": 0,
            "open_tickets": 0,
            "closed_tickets": 0
        }
        
        stats["categories"] = {
            cat["_id"]: cat["count"] for cat in categories
        }
        
        # Time-based stats
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        stats["tickets_last_7_days"] = await self.tickets.count_documents({
            "guild_id": guild_id,
            "created_at": {"$gte": week_ago}
        })
        
        stats["avg_response_time"] = await self._calculate_avg_response_time(guild_id)
        
        return stats
    
    async def _calculate_avg_response_time(self, guild_id: int) -> Optional[float]:
        """Calculate average response time for tickets"""
        pipeline = [
            {"$match": {
                "guild_id": guild_id,
                "claimed_at": {"$exists": True}
            }},
            {"$project": {
                "response_time": {
                    "$subtract": ["$claimed_at", "$created_at"]
                }
            }},
            {"$group": {
                "_id": None,
                "avg_time": {"$avg": "$response_time"}
            }}
        ]
        
        result = await self.tickets.aggregate(pipeline).to_list(length=1)
        
        if result and result[0]["avg_time"]:
            return result[0]["avg_time"] / 3600  # Convert to hours
        
        return None
    
    # ========== Settings Operations ==========
    
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get settings for a guild"""
        settings = await self.settings.find_one({"guild_id": guild_id})
        
        if not settings:
            # Create default settings
            settings = {
                "guild_id": guild_id,
                "ticket_category": Config.TICKET_CATEGORY,
                "support_role": Config.SUPPORT_ROLE,
                "log_channel": Config.LOG_CHANNEL,
                "max_tickets_per_user": Config.MAX_TICKETS_PER_USER,
                "ticket_types": Config.TICKET_TYPES,
                "updated_at": datetime.utcnow()
            }
            await self.settings.insert_one(settings)
        
        return settings
    
    async def update_guild_settings(self, guild_id: int, updates: Dict[str, Any]) -> None:
        """Update guild settings"""
        updates["updated_at"] = datetime.utcnow()
        
        await self.settings.update_one(
            {"guild_id": guild_id},
            {"$set": updates},
            upsert=True
        )
