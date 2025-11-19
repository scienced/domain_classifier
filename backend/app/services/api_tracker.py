"""
API usage tracking utility
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from ..models.models import ApiUsage, ApiProvider
from ..models.database import SessionLocal

logger = logging.getLogger(__name__)


class ApiTracker:
    """Track API usage for monitoring and cost management"""

    # Estimated costs per call (in USD)
    OPENAI_VISION_COST_PER_IMAGE = 0.003  # Approx for gpt-4o-mini with low detail
    FIRECRAWL_COST_PER_SCRAPE = 0.005     # Approx based on Firecrawl pricing

    @staticmethod
    def track_openai_vision(
        record_id: Optional[int] = None,
        run_id: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        tokens_used: Optional[int] = None,
        image_count: int = 1
    ):
        """
        Track OpenAI Vision API call.

        Args:
            record_id: Associated record ID
            run_id: Associated run ID
            success: Whether the API call succeeded
            error_message: Error message if failed
            tokens_used: Number of tokens used (if available)
            image_count: Number of images analyzed
        """
        try:
            db = SessionLocal()

            # Estimate cost based on image count
            estimated_cost = ApiTracker.OPENAI_VISION_COST_PER_IMAGE * image_count

            usage = ApiUsage(
                provider=ApiProvider.OPENAI,
                operation="vision_api",
                record_id=record_id,
                run_id=run_id,
                success=1 if success else 0,
                error_message=error_message[:500] if error_message else None,
                tokens_used=tokens_used,
                estimated_cost=estimated_cost
            )

            db.add(usage)
            db.commit()
            db.close()

            logger.debug(f"Tracked OpenAI Vision API call: success={success}, cost=${estimated_cost:.4f}")

        except Exception as e:
            logger.error(f"Failed to track OpenAI API usage: {e}")

    @staticmethod
    def track_firecrawl(
        record_id: Optional[int] = None,
        run_id: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Track Firecrawl API call.

        Args:
            record_id: Associated record ID
            run_id: Associated run ID
            success: Whether the API call succeeded
            error_message: Error message if failed
        """
        try:
            db = SessionLocal()

            usage = ApiUsage(
                provider=ApiProvider.FIRECRAWL,
                operation="scrape",
                record_id=record_id,
                run_id=run_id,
                success=1 if success else 0,
                error_message=error_message[:500] if error_message else None,
                estimated_cost=ApiTracker.FIRECRAWL_COST_PER_SCRAPE
            )

            db.add(usage)
            db.commit()
            db.close()

            logger.debug(f"Tracked Firecrawl API call: success={success}, cost=${ApiTracker.FIRECRAWL_COST_PER_SCRAPE:.4f}")

        except Exception as e:
            logger.error(f"Failed to track Firecrawl API usage: {e}")

    @staticmethod
    def get_usage_statistics(db: Session, days: int = 30) -> dict:
        """
        Get API usage statistics for the last N days.

        Args:
            db: Database session
            days: Number of days to look back

        Returns:
            Dictionary with usage statistics
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Query usage by provider
        stats = {
            'openai': {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_cost': 0.0,
                'total_tokens': 0
            },
            'firecrawl': {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_cost': 0.0
            },
            'total_cost': 0.0,
            'period_days': days
        }

        # OpenAI stats
        openai_usage = db.query(ApiUsage).filter(
            ApiUsage.provider == ApiProvider.OPENAI,
            ApiUsage.created_at >= cutoff_date
        ).all()

        for usage in openai_usage:
            stats['openai']['total_calls'] += 1
            if usage.success:
                stats['openai']['successful_calls'] += 1
            else:
                stats['openai']['failed_calls'] += 1
            if usage.estimated_cost:
                stats['openai']['total_cost'] += usage.estimated_cost
            if usage.tokens_used:
                stats['openai']['total_tokens'] += usage.tokens_used

        # Firecrawl stats
        firecrawl_usage = db.query(ApiUsage).filter(
            ApiUsage.provider == ApiProvider.FIRECRAWL,
            ApiUsage.created_at >= cutoff_date
        ).all()

        for usage in firecrawl_usage:
            stats['firecrawl']['total_calls'] += 1
            if usage.success:
                stats['firecrawl']['successful_calls'] += 1
            else:
                stats['firecrawl']['failed_calls'] += 1
            if usage.estimated_cost:
                stats['firecrawl']['total_cost'] += usage.estimated_cost

        # Total cost
        stats['total_cost'] = stats['openai']['total_cost'] + stats['firecrawl']['total_cost']

        return stats
