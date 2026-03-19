"""
Opportunities API — Products shortlisted or at 'New' pipeline status.
Uses product_metrics_view MV with columns: id (not product_id), name, etc.
"""
import os
import re
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import io

from db.session import get_db
from db.models import Product, ProductPipelineDetail
from api.routes.auth import get_current_user
from db.settings_utils import get_setting

router = APIRouter()


@router.get("/api/opportunities")
async def get_opportunities(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Products that are shortlisted OR at 'New' pipeline status."""
    rows = db.execute(text("""
        SELECT
            p.id, p.name, p.image, p.url, p.vendor, p.shortlisted,
            p.pipeline_status,
            par.name as parser_name,
            pmv.stock, pmv.avg_1d, pmv.avg_7d, pmv.avg_30d, pmv.price,
            ppd.monthly_sales_index
        FROM product_metrics_view pmv
        JOIN products p ON p.id = pmv.id
        LEFT JOIN parsers par ON par.id = p.parser_id
        LEFT JOIN product_pipeline_details ppd ON ppd.product_id = p.id
        WHERE (p.shortlisted = true OR p.pipeline_status = 'New')
        AND pmv.is_stale = false
        ORDER BY pmv.avg_30d DESC
    """)).fetchall()

    products = [
        {
            "id": r.id, "name": r.name, "image": r.image, "url": r.url,
            "vendor": r.vendor, "shortlisted": r.shortlisted,
            "pipeline_status": r.pipeline_status,
            "parser_name": r.parser_name,
            "stock": r.stock, "price": float(r.price) if r.price else None,
            "avg_1d": float(r.avg_1d) if r.avg_1d else 0,
            "avg_7d": float(r.avg_7d) if r.avg_7d else 0,
            "avg_30d": float(r.avg_30d) if r.avg_30d else 0,
            "seasonality": r.monthly_sales_index if r.monthly_sales_index else None,
            "has_seasonality": r.monthly_sales_index is not None and len(r.monthly_sales_index) == 12 if r.monthly_sales_index else False,
        }
        for r in rows
    ]

    return {"products": products, "total": len(products)}


@router.post("/api/opportunities/generate-seasonality")
async def batch_generate_seasonality(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Batch: Generate seasonality for opportunity products without it."""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key not configured"}

    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)

    rows = db.execute(text("""
        SELECT p.id, p.name FROM products p
        LEFT JOIN product_pipeline_details ppd ON ppd.product_id = p.id
        WHERE (p.shortlisted = true OR p.pipeline_status = 'New')
        AND (ppd.monthly_sales_index IS NULL)
        LIMIT 50
    """)).fetchall()

    generated = 0
    for r in rows:
        try:
            prompt = f"""For the e-commerce product "{r.name}" in Romania, return monthly demand intensity as a JSON array of 12 integers (0-100), Jan-Dec. 100=peak. Return ONLY the array."""
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite", contents=prompt
            )
            match = re.search(r'\[[\d\s,]+\]', response.text)
            if match:
                data = json.loads(match.group())
                if len(data) == 12:
                    detail = db.query(ProductPipelineDetail).filter(
                        ProductPipelineDetail.product_id == r.id
                    ).first()
                    if not detail:
                        detail = ProductPipelineDetail(product_id=r.id)
                        db.add(detail)
                    detail.monthly_sales_index = data
                    db.commit()
                    generated += 1
        except Exception:
            continue

    return {"generated": generated, "total_candidates": len(rows)}


@router.get("/api/opportunities/export-excel")
async def export_opportunities_excel(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Export opportunity products to Excel."""
    import openpyxl

    rows = db.execute(text("""
        SELECT p.id, p.name, p.vendor, par.name as parser_name,
               pmv.stock, pmv.avg_30d, pmv.price,
               ppd.monthly_sales_index
        FROM product_metrics_view pmv
        JOIN products p ON p.id = pmv.id
        LEFT JOIN parsers par ON par.id = p.parser_id
        LEFT JOIN product_pipeline_details ppd ON ppd.product_id = p.id
        WHERE (p.shortlisted = true OR p.pipeline_status = 'New')
        ORDER BY pmv.avg_30d DESC
    """)).fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Opportunities"
    ws.append(["ID", "Name", "Vendor", "Store", "Stock", "Avg 30D", "Price", "Seasonality"])

    for r in rows:
        seasonality_str = ""
        if r.monthly_sales_index:
            seasonality_str = ",".join(str(x) for x in r.monthly_sales_index)
        ws.append([r.id, r.name, r.vendor, r.parser_name, r.stock,
                    float(r.avg_30d) if r.avg_30d else 0,
                    float(r.price) if r.price else None,
                    seasonality_str])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=opportunities.xlsx"}
    )
