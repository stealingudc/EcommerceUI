"""
Configuration API — 3-tab CRUD: Product Categories, Parser Config, App Settings.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import ProductCategory, ProductGroup, Parser, ApplicationSetting
from api.routes.auth import get_current_user
from api.core.cache_utils import cache_invalidate
from api.core.mv_scheduler import refresh_all_mvs

router = APIRouter()


@router.get("/api/config/data")
async def get_config_data(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return all config data: categories, groups, parsers, settings."""
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    groups = db.query(ProductGroup).order_by(ProductGroup.name).all()
    parsers = db.query(Parser).order_by(Parser.name).all()
    settings = db.query(ApplicationSetting).order_by(ApplicationSetting.setting_key).all()

    return {
        "categories": [
            {"id": c.id, "name": c.name, "code": c.code} for c in categories
        ],
        "groups": [
            {"id": g.id, "name": g.name} for g in groups
        ],
        "parsers": [
            {
                "id": p.id, "name": p.name,
                "category": p.category,
            }
            for p in parsers
        ],
        "settings": [
            {
                "id": s.id, "key": s.setting_key,
                "value": s.setting_value, "type": s.value_type,
                "description": s.description,
            }
            for s in settings
        ],
    }


# ─── Product Categories ──────────────────────────────────────────────
@router.post("/api/config/product-categories")
async def create_product_category(
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    name = body.get("name", "").strip()
    code = body.get("code", "").strip().upper()
    if not name or not code:
        raise HTTPException(status_code=400, detail="Name and code are required")

    existing = db.query(ProductCategory).filter(ProductCategory.code == code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Code already exists")

    cat = ProductCategory(name=name, code=code)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "code": cat.code}


# ─── Parser-Defined Categories ───────────────────────────────────────
@router.post("/api/config/parser-defined-categories")
async def create_parser_category(
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    return {"message": f"Parser category '{name}' registered"}


# ─── Update Product Category ─────────────────────────────────────────
@router.put("/api/config/product-categories/{category_id}")
async def update_product_category(
    category_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    name = body.get("name", "").strip()
    code = body.get("code", "").strip().upper()
    if name:
        cat.name = name
    if code:
        cat.code = code
    db.commit()
    db.refresh(cat)
    cache_invalidate()
    return {"id": cat.id, "name": cat.name, "code": cat.code}


# ─── Delete Product Category ─────────────────────────────────────────
@router.delete("/api/config/product-categories/{category_id}")
async def delete_product_category(
    category_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
    cache_invalidate()
    return {"message": f"Category '{cat.name}' deleted"}


# ─── Update Product Group ────────────────────────────────────────────
@router.put("/api/config/product-groups/{group_id}")
async def update_product_group(
    group_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    group = db.query(ProductGroup).filter(ProductGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    group.name = name
    db.commit()
    db.refresh(group)
    cache_invalidate()
    return {"id": group.id, "name": group.name}


# ─── Delete Product Group ────────────────────────────────────────────
@router.delete("/api/config/product-groups/{group_id}")
async def delete_product_group(
    group_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    group = db.query(ProductGroup).filter(ProductGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    cache_invalidate()
    return {"message": f"Group '{group.name}' deleted"}


# ─── Product Groups ──────────────────────────────────────────────────
@router.post("/api/config/product-groups")
async def create_product_group(
    body: dict,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    group = ProductGroup(name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"id": group.id, "name": group.name}


# ─── Parser Category Assignment ──────────────────────────────────────
@router.post("/api/config/parsers/assign-categories")
async def assign_parser_categories(
    body: list,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    for assignment in body:
        parser_id = assignment.get("parser_id")
        category = assignment.get("category", "").strip()
        parser = db.query(Parser).filter(Parser.id == parser_id).first()
        if parser:
            parser.category = category
    db.commit()
    cache_invalidate("sidebar")
    return {"message": "Categories assigned"}


# ─── Application Settings ────────────────────────────────────────────
@router.post("/api/config/application-settings/update-via-form")
async def update_setting(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    setting_key: str = "",
    setting_value: str = "",
):
    setting = db.query(ApplicationSetting).filter(
        ApplicationSetting.setting_key == setting_key
    ).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    setting.setting_value = setting_value
    db.commit()
    cache_invalidate()
    return {"key": setting.setting_key, "value": setting.setting_value}


# ─── Tasks ────────────────────────────────────────────────────────────
@router.post("/api/config/tasks/update-sales-rankings")
async def trigger_sales_rankings(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Trigger sales ranking recalculation."""
    from db.settings_utils import get_setting

    high_threshold = get_setting(db, "SALES_RANKING_HIGH_THRESHOLD", 5.0)
    good_threshold = get_setting(db, "SALES_RANKING_GOOD_THRESHOLD", 2.0)
    slow_threshold = get_setting(db, "SALES_RANKING_SLOW_THRESHOLD", 0.5)

    db.execute(text("""
        UPDATE products p SET sales_ranking = (
            CASE
                WHEN pmv.avg_30d >= :high THEN 'High'
                WHEN pmv.avg_30d >= :good THEN 'Good'
                WHEN pmv.avg_30d >= :slow THEN 'Slow'
                ELSE 'Poor'
            END
        )
        FROM product_metrics_view pmv
        WHERE pmv.id = p.id
    """), {"high": high_threshold, "good": good_threshold, "slow": slow_threshold})
    db.commit()

    count = db.execute(text("SELECT COUNT(*) FROM products WHERE sales_ranking IS NOT NULL")).scalar()
    cache_invalidate()
    return {"message": "Sales rankings updated", "products_updated": count}


@router.post("/api/config/tasks/refresh-mvs")
async def trigger_refresh_mvs(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Trigger full MV refresh."""
    results = refresh_all_mvs(db)
    cache_invalidate()
    return {"message": "Materialized views refreshed", "results": results}
