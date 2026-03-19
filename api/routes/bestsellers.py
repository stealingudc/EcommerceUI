"""
Bestsellers API — Ranked view using mv_best_sellers_ranked MV.
Actual MV columns:
  product_id, parser_id, parser_name, vendor, name, url, image,
  latest_stock, price, ads7_cal, ads30_cal, ads90_cal, last_sold_day,
  search_vector, rnk_global_ads30, rnk_store_ads30
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from db.session import get_db
from api.routes.auth import get_current_user
from api.core.search_utils import build_search_conditions
from db.models import Product
from api.core.cache_utils import cache_invalidate
from api.core.mv_scheduler import refresh_bestseller_mvs

router = APIRouter()


@router.get("/api/bestsellers")
async def get_bestsellers(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    keywords: Optional[str] = Query(None),
    parser_id: Optional[int] = Query(None),
    top_n: Optional[int] = Query(None),
    stock_status: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_ads30: Optional[float] = Query(None),
    max_ads30: Optional[float] = Query(None),
    sort_by: str = Query("global_rank"),
    sort_dir: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50),
):
    """Bestsellers with filters. Uses actual MV column names."""
    conditions = []
    params: dict = {}

    if keywords:
        search_conds, search_params, _ = build_search_conditions(
            keywords, "bs.name", param_prefix="bs", extra_columns=["bs.vendor"]
        )
        conditions.extend(search_conds)
        params.update(search_params)
    if parser_id:
        conditions.append("bs.parser_id = :parser_id")
        params["parser_id"] = parser_id
    if top_n:
        conditions.append("bs.rnk_global_ads30 <= :top_n")
        params["top_n"] = top_n
    if stock_status == "in_stock":
        conditions.append("bs.latest_stock > 0")
    elif stock_status == "out_of_stock":
        conditions.append("(bs.latest_stock IS NULL OR bs.latest_stock = 0)")
    if min_price is not None:
        conditions.append("bs.price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        conditions.append("bs.price <= :max_price")
        params["max_price"] = max_price
    if min_ads30 is not None:
        conditions.append("bs.ads30_cal >= :min_ads30")
        params["min_ads30"] = min_ads30
    if max_ads30 is not None:
        conditions.append("bs.ads30_cal <= :max_ads30")
        params["max_ads30"] = max_ads30

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    safe_sort = {
        "global_rank": "bs.rnk_global_ads30", "name": "bs.name",
        "parser_name": "bs.parser_name", "vendor": "bs.vendor",
        "stock": "bs.latest_stock", "price": "bs.price",
        "ads30": "bs.ads30_cal", "ads7": "bs.ads7_cal",
    }
    sort_col = safe_sort.get(sort_by, "bs.rnk_global_ads30")
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM mv_best_sellers_ranked bs {where_clause}
    """), params).scalar() or 0

    offset = (page - 1) * page_size
    total_pages = max(1, (total + page_size - 1) // page_size)

    rows = db.execute(text(f"""
        SELECT
            bs.rnk_global_ads30 as global_rank,
            bs.rnk_store_ads30 as store_rank,
            bs.product_id, bs.name, bs.image,
            bs.parser_id, bs.parser_name, bs.vendor,
            bs.ads30_cal, bs.ads7_cal, bs.ads90_cal,
            bs.latest_stock, bs.price,
            bs.last_sold_day,
            p.shortlisted, p.pipeline_status, p.sales_ranking
        FROM mv_best_sellers_ranked bs
        JOIN products p ON p.id = bs.product_id
        {where_clause}
        ORDER BY {sort_col} {direction} NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": page_size, "offset": offset}).fetchall()

    products = [
        {
            "global_rank": r.global_rank,
            "store_rank": r.store_rank,
            "id": r.product_id,
            "name": r.name,
            "image": r.image,
            "parser_name": r.parser_name,
            "vendor": r.vendor,
            "ads30": float(r.ads30_cal) if r.ads30_cal else 0,
            "ads7": float(r.ads7_cal) if r.ads7_cal else 0,
            "stock": r.latest_stock,
            "price": float(r.price) if r.price else None,
            "shortlisted": r.shortlisted,
            "pipeline_status": r.pipeline_status,
            "sales_ranking": r.sales_ranking,
            "last_sold": r.last_sold_day.isoformat() if r.last_sold_day else None,
        }
        for r in rows
    ]

    return {
        "products": products,
        "total": total, "page": page,
        "page_size": page_size, "total_pages": total_pages,
    }


@router.post("/api/bestsellers/refresh")
async def refresh_bestsellers(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    refresh_bestseller_mvs(db)
    cache_invalidate("bestsellers")
    return {"message": "Bestsellers refreshed"}
