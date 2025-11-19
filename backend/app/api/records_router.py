"""
Records API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import Optional
import csv
import io

from ..models.database import get_db
from ..models.models import Record, Run, Override, RecordStatus, Label
from ..schemas.schemas import (
    RecordResponse, RecordList, RecordFilter, OverrideCreate, OverrideResponse
)
from ..auth import get_current_user

router = APIRouter()


@router.get("/run/{run_id}", response_model=RecordList)
async def list_records(
    run_id: int,
    page: int = 1,
    page_size: int = 50,
    label: Optional[Label] = None,
    status: Optional[RecordStatus] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    has_error: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    List records for a run with filtering and pagination
    """
    # Check run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Build query
    query = db.query(Record).filter(Record.run_id == run_id)

    # Apply filters
    if label:
        query = query.filter(Record.label == label)
    if status:
        query = query.filter(Record.status == status)
    if min_confidence is not None:
        query = query.filter(Record.confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(Record.confidence <= max_confidence)
    if has_error is not None:
        if has_error:
            query = query.filter(Record.error.isnot(None))
        else:
            query = query.filter(Record.error.is_(None))

    # Get total
    total = query.count()

    # Pagination
    offset = (page - 1) * page_size
    records = query.order_by(Record.created_at).offset(offset).limit(page_size).all()

    return RecordList(
        records=[RecordResponse.model_validate(record) for record in records],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Get record details
    """
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return RecordResponse.model_validate(record)


@router.post("/{record_id}/override", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)
async def create_override(
    record_id: int,
    override_data: OverrideCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Create a manual override for a record's classification
    """
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if not record.label:
        raise HTTPException(
            status_code=400,
            detail="Cannot override a record that hasn't been classified yet"
        )

    # Create override
    override = Override(
        record_id=record.id,
        old_label=record.label,
        new_label=override_data.new_label,
        user_note=override_data.user_note
    )

    # Update record label
    record.label = override_data.new_label

    db.add(override)
    db.commit()
    db.refresh(override)

    return OverrideResponse.model_validate(override)


@router.get("/run/{run_id}/export")
async def export_records_csv(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Export run records as CSV
    """
    # Check run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get all records
    records = db.query(Record).filter(Record.run_id == run_id).all()

    # Create CSV
    output = io.StringIO()
    fieldnames = [
        'domain', 'label', 'confidence', 'text_score', 'vision_score',
        'reasons', 'stage_used', 'image_count', 'http_status', 'final_url',
        'nav_count', 'heading_count', 'error', 'status',
        'created_at', 'started_at', 'processed_at', 'is_overridden'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for record in records:
        writer.writerow({
            'domain': record.domain,
            'label': record.label.value if record.label else '',
            'confidence': record.confidence if record.confidence is not None else '',
            'text_score': record.text_score if record.text_score is not None else '',
            'vision_score': record.vision_score if record.vision_score is not None else '',
            'reasons': record.reasons or '',
            'stage_used': record.stage_used or '',
            'image_count': record.image_count,
            'http_status': record.http_status if record.http_status is not None else '',
            'final_url': record.final_url or '',
            'nav_count': record.nav_count,
            'heading_count': record.heading_count,
            'error': record.error or '',
            'status': record.status.value,
            'created_at': record.created_at.isoformat() if record.created_at else '',
            'started_at': record.started_at.isoformat() if record.started_at else '',
            'processed_at': record.processed_at.isoformat() if record.processed_at else '',
            'is_overridden': record.is_overridden
        })

    # Return CSV response
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=run_{run_id}_results.csv"
        }
    )
