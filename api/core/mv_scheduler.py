"""
Materialized View Scheduler — Refreshes all MVs in dependency order.
Can be triggered hourly on startup or manually.
"""
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# MVs in dependency order (dependencies first)
MV_REFRESH_ORDER = [
    "mv_latest_stock",
    "mv_latest_price",
    "mv_stock_last_per_day",
    "mv_product_daily_sales",
    "product_metrics_view",
    "mv_product_scores",
    "mv_best_sellers",
    "mv_best_sellers_ranked",
    "mv_parser_activity",
    "mv_sidebar_parser_counts",
    "mv_sidebar_pipeline_status_counts",
    "mv_vendor_counts_all",
    "mv_vendor_counts_by_parser",
    "store_analytics_mv",
]


def mv_exists(db: Session, mv_name: str) -> bool:
    """Check if a materialized view exists."""
    result = db.execute(
        text("SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = :name)"),
        {"name": mv_name}
    )
    return result.scalar()


def refresh_mv(db: Session, mv_name: str) -> bool:
    """Refresh a single materialized view. Returns True on success."""
    if not mv_exists(db, mv_name):
        logger.debug(f"MV '{mv_name}' does not exist, skipping")
        return False

    try:
        db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}"))
        db.commit()
        logger.info(f"Refreshed MV: {mv_name} (concurrent)")
        return True
    except Exception:
        db.rollback()
        try:
            db.execute(text(f"REFRESH MATERIALIZED VIEW {mv_name}"))
            db.commit()
            logger.info(f"Refreshed MV: {mv_name} (blocking)")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to refresh MV '{mv_name}': {e}")
            return False


def refresh_all_mvs(db: Session) -> dict:
    """Refresh all MVs in dependency order. Returns status per MV."""
    results = {}
    for mv_name in MV_REFRESH_ORDER:
        results[mv_name] = refresh_mv(db, mv_name)
    return results


def refresh_sidebar_mvs(db: Session):
    """Refresh only sidebar-related MVs."""
    for mv_name in ["mv_sidebar_parser_counts", "mv_sidebar_pipeline_status_counts"]:
        refresh_mv(db, mv_name)


def refresh_dashboard_mvs(db: Session):
    """Refresh dashboard-related MVs in dependency order."""
    for mv_name in [
        "mv_latest_stock", "mv_latest_price", "mv_stock_last_per_day",
        "mv_product_daily_sales", "product_metrics_view", "mv_product_scores",
        "mv_sidebar_parser_counts", "mv_sidebar_pipeline_status_counts",
        "mv_vendor_counts_all", "mv_vendor_counts_by_parser",
    ]:
        refresh_mv(db, mv_name)


def refresh_bestseller_mvs(db: Session):
    """Refresh bestseller-related MVs in dependency order."""
    for mv_name in [
        "mv_latest_stock", "mv_latest_price", "mv_stock_last_per_day",
        "mv_product_daily_sales", "mv_best_sellers", "mv_best_sellers_ranked",
    ]:
        refresh_mv(db, mv_name)
