"""
Background worker for processing classification runs
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models.database import SessionLocal
from ..models.models import Run, Record, RunStatus, RecordStatus, Label
from ..config import settings
from .classifier_service import get_classifier

logger = logging.getLogger(__name__)


class Worker:
    """
    Background worker that processes pending classification runs
    """

    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.current_run_id: Optional[int] = None
        self.current_domain: Optional[str] = None

    async def run(self):
        """Main worker loop"""
        self.is_running = True
        logger.info("Background worker started")

        try:
            while not self.should_stop:
                # Poll for pending work
                await self._process_next_run()

                # Wait before next poll
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("Background worker stopped")

    async def stop(self):
        """Stop worker gracefully"""
        logger.info("Stopping background worker...")
        self.should_stop = True

        # Wait for current domain to finish (max 60 seconds)
        for _ in range(60):
            if not self.is_running:
                break
            await asyncio.sleep(1)

    async def _process_next_run(self):
        """Find and process next pending run"""
        db: Session = SessionLocal()

        try:
            # Find next pending or running run
            run = db.query(Run).filter(
                Run.status.in_([RunStatus.PENDING, RunStatus.RUNNING])
            ).order_by(Run.created_at).first()

            if not run:
                return

            self.current_run_id = run.id
            logger.info(f"Processing run {run.id}: {run.name}")

            # Mark run as running if pending
            if run.status == RunStatus.PENDING:
                run.status = RunStatus.RUNNING
                run.started_at = datetime.utcnow()
                db.commit()

            # Process pending records
            while not self.should_stop:
                # Get next pending record
                record = db.query(Record).filter(
                    Record.run_id == run.id,
                    Record.status == RecordStatus.PENDING
                ).first()

                if not record:
                    # No more pending records, mark run as completed
                    run.status = RunStatus.COMPLETED
                    run.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Run {run.id} completed")
                    break

                # Process record
                await self._process_record(record, db)

                # Update run progress counter
                run.processed_records = db.query(Record).filter(
                    Record.run_id == run.id,
                    Record.status.in_([RecordStatus.COMPLETED, RecordStatus.ERROR])
                ).count()
                db.commit()

        except Exception as e:
            logger.error(f"Error processing run: {e}", exc_info=True)
            if self.current_run_id:
                run = db.query(Run).filter(Run.id == self.current_run_id).first()
                if run:
                    run.status = RunStatus.FAILED
                    db.commit()
        finally:
            self.current_run_id = None
            self.current_domain = None
            db.close()

    async def _process_record(self, record: Record, db: Session):
        """Process a single record"""
        self.current_domain = record.domain
        logger.info(f"Processing record {record.id}: {record.domain}")

        # Mark record as processing
        record.status = RecordStatus.PROCESSING
        record.started_at = datetime.utcnow()
        db.commit()

        try:
            # Get classifier
            classifier = await get_classifier()

            # Classify domain
            result = await classifier.classify_domain(record.domain)

            # Update record with results
            record.label = self._map_label(result.get('label'))
            record.confidence = result.get('confidence')
            record.text_score = result.get('text_score')
            record.vision_score = result.get('vision_score')
            record.reasons = result.get('reasons')
            record.stage_used = result.get('stage_used')
            record.image_count = result.get('image_count', 0)
            record.http_status = result.get('http_status')
            record.final_url = result.get('final_url')
            record.nav_count = result.get('nav_count', 0)
            record.heading_count = result.get('heading_count', 0)
            record.error = result.get('error')
            record.status = RecordStatus.COMPLETED if not result.get('error') else RecordStatus.ERROR
            record.processed_at = datetime.utcnow()

            # Commit record updates
            db.commit()

            # Format confidence for logging
            conf_str = f"{record.confidence:.3f}" if record.confidence is not None else "N/A"
            logger.info(
                f"Record {record.id} completed: {record.label} "
                f"(confidence: {conf_str})"
            )

        except Exception as e:
            logger.error(f"Error processing record {record.id}: {e}", exc_info=True)
            record.status = RecordStatus.ERROR
            record.error = str(e)[:500]
            record.processed_at = datetime.utcnow()
            db.commit()

    def _map_label(self, label_str: Optional[str]) -> Label:
        """Map label string to Label enum"""
        if not label_str:
            return Label.ERROR

        label_map = {
            'Pure Bodywear': Label.PURE_BODYWEAR,
            'Bodywear Leaning': Label.BODYWEAR_LEANING,
            'Needs Review': Label.NEEDS_REVIEW,
            'Generalist': Label.GENERALIST,
            'Error': Label.ERROR
        }

        return label_map.get(label_str, Label.ERROR)
