"""
Analytics API — Store analytics KPIs and cross-store charts.
Actual store_analytics_mv columns:
  parser_name, total_current_stock, total_sku_count, sold_last_24h,
  sold_last_7d, sold_last_30d, restocked_last_24h, restocked_last_7d,
  restocked_last_30d, total_revenue_30d, total_inventory_value,
  active_sku_count_30d, average_order_value, active_sku_ratio,
  revenue_per_active_sku, sell_through_rate, days_of_inventory, stock_turn
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from api.routes.auth import get_current_user
from api.core.cache_utils import cache_get, cache_set, cache_invalidate
from api.core.mv_scheduler import refresh_mv

router = APIRouter()


@router.get("/api/store-analytics")
async def get_store_analytics(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Store-level KPIs from store_analytics_mv using actual column names."""
    cached = cache_get("store_analytics")
    if cached:
        return cached

    rows = db.execute(text("""
        SELECT * FROM store_analytics_mv ORDER BY parser_name
    """)).fetchall()

    stores = []
    for r in rows:
        d = dict(r._mapping)
        stores.append({
            "store": d.get("parser_name", "Unknown"),
            "products": d.get("total_sku_count", 0),
            "active_products": d.get("active_sku_count_30d", 0),
            "total_stock": d.get("total_current_stock", 0),
            "avg_price": float(d.get("average_order_value", 0) or 0),
            "vendors": 0,  # Not in this MV
            "revenue_30d": float(d.get("total_revenue_30d", 0) or 0),
            "units_sold_30d": d.get("sold_last_30d", 0) or 0,
            "sell_through_pct": float(d.get("sell_through_rate", 0) or 0) * 100,
            "stock_turnover": float(d.get("stock_turn", 0) or 0),
            "days_of_inventory": float(d.get("days_of_inventory", 0) or 0),
            "inventory_value": float(d.get("total_inventory_value", 0) or 0),
        })

    data = {"stores": stores}
    cache_set("store_analytics", data, ttl=300)
    return data


@router.post("/api/store-analytics/refresh")
async def refresh_store_analytics(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    refresh_mv(db, "store_analytics_mv")
    cache_invalidate("store_analytics")
    return {"message": "Store analytics refreshed"}


@router.get("/api/analytics")
async def get_analytics(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Cross-store analytics for chart panels."""
    cached = cache_get("analytics_charts")
    if cached:
        return cached

    # Vendor distribution
    vendor_dist = db.execute(text("""
        SELECT vendor, COUNT(*) as count FROM products
        WHERE vendor IS NOT NULL GROUP BY vendor ORDER BY count DESC LIMIT 20
    """)).fetchall()

    # Pipeline distribution
    pipeline_dist = db.execute(text("""
        SELECT pipeline_status, COUNT(*) as count FROM products
        WHERE pipeline_status IS NOT NULL GROUP BY pipeline_status ORDER BY count DESC
    """)).fetchall()

    # Sales ranking distribution
    ranking_dist = db.execute(text("""
        SELECT sales_ranking, COUNT(*) as count FROM products
        WHERE sales_ranking IS NOT NULL GROUP BY sales_ranking ORDER BY count DESC
    """)).fetchall()

    # Top parsers by product count
    parser_counts = db.execute(text("""
        SELECT par.name, COUNT(*) as count FROM products p
        JOIN parsers par ON par.id = p.parser_id
        GROUP BY par.name ORDER BY count DESC LIMIT 15
    """)).fetchall()

    data = {
        "vendors": [{"label": r.vendor, "value": r.count} for r in vendor_dist],
        "pipeline": [{"label": r.pipeline_status, "value": r.count} for r in pipeline_dist],
        "rankings": [{"label": r.sales_ranking, "value": r.count} for r in ranking_dist],
        "per_store": [{"label": r.name, "value": r.count} for r in parser_counts],
    }
    cache_set("analytics_charts", data, ttl=300)
    return data
