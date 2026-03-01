"""
Flask Dashboard Server
"""

from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
import asyncio
import threading
from typing import Dict, Any
import logging

from config import Config
from database.mongodb import Database
from dashboard.routes import setup_routes
from dashboard.auth import require_auth

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(
    __name__,
    template_folder='../templates',
    static_folder='../static'
)
app.secret_key = Config.DASHBOARD_SECRET
CORS(app)

# Database instance (will be set later)
db: Database = None

def init_dashboard(database: Database):
    """Initialize dashboard with database instance"""
    global db
    db = database
    setup_routes(app, db)
    logger.info("✅ Dashboard routes initialized")

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """API status endpoint"""
    return jsonify({
        'status': 'online',
        'version': '2.0.0',
        'timestamp': asyncio.run(db.get_guild_stats(Config.GUILD_ID)) if db else {}
    })

async def start_dashboard():
    """Start the Flask dashboard server"""
    from hypercorn.asyncio import serve
    from hypercorn.config import Config as HyperConfig
    
    hyper_config = HyperConfig()
    hyper_config.bind = [f"{Config.HOST}:{Config.PORT}"]
    
    logger.info(f"🌐 Dashboard starting on http://{Config.HOST}:{Config.PORT}")
    await serve(app, hyper_config)

def run_dashboard_sync(database):
    """Run dashboard in a separate thread (synchronous)"""
    global db
    db = database
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

def start_dashboard_thread(database):
    """Start dashboard in a background thread"""
    thread = threading.Thread(target=run_dashboard_sync, args=(database,))
    thread.daemon = True
    thread.start()
    return thread
