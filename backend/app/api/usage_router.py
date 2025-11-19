"""
API endpoints for usage tracking and statistics
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from ..models.database import get_db
from ..models.models import ApiUsage, ApiProvider
from ..services.api_tracker import ApiTracker
from ..auth import get_current_user

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/statistics")
async def get_usage_statistics(
    days: int = 30,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    """
    Get API usage statistics for the last N days.

    Args:
        days: Number of days to look back (default: 30)

    Returns:
        Usage statistics including call counts and estimated costs
    """
    try:
        stats = ApiTracker.get_usage_statistics(db, days=days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")


@router.get("/history")
async def get_usage_history(
    days: int = 30,
    provider: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    """
    Get detailed usage history.

    Args:
        days: Number of days to look back
        provider: Filter by provider (openai or firecrawl)
        limit: Maximum number of records to return

    Returns:
        List of API usage records
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(ApiUsage).filter(ApiUsage.created_at >= cutoff_date)

        if provider:
            if provider == "openai":
                query = query.filter(ApiUsage.provider == ApiProvider.OPENAI)
            elif provider == "firecrawl":
                query = query.filter(ApiUsage.provider == ApiProvider.FIRECRAWL)

        usage_records = query.order_by(ApiUsage.created_at.desc()).limit(limit).all()

        return {
            "records": [
                {
                    "id": record.id,
                    "provider": record.provider.value,
                    "operation": record.operation,
                    "success": bool(record.success),
                    "error_message": record.error_message,
                    "tokens_used": record.tokens_used,
                    "estimated_cost": record.estimated_cost,
                    "created_at": record.created_at.isoformat()
                }
                for record in usage_records
            ],
            "total": len(usage_records)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")


@router.get("/daily-breakdown")
async def get_daily_breakdown(
    days: int = 30,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user)
):
    """
    Get daily breakdown of API usage.

    Args:
        days: Number of days to look back

    Returns:
        Daily usage statistics
    """
    try:
        from sqlalchemy import func, cast, Date

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Query for daily breakdown
        daily_stats = db.query(
            cast(ApiUsage.created_at, Date).label('date'),
            ApiUsage.provider,
            func.count(ApiUsage.id).label('call_count'),
            func.sum(ApiUsage.estimated_cost).label('total_cost'),
            func.sum(ApiUsage.success).label('successful_calls')
        ).filter(
            ApiUsage.created_at >= cutoff_date
        ).group_by(
            cast(ApiUsage.created_at, Date),
            ApiUsage.provider
        ).order_by(
            cast(ApiUsage.created_at, Date).desc()
        ).all()

        # Format results
        results = []
        for stat in daily_stats:
            results.append({
                "date": stat.date.isoformat(),
                "provider": stat.provider.value,
                "call_count": stat.call_count,
                "successful_calls": stat.successful_calls,
                "failed_calls": stat.call_count - stat.successful_calls,
                "total_cost": float(stat.total_cost) if stat.total_cost else 0.0
            })

        return {"daily_breakdown": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving daily breakdown: {str(e)}")
