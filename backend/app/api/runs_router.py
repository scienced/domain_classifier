"""
Classification runs API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import csv
import io
from datetime import datetime

from ..models.database import get_db
from ..models.models import Run, Record, RunStatus, RecordStatus, Label
from ..schemas.schemas import (
    RunCreate, RunResponse, RunList, RunStatusResponse,
    RunStatistics, DomainUpload
)
from ..auth import get_current_user

router = APIRouter()


@router.get("/", response_model=RunList)
async def list_runs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    List all classification runs with pagination
    """
    offset = (page - 1) * page_size

    total = db.query(Run).count()
    runs = db.query(Run).order_by(Run.created_at.desc()).offset(offset).limit(page_size).all()

    return RunList(
        runs=[RunResponse.model_validate(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run_data: RunCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Create a new classification run
    """
    run = Run(
        name=run_data.name,
        status=RunStatus.PENDING,
        total_records=0,
        processed_records=0
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return RunResponse.model_validate(run)


@router.post("/{run_id}/upload")
async def upload_domains(
    run_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Upload CSV file with domains for a run
    """
    # Get run
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Can only upload domains to pending runs"
        )

    # Read CSV
    try:
        content = await file.read()
        csv_file = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(csv_file)

        # Find domain column (case-insensitive)
        fieldnames = reader.fieldnames
        domain_column = None
        for field in fieldnames:
            if field.lower() == 'domain':
                domain_column = field
                break

        if not domain_column:
            raise HTTPException(
                status_code=400,
                detail="CSV must contain a 'domain' column"
            )

        # Read domains
        domains = []
        for row in reader:
            domain = row.get(domain_column, '').strip()
            if domain:
                domains.append(domain)

        if not domains:
            raise HTTPException(
                status_code=400,
                detail="No valid domains found in CSV"
            )

        # Create records
        for domain in domains:
            record = Record(
                run_id=run.id,
                domain=domain,
                status=RecordStatus.PENDING
            )
            db.add(record)

        # Update run
        run.total_records = len(domains)
        db.commit()

        return {
            "message": f"Uploaded {len(domains)} domains",
            "total_records": len(domains)
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV file encoding. Please use UTF-8."
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing CSV: {str(e)}"
        )


@router.post("/{run_id}/upload-json", response_model=dict)
async def upload_domains_json(
    run_id: int,
    data: DomainUpload,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Upload domains as JSON array for a run
    """
    # Get run
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Can only upload domains to pending runs"
        )

    # Create records
    for domain in data.domains:
        domain = domain.strip()
        if domain:
            record = Record(
                run_id=run.id,
                domain=domain,
                status=RecordStatus.PENDING
            )
            db.add(record)

    # Update run
    run.total_records = len(data.domains)
    db.commit()

    return {
        "message": f"Uploaded {len(data.domains)} domains",
        "total_records": len(data.domains)
    }


@router.post("/{run_id}/start", response_model=RunResponse)
async def start_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Start processing a run (worker will pick it up)
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Can only start pending runs"
        )

    if run.total_records == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot start run with no domains"
        )

    # Mark as pending (worker will pick it up)
    run.status = RunStatus.PENDING
    db.commit()
    db.refresh(run)

    return RunResponse.model_validate(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Get run details
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse.model_validate(run)


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Get run status with ETA
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Calculate ETA
    eta_seconds = None
    if run.status == RunStatus.RUNNING and run.processed_records > 0:
        # Average time per record
        if run.started_at:
            elapsed_seconds = (datetime.utcnow() - run.started_at).total_seconds()
            avg_seconds_per_record = elapsed_seconds / run.processed_records
            remaining_records = run.total_records - run.processed_records
            eta_seconds = avg_seconds_per_record * remaining_records

    return RunStatusResponse(
        id=run.id,
        name=run.name,
        status=run.status,
        total_records=run.total_records,
        processed_records=run.processed_records,
        progress_percentage=run.progress_percentage,
        eta_seconds=eta_seconds,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at
    )


@router.get("/{run_id}/statistics", response_model=RunStatistics)
async def get_run_statistics(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Get run statistics
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    records = db.query(Record).filter(Record.run_id == run_id).all()

    # Count by status
    completed_records = sum(1 for r in records if r.status == RecordStatus.COMPLETED)
    error_records = sum(1 for r in records if r.status == RecordStatus.ERROR)

    # Count by label
    label_distribution = {}
    for label in Label:
        count = sum(1 for r in records if r.label == label)
        if count > 0:
            label_distribution[label.value] = count

    # Count by stage
    stage_distribution = {}
    for record in records:
        if record.stage_used:
            stage_distribution[record.stage_used] = stage_distribution.get(record.stage_used, 0) + 1

    # Calculate average confidence
    confidences = [r.confidence for r in records if r.confidence is not None]
    average_confidence = sum(confidences) / len(confidences) if confidences else None

    # Calculate average processing time
    processing_times = []
    for record in records:
        if record.started_at and record.processed_at:
            duration = (record.processed_at - record.started_at).total_seconds()
            processing_times.append(duration)
    average_processing_time = sum(processing_times) / len(processing_times) if processing_times else None

    return RunStatistics(
        total_records=run.total_records,
        completed_records=completed_records,
        error_records=error_records,
        label_distribution=label_distribution,
        stage_distribution=stage_distribution,
        average_confidence=average_confidence,
        average_processing_time_seconds=average_processing_time
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Delete a run and all its records
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status == RunStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a running run"
        )

    db.delete(run)
    db.commit()

    return None
