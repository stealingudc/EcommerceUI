"""
Product Detail API — Single product view with stock/price history.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Product
from api.routes.auth import get_current_user

router = APIRouter()


@router.get("/api/product/{product_id}")
async def get_product_detail(
    product_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return product info + stock/price history for charts."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Current stock
    stock_row = db.execute(text("""
        SELECT quantity FROM mv_latest_stock WHERE product_id = :pid
    """), {"pid": product_id}).fetchone()

    # Current price
    price_row = db.execute(text("""
        SELECT price FROM mv_latest_price WHERE product_id = :pid
    """), {"pid": product_id}).fetchone()

    # Stock history
    stock_history = db.execute(text("""
        SELECT quantity, timestamp FROM stock_history
        WHERE product_id = :pid ORDER BY timestamp
    """), {"pid": product_id}).fetchall()

    # Price history
    price_history = db.execute(text("""
        SELECT value, timestamp FROM price_history
        WHERE product_id = :pid ORDER BY timestamp
    """), {"pid": product_id}).fetchall()

    # Parser name
    parser_name = None
    if product.parser:
        parser_name = product.parser.name

    return {
        "id": product.id,
        "name": product.name,
        "url": product.url,
        "image": product.image,
        "vendor": product.vendor,
        "parser_name": parser_name,
        "pipeline_status": product.pipeline_status,
        "shortlisted": product.shortlisted,
        "current_stock": stock_row.quantity if stock_row else None,
        "current_price": float(price_row.price) if price_row else None,
        "stock_history": [
            {"quantity": r.quantity, "timestamp": r.timestamp.isoformat() if r.timestamp else None}
            for r in stock_history
        ],
        "price_history": [
            {"value": float(r.value), "timestamp": r.timestamp.isoformat() if r.timestamp else None}
            for r in price_history
        ],
    }


@router.get("/api/product/{product_id}/similar")
async def get_similar_products(
    product_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Find similar products using pg_trgm name similarity, sorted by score."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Use pg_trgm similarity on unaccented product names.
    # We extract the key part of the name (first ~60 chars) to focus similarity
    # on the product type rather than variant details.
    rows = db.execute(text("""
        SELECT
            p.id,
            p.name,
            p.image,
            p.url,
            p.vendor,
            p.pipeline_status,
            par.name AS parser_name,
            ls.quantity AS current_stock,
            lp.price AS current_price,
            COALESCE(ps.total_score, 0) AS total_score,
            COALESCE(ps.grade, 'F') AS grade,
            similarity(unaccent(lower(p.name)), unaccent(lower(:product_name))) AS sim
        FROM products p
        LEFT JOIN parsers par ON par.id = p.parser_id
        LEFT JOIN mv_latest_stock ls ON ls.product_id = p.id
        LEFT JOIN mv_latest_price lp ON lp.product_id = p.id
        LEFT JOIN mv_product_scores ps ON ps.product_id = p.id
        WHERE p.id != :pid
          AND similarity(unaccent(lower(p.name)), unaccent(lower(:product_name))) > 0.15
        ORDER BY sim DESC, total_score DESC
        LIMIT :lim
    """), {
        "pid": product_id,
        "product_name": product.name[:80],  # Focus on core product name
        "lim": limit,
    }).fetchall()

    return {
        "products": [
            {
                "id": r.id,
                "name": r.name,
                "image": r.image,
                "url": r.url,
                "vendor": r.vendor,
                "pipeline_status": r.pipeline_status,
                "parser_name": r.parser_name,
                "current_stock": r.current_stock,
                "current_price": float(r.current_price) if r.current_price else None,
                "total_score": r.total_score,
                "grade": r.grade,
                "similarity": round(float(r.sim), 3),
            }
            for r in rows
        ],
        "total": len(rows),
    }

