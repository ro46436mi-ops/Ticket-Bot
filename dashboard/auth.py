"""
Dashboard Authentication
"""

from functools import wraps
from flask import session, jsonify, request
import secrets
import hashlib
import hmac

from config import Config

def verify_key(key: str) -> bool:
    """Verify dashboard authentication key"""
    if not key or not Config.DASHBOARD_SECRET:
        return False
    
    # Constant time comparison to prevent timing attacks
    return hmac.compare_digest(key, Config.DASHBOARD_SECRET)

def require_auth(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session first
        if session.get('authenticated'):
            return f(*args, **kwargs)
        
        # Check header
        auth_key = request.headers.get('X-Dashboard-Key')
        if auth_key and verify_key(auth_key):
            return f(*args, **kwargs)
        
        return jsonify({'error': 'Unauthorized'}), 401
    
    return decorated

def generate_session_token() -> str:
    """Generate a new session token"""
    return secrets.token_urlsafe(32)

def hash_key(key: str) -> str:
    """Hash a key for storage"""
    salt = Config.DASHBOARD_SECRET.encode()
    return hashlib.pbkdf2_hmac('sha256', key.encode(), salt, 100000).hex()
