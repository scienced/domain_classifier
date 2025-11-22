"""
Database configuration and session management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL - SQLite file stored in backend directory
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./classifier.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # CRITICAL FIX: 30 second timeout instead of default 5
    } if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,  # CRITICAL FIX: Validate connections before use
    echo=False  # Set to True for SQL query logging during development
)

# CRITICAL FIX: Enable WAL mode for SQLite to allow concurrent reads
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better concurrency and performance."""
    if 'sqlite' in str(dbapi_conn):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrency
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
        cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    """
    Base.metadata.create_all(bind=engine)
