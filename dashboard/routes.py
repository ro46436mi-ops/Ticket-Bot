"""
Dashboard API Routes
"""

from flask import jsonify, request, session
from functools import wraps
from datetime import datetime
import logging

from config import Config
from dashboard.auth import require_auth, verify_key

logger = logging.getLogger(__name__)

def setup_routes(app, db):
    """Setup all dashboard routes"""
    
    @app.route('/api/auth', methods=['POST'])
    def auth():
        """Authenticate with dashboard key"""
        data = request.json
        key = data.get('key')
        
        if verify_key(key):
            session['authenticated'] = True
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Invalid key'}), 401
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        """Logout from dashboard"""
        session.pop('authenticated', None)
        return jsonify({'success': True})
    
    @app.route('/api/stats')
    @require_auth
    async def get_stats():
        """Get overall statistics"""
        try:
            stats = await db.get_guild_stats(Config.GUILD_ID)
            
            # Add user stats
            stats['total_users'] = await db.users.count_documents({})
            stats['blacklisted'] = await db.blacklist.count_documents({})
            
            # Add recent activity
            recent = await db.tickets.find(
                {"guild_id": Config.GUILD_ID}
            ).sort("created_at", -1).limit(5).to_list(length=5)
            
            for ticket in recent:
                ticket['_id'] = str(ticket['_id'])
            
            stats['recent'] = recent
            
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/tickets')
    @require_auth
    async def get_tickets():
        """Get list of tickets"""
        try:
            status = request.args.get('status', 'all')
            limit = int(request.args.get('limit', 50))
            
            query = {"guild_id": Config.GUILD_ID}
            if status != 'all':
                query['status'] = status
            
            tickets = await db.tickets.find(query).sort(
                "created_at", -1
            ).limit(limit).to_list(length=limit)
            
            for ticket in tickets:
                ticket['_id'] = str(ticket['_id'])
                
                # Get user info
                user = await db.users.find_one({"user_id": ticket['user_id']})
                if user:
                    ticket['user'] = user
            
            return jsonify(tickets)
        except Exception as e:
            logger.error(f"Error getting tickets: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/tickets/<ticket_id>')
    @require_auth
    async def get_ticket(ticket_id):
        """Get specific ticket details"""
        try:
            ticket = await db.get_ticket(ticket_id)
            
            if not ticket:
                return jsonify({'error': 'Ticket not found'}), 404
            
            ticket['_id'] = str(ticket['_id'])
            
            # Get logs
            logs = await db.get_ticket_logs(ticket_id)
            for log in logs:
                log['_id'] = str(log['_id'])
            
            ticket['logs'] = logs
            
            return jsonify(ticket)
        except Exception as e:
            logger.error(f"Error getting ticket {ticket_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/tickets/<ticket_id>/close', methods=['POST'])
    @require_auth
    async def close_ticket(ticket_id):
        """Close a ticket"""
        try:
            result = await db.close_ticket(ticket_id, 'dashboard')
            
            if result:
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Failed to close ticket'}), 400
        except Exception as e:
            logger.error(f"Error closing ticket {ticket_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/blacklist')
    @require_auth
    async def get_blacklist():
        """Get blacklisted users"""
        try:
            blacklist = await db.blacklist.find({}).sort(
                "blacklisted_at", -1
            ).to_list(length=100)
            
            for entry in blacklist:
                entry['_id'] = str(entry['_id'])
            
            return jsonify(blacklist)
        except Exception as e:
            logger.error(f"Error getting blacklist: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/blacklist/add', methods=['POST'])
    @require_auth
    async def add_blacklist():
        """Add user to blacklist"""
        try:
            data = request.json
            user_id = data.get('user_id')
            reason = data.get('reason', 'No reason provided')
            
            await db.blacklist_user(user_id, reason, 'dashboard')
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/blacklist/remove', methods=['POST'])
    @require_auth
    async def remove_blacklist():
        """Remove user from blacklist"""
        try:
            data = request.json
            user_id = data.get('user_id')
            
            result = await db.unblacklist_user(user_id)
            
            return jsonify({'success': result})
        except Exception as e:
            logger.error(f"Error removing from blacklist: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/config')
    @require_auth
    def get_config():
        """Get bot configuration"""
        return jsonify({
            'ticket_types': Config.TICKET_TYPES,
            'max_tickets_per_user': Config.MAX_TICKETS_PER_USER,
            'guild_id': Config.GUILD_ID,
            'support_role': Config.SUPPORT_ROLE,
            'admin_role': Config.ADMIN_ROLE,
            'log_channel': Config.LOG_CHANNEL,
            'ticket_log_channel': Config.TICKET_LOG_CHANNEL
        })
    
    @app.route('/api/config/update', methods=['POST'])
    @require_auth
    async def update_config():
        """Update configuration"""
        try:
            data = request.json
            
            # Update in database
            await db.update_guild_settings(Config.GUILD_ID, data)
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/users/search')
    @require_auth
    async def search_users():
        """Search for users"""
        try:
            query = request.args.get('q', '')
            
            if not query:
                return jsonify([])
            
            # Search in database
            users = await db.users.find({
                "$or": [
                    {"user_id": {"$regex": query, "$options": "i"}},
                ]
            }).limit(10).to_list(length=10)
            
            for user in users:
                user['_id'] = str(user['_id'])
            
            return jsonify(users)
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return jsonify({'error': str(e)}), 500
    
    return app
