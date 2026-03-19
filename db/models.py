"""
SQLAlchemy ORM models mapping to the existing PostgreSQL schema.
10 models + 1 M2M association table.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey,
    Table, Numeric, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db.session import Base


# ─── M2M Association ────────────────────────────────────────────────
product_assigned_categories = Table(
    "product_assigned_categories",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("product_categories.id"), primary_key=True),
)


# ─── User ───────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)


# ─── Parser ─────────────────────────────────────────────────────────
class Parser(Base):
    __tablename__ = "parsers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String)

    products = relationship("Product", back_populates="parser")
    run_logs = relationship("ParserRunLog", back_populates="parser")


# ─── Product ────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(String, unique=True)
    name = Column(String, nullable=False)
    url = Column(String)
    image = Column(String)
    slug = Column(String)
    vendor = Column(String)
    stock_policy = Column(String)
    parser_id = Column(Integer, ForeignKey("parsers.id"))
    parent_id = Column(String)
    shortlisted = Column(Boolean, default=False)
    pipeline_status = Column(String, default=None)
    sales_ranking = Column(String)
    group_id = Column(Integer, ForeignKey("product_groups.id"))

    parser = relationship("Parser", back_populates="products")
    group = relationship("ProductGroup", back_populates="products")
    pipeline_detail = relationship("ProductPipelineDetail", uselist=False, back_populates="product")
    stock_history = relationship("StockHistory", back_populates="product", lazy="dynamic")
    price_history = relationship("PriceHistory", back_populates="product", lazy="dynamic")
    categories = relationship("ProductCategory", secondary=product_assigned_categories, back_populates="products")


# ─── ProductPipelineDetail ──────────────────────────────────────────
class ProductPipelineDetail(Base):
    __tablename__ = "product_pipeline_details"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    title = Column(String)
    variants = Column(JSONB, default=list)
    sku = Column(String)
    barcode = Column(String)
    specs = Column(Text)
    retail_price = Column(Numeric(10, 2))
    factory_link_url = Column(Text)
    cogs_usd = Column(Numeric(10, 2))
    transport_usd = Column(Numeric(10, 2))
    dimension_width_cm = Column(Numeric(10, 2))
    dimension_length_cm = Column(Numeric(10, 2))
    dimension_height_cm = Column(Numeric(10, 2))
    cubic_meters = Column(Numeric(10, 4))
    customs_rate_percentage = Column(Numeric(5, 2))
    hs_code = Column(String)
    top_keywords = Column(Text)
    keyword_difficulty = Column(String)
    main_competitors = Column(Text)
    market_research_insights = Column(Text)
    suggested_quantity_min = Column(Integer)
    suggested_quantity_max = Column(Integer)
    first_order_cost_estimate = Column(Numeric(10, 2))
    launch_notes = Column(Text)
    last_saved_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    monthly_sales_index = Column(JSONB)

    product = relationship("Product", back_populates="pipeline_detail")


# ─── StockHistory ───────────────────────────────────────────────────
class StockHistory(Base):
    __tablename__ = "stock_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())

    product = relationship("Product", back_populates="stock_history")


# ─── PriceHistory ───────────────────────────────────────────────────
class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())

    product = relationship("Product", back_populates="price_history")


# ─── ProductCategory ────────────────────────────────────────────────
class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String)

    products = relationship("Product", secondary=product_assigned_categories, back_populates="categories")


# ─── ParserDefinedCategory ──────────────────────────────────────────
class ParserDefinedCategory(Base):
    __tablename__ = "parser_defined_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)


# ─── ProductGroup ───────────────────────────────────────────────────
class ProductGroup(Base):
    __tablename__ = "product_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    products = relationship("Product", back_populates="group")


# ─── ParserRunLog ───────────────────────────────────────────────────
class ParserRunLog(Base):
    __tablename__ = "parser_run_logs"

    id = Column(Integer, primary_key=True, index=True)
    parser_id = Column(Integer, ForeignKey("parsers.id"), nullable=False, index=True)
    run_date = Column(DateTime)
    products_found = Column(Integer)
    products_parsed_success = Column(Integer)
    products_parsed_failed = Column(Integer)
    stock_entries_saved = Column(Integer)
    price_entries_saved = Column(Integer)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_seconds = Column(Float)
    status = Column(String)
    error_message = Column(Text)
    speed_products_per_sec = Column(Float)

    parser = relationship("Parser", back_populates="run_logs")


# ─── ApplicationSetting ────────────────────────────────────────────
class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String, unique=True, nullable=False)
    setting_value = Column(String, nullable=False)
    value_type = Column(String, default="string")
    description = Column(Text)
