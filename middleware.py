#!/usr/bin/env python3
"""
Middleware for the AI Image Generator application.
Includes rate limiting, security headers, and performance optimizations.
"""

import time
import logging
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify, g
import hashlib

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Simple in-memory rate limiter with sliding window.
    For production, consider using Redis or similar external store.
    """
    
    def __init__(self, requests_per_minute=10, requests_per_hour=100):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        
        # Store request timestamps for each client
        self.minute_requests = defaultdict(deque)
        self.hour_requests = defaultdict(deque)
        
        # Cleanup interval
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def _get_client_id(self):
        """Get client identifier (IP address with optional user agent hash)."""
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Add user agent hash for better client identification
        user_agent = request.headers.get('User-Agent', '')
        user_agent_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        return f"{client_ip}:{user_agent_hash}"
    
    def _cleanup_old_requests(self):
        """Clean up old request records to prevent memory leaks."""
        current_time = time.time()
        
        # Only cleanup periodically
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600
        
        # Clean up minute requests
        for client_id in list(self.minute_requests.keys()):
            requests = self.minute_requests[client_id]
            while requests and requests[0] < minute_cutoff:
                requests.popleft()
            if not requests:
                del self.minute_requests[client_id]
        
        # Clean up hour requests
        for client_id in list(self.hour_requests.keys()):
            requests = self.hour_requests[client_id]
            while requests and requests[0] < hour_cutoff:
                requests.popleft()
            if not requests:
                del self.hour_requests[client_id]
        
        self.last_cleanup = current_time
        logger.debug(f"Rate limiter cleanup completed. Active clients: {len(self.minute_requests)}")
    
    def is_allowed(self):
        """Check if the current request is allowed."""
        client_id = self._get_client_id()
        current_time = time.time()
        
        # Cleanup old requests
        self._cleanup_old_requests()
        
        # Check minute limit
        minute_requests = self.minute_requests[client_id]
        minute_cutoff = current_time - 60
        
        # Remove old requests from minute window
        while minute_requests and minute_requests[0] < minute_cutoff:
            minute_requests.popleft()
        
        if len(minute_requests) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute): {client_id} - {len(minute_requests)} requests")
            return False, "Too many requests per minute"
        
        # Check hour limit
        hour_requests = self.hour_requests[client_id]
        hour_cutoff = current_time - 3600
        
        # Remove old requests from hour window
        while hour_requests and hour_requests[0] < hour_cutoff:
            hour_requests.popleft()
        
        if len(hour_requests) >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour): {client_id} - {len(hour_requests)} requests")
            return False, "Too many requests per hour"
        
        # Record this request
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        return True, None
    
    def get_stats(self):
        """Get rate limiter statistics."""
        return {
            "active_clients": len(self.minute_requests),
            "total_minute_requests": sum(len(requests) for requests in self.minute_requests.values()),
            "total_hour_requests": sum(len(requests) for requests in self.hour_requests.values()),
            "requests_per_minute_limit": self.requests_per_minute,
            "requests_per_hour_limit": self.requests_per_hour
        }

# Global rate limiter instance
rate_limiter = None

def init_rate_limiter(app):
    """Initialize rate limiter with app configuration."""
    global rate_limiter
    
    if app.config.get('RATE_LIMIT_ENABLED', True):
        rate_limiter = RateLimiter(
            requests_per_minute=app.config.get('RATE_LIMIT_PER_MINUTE', 10),
            requests_per_hour=app.config.get('RATE_LIMIT_PER_HOUR', 100)
        )
        logger.info(f"Rate limiter initialized: {app.config.get('RATE_LIMIT_PER_MINUTE')}/min, {app.config.get('RATE_LIMIT_PER_HOUR')}/hour")
    else:
        logger.info("Rate limiting disabled")

def rate_limit_required(f):
    """Decorator to apply rate limiting to routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if rate_limiter:
            allowed, message = rate_limiter.is_allowed()
            if not allowed:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': message,
                    'retry_after': 60  # seconds
                }), 429
        
        return f(*args, **kwargs)
    return decorated_function

def add_security_headers(response):
    """Add security headers to response."""
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' https:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    
    return response

def add_performance_headers(response):
    """Add performance-related headers."""
    # Cache control for static assets
    if request.endpoint == 'static':
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
    elif request.endpoint in ['health', 'get_storage_stats']:
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    else:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response

def add_cors_headers(response, app):
    """Add CORS headers if enabled."""
    if app.config.get('ENABLE_CORS', False):
        allowed_origins = app.config.get('ALLOWED_ORIGINS', [])
        origin = request.headers.get('Origin')
        
        if not allowed_origins or origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin or '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Max-Age'] = '3600'
    
    return response

class RequestLogger:
    """Log requests with performance metrics."""
    
    def __init__(self):
        self.start_time = None
    
    def before_request(self):
        """Log request start."""
        g.start_time = time.time()
        logger.debug(f"Request started: {request.method} {request.url}")
    
    def after_request(self, response):
        """Log request completion with timing."""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # Log slow requests
            if duration > 1.0:  # Log requests taking more than 1 second
                logger.warning(f"Slow request: {request.method} {request.url} - {duration:.2f}s - {response.status_code}")
            else:
                logger.debug(f"Request completed: {request.method} {request.url} - {duration:.2f}s - {response.status_code}")
        
        return response

def init_middleware(app):
    """Initialize all middleware for the application."""
    
    # Initialize rate limiter
    init_rate_limiter(app)
    
    # Initialize request logger
    request_logger = RequestLogger()
    
    # Register before request handlers
    @app.before_request
    def before_request():
        request_logger.before_request()
    
    # Register after request handlers
    @app.after_request
    def after_request(response):
        # Apply security headers
        response = add_security_headers(response)
        
        # Apply performance headers
        response = add_performance_headers(response)
        
        # Apply CORS headers if enabled
        response = add_cors_headers(response, app)
        
        # Log request
        response = request_logger.after_request(response)
        
        return response
    
    # Handle OPTIONS requests for CORS
    @app.route('/', methods=['OPTIONS'])
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options(path=None):
        response = jsonify({'status': 'ok'})
        return response
    
    logger.info("Middleware initialized successfully")

def get_rate_limiter_stats():
    """Get rate limiter statistics."""
    if rate_limiter:
        return rate_limiter.get_stats()
    return {"rate_limiting": "disabled"}