"""
System Monitoring API — MV status, refresh history, next scheduled refresh,
score distribution, and manual refresh triggers.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from api.routes.auth import get_current_user
from api.core.mv_scheduler import MV_REFRESH_ORDER, refresh_mv, mv_exists

router = APIRouter()


def _get_mv_info(db: Session) -> list[dict]:
    """Get last refresh time and row count for each MV."""
    results = []
    for mv_name in MV_REFRESH_ORDER:
        exists = mv_exists(db, mv_name)
        info = {
            "name": mv_name,
            "exists": exists,
            "row_count": None,
            "size_bytes": None,
            "size_pretty": None,
        }

        if exists:
            try:
                # Row count (use reltuples for speed on large MVs)
                row = db.execute(text(
                    "SELECT reltuples::bigint FROM pg_class WHERE relname = :name"
                ), {"name": mv_name}).fetchone()
                info["row_count"] = int(row[0]) if row and row[0] >= 0 else None

                # Size
                row = db.execute(text(
                    "SELECT pg_total_relation_size(:name), pg_size_pretty(pg_total_relation_size(:name))"
                ), {"name": mv_name}).fetchone()
                if row:
                    info["size_bytes"] = row[0]
                    info["size_pretty"] = row[1]
            except Exception:
                pass

        results.append(info)

    return results


@router.get("/api/system/monitoring")
async def get_system_monitoring(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Returns system health data: MV statuses, next scheduled refresh,
    database stats, and score distribution.
    """
    # MV info
    mv_info = _get_mv_info(db)

    # Next scheduled refresh (daily at 8:00 AM)
    now = datetime.now()
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    next_refresh_at = target.isoformat()
    seconds_until_refresh = int((target - now).total_seconds())

    # Database size
    db_size = None
    try:
        row = db.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )).fetchone()
        db_size = row[0] if row else None
    except Exception:
        pass

    # Table counts
    table_stats = {}
    for table in ["products", "stock_history", "price_history"]:
        try:
            row = db.execute(text(
                f"SELECT reltuples::bigint FROM pg_class WHERE relname = :name"
            ), {"name": table}).fetchone()
            table_stats[table] = int(row[0]) if row and row[0] >= 0 else None
        except Exception:
            table_stats[table] = None

    # Score distribution (if mv_product_scores exists)
    score_distribution = {}
    if mv_exists(db, "mv_product_scores"):
        try:
            rows = db.execute(text(
                "SELECT grade, COUNT(*) as cnt FROM mv_product_scores GROUP BY grade ORDER BY grade"
            )).fetchall()
            score_distribution = {row[0]: row[1] for row in rows}
        except Exception:
            pass

    return {
        "materialized_views": mv_info,
        "schedule": {
            "type": "daily",
            "target_hour": "08:00",
            "next_refresh_at": next_refresh_at,
            "seconds_until_refresh": seconds_until_refresh,
        },
        "database": {
            "size": db_size,
            "table_counts": table_stats,
        },
        "score_distribution": score_distribution,
    }


@router.post("/api/system/refresh-mv/{mv_name}")
async def trigger_single_mv_refresh(
    mv_name: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Trigger refresh for a single MV."""
    if mv_name not in MV_REFRESH_ORDER:
        return {"success": False, "error": f"Unknown MV: {mv_name}"}

    success = refresh_mv(db, mv_name)
    return {"success": success, "mv_name": mv_name}
