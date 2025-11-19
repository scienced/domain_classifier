"""
SQLAlchemy models for classification runs, records, and overrides
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base


class RunStatus(str, enum.Enum):
    """Classification run status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordStatus(str, enum.Enum):
    """Individual record processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Label(str, enum.Enum):
    """Classification labels"""
    PURE_BODYWEAR = "Pure Bodywear"
    BODYWEAR_LEANING = "Bodywear Leaning"
    NEEDS_REVIEW = "Needs Review"
    GENERALIST = "Generalist"
    ERROR = "Error"


class ApiProvider(str, enum.Enum):
    """External API providers"""
    OPENAI = "openai"
    FIRECRAWL = "firecrawl"


class Run(Base):
    """
    Classification run - represents a batch of domains to be classified
    """
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(Enum(RunStatus), default=RunStatus.PENDING, nullable=False)

    # Progress tracking
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    records = relationship("Record", back_populates="run", cascade="all, delete-orphan")

    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_records == 0:
            return 0
        return (self.processed_records / self.total_records) * 100

    @property
    def is_active(self):
        """Check if run is currently active"""
        return self.status in [RunStatus.RUNNING, RunStatus.PENDING]


class Record(Base):
    """
    Individual domain classification record
    """
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False, index=True)

    # Domain and classification result
    domain = Column(String(255), nullable=False, index=True)
    label = Column(Enum(Label), nullable=True)
    confidence = Column(Float, nullable=True)

    # Detailed scores
    text_score = Column(Float, nullable=True)
    vision_score = Column(Float, nullable=True)

    # Classification details
    reasons = Column(Text, nullable=True)  # Semicolon-separated reasoning
    stage_used = Column(String(50), nullable=True)  # http, playwright, firecrawl
    image_count = Column(Integer, default=0)

    # Metadata
    http_status = Column(Integer, nullable=True)
    final_url = Column(String(512), nullable=True)
    nav_count = Column(Integer, default=0)
    heading_count = Column(Integer, default=0)

    # Error handling
    error = Column(Text, nullable=True)
    status = Column(Enum(RecordStatus), default=RecordStatus.PENDING, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    run = relationship("Run", back_populates="records")
    overrides = relationship("Override", back_populates="record", cascade="all, delete-orphan")

    @property
    def is_overridden(self):
        """Check if this record has been manually overridden"""
        return len(self.overrides) > 0

    @property
    def current_override(self):
        """Get the most recent override if any"""
        if self.overrides:
            return sorted(self.overrides, key=lambda o: o.created_at, reverse=True)[0]
        return None


class Override(Base):
    """
    Manual override of classification result
    """
    __tablename__ = "overrides"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id"), nullable=False, index=True)

    # Override data
    old_label = Column(Enum(Label), nullable=False)
    new_label = Column(Enum(Label), nullable=False)
    user_note = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    record = relationship("Record", back_populates="overrides")


class ApiUsage(Base):
    """
    Track external API usage for monitoring and cost management
    """
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)

    # API details
    provider = Column(Enum(ApiProvider), nullable=False, index=True)
    operation = Column(String(100), nullable=False)  # e.g., "vision_api", "scrape"

    # Association
    record_id = Column(Integer, ForeignKey("records.id"), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True, index=True)

    # Result
    success = Column(Integer, default=1)  # 1 = success, 0 = failure
    error_message = Column(Text, nullable=True)

    # Cost tracking (optional)
    tokens_used = Column(Integer, nullable=True)  # For OpenAI
    estimated_cost = Column(Float, nullable=True)  # In USD

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
