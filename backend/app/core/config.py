"""
GigShield Configuration Module

Reads and validates environment variables using Pydantic Settings.
All configuration is centralized here for use across the application.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    
    All variables are required unless marked Optional.
    Uses python-dotenv for local .env file support.
    """

    # Database Configuration
    database_url: str
    """PostgreSQL connection string for Supabase with PostGIS and TimescaleDB"""

    # Cache & Message Broker
    redis_url: str
    """Redis connection URL for Celery broker (rediss:// for TLS on Upstash)"""

    # Payment Gateway
    razorpay_key_id: str
    """Razorpay test mode API Key ID (starts with rzp_test_)"""
    
    razorpay_key_secret: str
    """Razorpay test mode API Key Secret"""

    # Weather & Environmental Data
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    """Open-Meteo Forecast API base URL (real-time trigger monitoring)"""
    
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1"
    """Open-Meteo Historical Archive API base URL (training data, 80-year rainfall)"""

    # AQI Monitoring
    data_gov_in_api_key: str
    """API key for data.gov.in CPCB NAMP AQI queries"""

    # Push Notifications (Phase 3)
    expo_access_token: Optional[str] = None
    """Expo push notification access token (used in Phase 3)"""

    # Application Settings
    environment: str = "development"
    """Deployment environment: 'development', 'staging', or 'production'"""
    
    debug: bool = False
    """FastAPI debug mode (disable in production)"""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        """Environment variable names are case-insensitive"""


# Global settings instance
settings = Settings()
