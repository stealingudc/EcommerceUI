"""
Parser Status API — Health monitoring with dual status system (run + activity),
coverage bars, 24h/48h update counts, and run logs.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from db.session import get_db
from db.models import ParserRunLog
from api.routes.auth import get_current_user
from api.core.cache_utils import cache_get, cache_set

router = APIRouter()


@router.get("/api/parser-status")
async def get_parser_status(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Parser health dashboard with dual status system and coverage metrics."""
    cached = cache_get("parser_status")
    if cached:
        return cached

    rows = db.execute(text("""
        SELECT
            p.id, p.name, p.url, p.category,
            (SELECT COUNT(*) FROM products WHERE parser_id = p.id) as total_products,
            (SELECT COUNT(*) FROM products prod
             JOIN stock_history sh ON sh.product_id = prod.id
             WHERE prod.parser_id = p.id
             AND sh.timestamp >= NOW() - INTERVAL '24 hours'
            ) as products_24h,
            (SELECT COUNT(*) FROM products prod
             JOIN stock_history sh ON sh.product_id = prod.id
             WHERE prod.parser_id = p.id
             AND sh.timestamp >= NOW() - INTERVAL '48 hours'
            ) as products_48h,
            prl.status as last_status,
            prl.finished_at as last_run,
            prl.products_found,
            prl.duration_seconds
        FROM parsers p
        LEFT JOIN LATERAL (
            SELECT status, finished_at, products_found, duration_seconds
            FROM parser_run_logs WHERE parser_id = p.id
            ORDER BY finished_at DESC NULLS LAST LIMIT 1
        ) prl ON true
        ORDER BY p.name
    """)).fetchall()

    # Compute average duration per parser
    avg_durations = {}
    avg_rows = db.execute(text("""
        SELECT parser_id, AVG(duration_seconds) as avg_dur
        FROM parser_run_logs
        WHERE duration_seconds IS NOT NULL
        GROUP BY parser_id
    """)).fetchall()
    for r in avg_rows:
        avg_durations[r.parser_id] = float(r.avg_dur)

    parsers = []
    for r in rows:
        total = r.total_products or 0
        p24h = r.products_24h or 0
        p48h = r.products_48h or 0

        # Coverage percentage
        coverage_pct = round((p24h / total) * 100, 1) if total > 0 else 0

        # Run status (from last run log)
        run_status = "Unknown"
        if r.last_status in ("ok", "success", "completed"):
            run_status = "Healthy"
        elif r.last_status in ("error", "failed"):
            run_status = "Error"
        elif r.last_status == "running":
            run_status = "Running"
        elif r.last_run:
            hours_since = (datetime.utcnow() - r.last_run).total_seconds() / 3600
            if hours_since > 48:
                run_status = "Stale"
            else:
                run_status = "Warning"

        # Activity status (from update percentages)
        if total == 0:
            activity_status = "Inactive"
        else:
            pct_24h = (p24h / total) * 100
            pct_48h = (p48h / total) * 100
            if pct_24h >= 50:
                activity_status = "Active"
            elif pct_24h >= 10:
                activity_status = "Partial"
            elif pct_48h >= 10:
                activity_status = "Stale"
            else:
                activity_status = "Inactive"

        hours_since_run = None
        if r.last_run:
            hours_since_run = round((datetime.utcnow() - r.last_run).total_seconds() / 3600, 1)

        parsers.append({
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "total_products": total,
            "products_24h": p24h,
            "products_48h": p48h,
            "coverage_pct": coverage_pct,
            "last_stock_update": r.last_run.isoformat() if r.last_run else None,
            "run_status": run_status,
            "activity_status": activity_status,
            "last_run_status": r.last_status,
            "avg_duration": avg_durations.get(r.id),
            "hours_since_run": hours_since_run,
        })

    data = {"parsers": parsers}
    cache_set("parser_status", data, ttl=60)
    return data


@router.get("/api/parser-runs")
async def get_parser_runs(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    parser_id: Optional[int] = Query(None),
    page: int = 1,
    page_size: int = 50,
):
    """Recent parser run logs — matches frontend ParserStatus.tsx field names."""
    query = db.query(ParserRunLog).order_by(ParserRunLog.finished_at.desc())
    if parser_id:
        query = query.filter(ParserRunLog.parser_id == parser_id)

    total = query.count()
    offset = (page - 1) * page_size
    runs = query.offset(offset).limit(page_size).all()

    return {
        "runs": [
            {
                "id": r.id,
                "parser_id": r.parser_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "products_found": r.products_found or 0,
                "products_parsed_success": getattr(r, 'products_parsed_success', 0) or 0,
                "products_parsed_failed": getattr(r, 'products_parsed_failed', 0) or 0,
                "duration_seconds": float(r.duration_seconds) if r.duration_seconds else None,
                "error_message": r.error_message if hasattr(r, 'error_message') else None,
            }
            for r in runs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
