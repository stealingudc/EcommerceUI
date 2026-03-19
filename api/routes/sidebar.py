"""
Sidebar API — Parser counts and pipeline status counts for navigation.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from api.routes.auth import get_current_user
from api.core.cache_utils import cache_get, cache_set

router = APIRouter()


@router.get("/api/sidebar")
async def get_sidebar(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return parser list with product counts + pipeline status counts."""
    # Check cache
    cached = cache_get("sidebar_data")
    if cached:
        return cached

    # Parser counts (grouped by category)
    parser_rows = db.execute(text("""
        SELECT id, name, category, product_count
        FROM mv_sidebar_parser_counts
        ORDER BY category NULLS LAST, name
    """)).fetchall()

    parsers = [
        {
            "id": r.id, "name": r.name,
            "category": r.category, "product_count": r.product_count
        }
        for r in parser_rows
    ]

    # Pipeline status counts — LIVE query (only ~1300 non-None products, instant)
    status_rows = db.execute(text("""
        SELECT pipeline_status, COUNT(*) as product_count
        FROM products
        WHERE pipeline_status IS NOT NULL
          AND pipeline_status != 'None'
        GROUP BY pipeline_status
        ORDER BY pipeline_status
    """)).fetchall()

    # Explicit slug mapping — must match product_pipeline.py status_map keys
    STATUS_TO_SLUG = {
        "New": "new",
        "Waiting for Supplier Info": "supplier-info",
        "Financial Review": "financial-review",
        "Market Research": "market-research",
        "Approved": "approved",
        "Hold": "hold",
        "Discarded": "discarded",
    }

    pipeline_statuses = [
        {
            "status": r.pipeline_status,
            "slug": STATUS_TO_SLUG.get(r.pipeline_status, r.pipeline_status.lower().replace(" ", "-")),
            "count": r.product_count,
        }
        for r in status_rows
        if r.pipeline_status in STATUS_TO_SLUG
    ]

    data = {"parsers": parsers, "pipeline_statuses": pipeline_statuses}
    cache_set("sidebar_data", data, ttl=15)
    return data
