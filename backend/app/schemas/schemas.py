"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    """Run status enum"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordStatus(str, Enum):
    """Record status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Label(str, Enum):
    """Classification label enum"""
    PURE_BODYWEAR = "Pure Bodywear"
    BODYWEAR_LEANING = "Bodywear Leaning"
    NEEDS_REVIEW = "Needs Review"
    GENERALIST = "Generalist"
    ERROR = "Error"


# Run schemas
class RunCreate(BaseModel):
    """Schema for creating a new run"""
    name: str = Field(..., min_length=1, max_length=255)


class RunResponse(BaseModel):
    """Schema for run response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: RunStatus
    total_records: int
    processed_records: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_percentage: float


class RunList(BaseModel):
    """Schema for paginated run list"""
    runs: List[RunResponse]
    total: int
    page: int
    page_size: int


# Record schemas
class RecordResponse(BaseModel):
    """Schema for record response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    domain: str
    label: Optional[Label]
    confidence: Optional[float]
    text_score: Optional[float]
    vision_score: Optional[float]
    reasons: Optional[str]
    stage_used: Optional[str]
    image_count: int
    http_status: Optional[int]
    final_url: Optional[str]
    nav_count: int
    heading_count: int
    error: Optional[str]
    status: RecordStatus
    created_at: datetime
    started_at: Optional[datetime]
    processed_at: Optional[datetime]
    is_overridden: bool


class RecordList(BaseModel):
    """Schema for paginated record list"""
    records: List[RecordResponse]
    total: int
    page: int
    page_size: int


class RecordFilter(BaseModel):
    """Schema for filtering records"""
    label: Optional[Label] = None
    status: Optional[RecordStatus] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    has_error: Optional[bool] = None
    is_overridden: Optional[bool] = None


# Override schemas
class OverrideCreate(BaseModel):
    """Schema for creating a manual override"""
    new_label: Label
    user_note: Optional[str] = Field(None, max_length=1000)


class OverrideResponse(BaseModel):
    """Schema for override response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_id: int
    old_label: Label
    new_label: Label
    user_note: Optional[str]
    created_at: datetime


# Upload schemas
class DomainUpload(BaseModel):
    """Schema for uploading domains"""
    domains: List[str] = Field(..., min_length=1)


# Status schemas
class RunStatusResponse(BaseModel):
    """Schema for detailed run status with ETA"""
    id: int
    name: str
    status: RunStatus
    total_records: int
    processed_records: int
    progress_percentage: float
    eta_seconds: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# Statistics schemas
class RunStatistics(BaseModel):
    """Schema for run statistics"""
    total_records: int
    completed_records: int
    error_records: int
    label_distribution: dict[str, int]
    stage_distribution: dict[str, int]
    average_confidence: Optional[float]
    average_processing_time_seconds: Optional[float]


# Authentication schemas
class LoginRequest(BaseModel):
    """Schema for login request"""
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Schema for login response"""
    access_token: str
    token_type: str = "bearer"


# Health check schema
class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    database: bool
    worker_running: bool
