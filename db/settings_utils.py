"""
Default application settings with types and descriptions.
Ensures all 20 settings exist in the database on startup.
"""
from sqlalchemy.orm import Session
from db.models import ApplicationSetting


DEFAULT_SETTINGS = [
    ("VAT_RATE", "19.0", "decimal", "Romanian VAT percentage for margin calculation"),
    ("USD_TO_RON_CONVERSION_RATE", "4.60", "decimal", "USD to RON conversion rate for landed cost"),
    ("SALES_AVG_PERIOD_DAYS", "30", "int", "Number of days for sales averaging window"),
    ("DECIMAL_HIGH_MARGIN_THRESHOLD", "50.0", "decimal", "Margin >= this is 'Healthy'"),
    ("DECIMAL_AVERAGE_MARGIN_THRESHOLD_LOWER", "30.0", "decimal", "Margin >= this is 'Average', below is 'Low'"),
    ("SALES_RANKING_HIGH_MIN_AVG_UNITS", "3.0", "decimal", "High rank: minimum avg daily units"),
    ("SALES_RANKING_HIGH_MIN_DAYS_PERCENT", "75.0", "decimal", "High rank: minimum % of days with sales"),
    ("SALES_RANKING_GOOD_MIN_AVG_UNITS", "1.0", "decimal", "Good rank: minimum avg daily units"),
    ("SALES_RANKING_GOOD_MIN_DAYS_PERCENT", "50.0", "decimal", "Good rank: minimum % of days with sales"),
    ("SALES_RANKING_SLOW_MIN_AVG_UNITS", "0.2", "decimal", "Slow rank: minimum avg daily units"),
    ("SALES_RANKING_SLOW_MIN_DAYS_PERCENT", "20.0", "decimal", "Slow rank: minimum % of days with sales"),
    ("SALES_SANITY_CHECK_THRESHOLD", "10000", "int", "Stock above this = placeholder, ignore in sales calc"),
    ("SALES_OUTLIER_MULTIPLIER", "10", "int", "Cap daily sales at median * this multiplier"),
    ("DEFAULT_PAGE_SIZE", "50", "int", "Default pagination page size"),
    ("SEASONALITY_DEMAND_THRESHOLD", "50", "int", "Monthly index >= this = 'good demand' month"),
    ("STALE_PRODUCT_DAYS_THRESHOLD", "14", "int", "Days without stock update to mark product as stale"),
    ("DECIMAL_LOW_MARGIN_THRESHOLD", "10.0", "decimal", "Margin below this = critical warning"),
    ("MAX_EXPORT_ROWS", "10000", "int", "Maximum rows for Excel export"),
    ("CACHE_TTL_SIDEBAR", "60", "int", "Sidebar cache TTL in seconds"),
    ("CACHE_TTL_DASHBOARD", "30", "int", "Dashboard cache TTL in seconds"),
]


def ensure_settings(db: Session):
    """Insert any missing default settings into the database."""
    existing_keys = {s.setting_key for s in db.query(ApplicationSetting.setting_key).all()}

    new_settings = []
    for key, value, vtype, desc in DEFAULT_SETTINGS:
        if key not in existing_keys:
            new_settings.append(ApplicationSetting(
                setting_key=key,
                setting_value=value,
                value_type=vtype,
                description=desc,
            ))

    if new_settings:
        db.add_all(new_settings)
        db.commit()


def get_setting(db: Session, key: str, default=None):
    """Get a setting value, cast to its declared type."""
    setting = db.query(ApplicationSetting).filter(
        ApplicationSetting.setting_key == key
    ).first()

    if not setting:
        return default

    raw = setting.setting_value
    vtype = (setting.value_type or "").lower().strip()

    if vtype in ("int", "integer"):
        try:
            return int(float(raw))  # int(float()) handles "50.0" -> 50
        except (ValueError, TypeError):
            return default
    elif vtype in ("decimal", "float", "number"):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return default
    elif vtype == "bool":
        return raw.lower() in ("true", "1", "yes")
    return raw
