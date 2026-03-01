"""
Data models for Ticket Bot
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class Ticket:
    """Ticket data model"""
    ticket_id: str
    user_id: str
    channel_id: str
    category: str
    guild_id: int
    status: str = "open"
    created_at: datetime = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    messages: List[Dict] = None
    transcript: Optional[str] = None
    priority: int = 0
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class User:
    """User statistics model"""
    user_id: str
    total_tickets: int = 0
    open_tickets: int = 0
    closed_tickets: int = 0
    first_seen: Optional[datetime] = None
    last_ticket: Optional[datetime] = None
    banned: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class TicketLog:
    """Ticket log entry model"""
    ticket_id: str
    action: str  # created, closed, claimed, message, etc.
    user_id: str
    timestamp: datetime
    details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class BlacklistEntry:
    """Blacklist entry model"""
    user_id: str
    reason: str
    blacklisted_by: str
    blacklisted_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GuildSettings:
    """Guild settings model"""
    guild_id: int
    ticket_category: int
    support_role: int
    log_channel: int
    admin_role: Optional[int] = None
    max_tickets_per_user: int = 1
    ticket_types: List[Dict] = None
    welcome_message: Optional[str] = None
    auto_close_days: Optional[int] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.ticket_types is None:
            from config import Config
            self.ticket_types = Config.TICKET_TYPES
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
