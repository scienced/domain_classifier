"""
Application configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Brand Classification MVP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Authentication
    AUTH_PASSWORD: str = "changeme"  # Override in .env
    AUTH_TOKEN_SECRET: str = "your-secret-key-change-in-production"  # Override in .env
    AUTH_TOKEN_EXPIRE_HOURS: int = 24

    # Database
    DATABASE_URL: str = "sqlite:///./classifier.db"

    # External APIs
    OPENAI_API_KEY: Optional[str] = None
    FIRECRAWL_API_KEY: Optional[str] = None

    # Worker settings
    WORKER_POLL_INTERVAL_SECONDS: int = 2
    WORKER_ENABLED: bool = True

    # Classification settings
    CONFIG_DIR: str = "../config"  # Relative to backend/app

    # CORS settings
    CORS_ORIGINS: list = [
        "http://localhost:3000",  # React dev server
        "http://localhost:8000",  # Backend dev server
    ]

    class Config:
        env_file = "../.env"  # Look for .env in project root (one level up from backend/)
        case_sensitive = True


# Global settings instance
settings = Settings()
