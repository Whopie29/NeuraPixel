#!/usr/bin/env python3
"""
Configuration management for the AI Image Generator application.
Handles different environments (development, production) and provides
secure configuration options.
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class with common settings."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Image generation settings
    IMAGE_GENERATION_TIMEOUT = int(os.environ.get('IMAGE_GENERATION_TIMEOUT', '120'))  # 2 minutes
    MAX_CONCURRENT_GENERATIONS = int(os.environ.get('MAX_CONCURRENT_GENERATIONS', '5'))
    
    # File management settings
    GENERATED_IMAGES_DIR = os.environ.get('GENERATED_IMAGES_DIR', 'generated_images')
    MAX_IMAGE_AGE_DAYS = int(os.environ.get('MAX_IMAGE_AGE_DAYS', '30'))
    MAX_STORAGE_SIZE_MB = int(os.environ.get('MAX_STORAGE_SIZE_MB', '1000'))  # 1GB
    
    # Rate limiting settings
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '10'))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', '100'))
    
    # Security settings
    ENABLE_CORS = os.environ.get('ENABLE_CORS', 'False').lower() == 'true'
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',') if os.environ.get('ALLOWED_ORIGINS') else []
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', None)
    
    # Performance settings
    ENABLE_GZIP = os.environ.get('ENABLE_GZIP', 'True').lower() == 'true'
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', '3600'))  # 1 hour
    
    # Health check settings
    HEALTH_CHECK_ENABLED = os.environ.get('HEALTH_CHECK_ENABLED', 'True').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        pass

class DevelopmentConfig(Config):
    """Development configuration with debug settings."""
    
    DEBUG = True
    TESTING = False
    
    # More verbose logging in development
    LOG_LEVEL = 'DEBUG'
    
    # Shorter timeouts for faster development
    IMAGE_GENERATION_TIMEOUT = 60
    
    # Less strict rate limiting
    RATE_LIMIT_PER_MINUTE = 20
    RATE_LIMIT_PER_HOUR = 200
    
    # Enable CORS for development
    ENABLE_CORS = True
    ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

class ProductionConfig(Config):
    """Production configuration with security and performance optimizations."""
    
    DEBUG = False
    TESTING = False
    
    # Stricter security in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or None
    
    # Production logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')
    LOG_FILE = os.environ.get('LOG_FILE', '/var/log/ai-image-generator.log')
    
    # Production timeouts
    IMAGE_GENERATION_TIMEOUT = int(os.environ.get('IMAGE_GENERATION_TIMEOUT', '180'))  # 3 minutes
    
    # Stricter rate limiting
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '5'))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', '50'))
    
    # Production file management
    MAX_IMAGE_AGE_DAYS = int(os.environ.get('MAX_IMAGE_AGE_DAYS', '7'))  # Shorter retention
    MAX_STORAGE_SIZE_MB = int(os.environ.get('MAX_STORAGE_SIZE_MB', '5000'))  # 5GB
    
    @staticmethod
    def init_app(app):
        """Initialize production-specific settings."""
        Config.init_app(app)
        
        # Ensure secret key is set in production
        if not app.config.get('SECRET_KEY'):
            raise ValueError('SECRET_KEY environment variable must be set in production')
        
        # Set up production logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if app.config.get('LOG_FILE'):
            file_handler = RotatingFileHandler(
                app.config['LOG_FILE'],
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.WARNING)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.WARNING)

class TestingConfig(Config):
    """Testing configuration for unit tests."""
    
    TESTING = True
    DEBUG = True
    
    # Use in-memory or temporary storage for tests
    GENERATED_IMAGES_DIR = 'test_generated_images'
    
    # Faster timeouts for tests
    IMAGE_GENERATION_TIMEOUT = 30
    
    # Disable rate limiting for tests
    RATE_LIMIT_ENABLED = False
    
    # Shorter retention for tests
    MAX_IMAGE_AGE_DAYS = 1

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])