"""
Product Scorer — Computes a composite quality score (0–100) for each product
based on 5 dimensions: Sales Velocity, Restock Pattern, Price Stability,
Data Quality, and Market Position.

All heavy computation is done via SQL (materialized view) for performance
across 4M+ products. This module handles MV creation, refresh, and
single-product scoring for on-demand use.
"""
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ─── MV Creation SQL ───────────────────────────────────────────────────────────

CREATE_MV_SQL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_scores AS
WITH
-- 1) Daily stock: last reading per product per day (already in mv_stock_last_per_day)
daily_stock AS (
    SELECT product_id, s_day, quantity
    FROM mv_stock_last_per_day
    WHERE s_day >= CURRENT_DATE - INTERVAL '90 days'
),

-- 2) Restock detection: stock increases after decreases
stock_changes AS (
    SELECT
        product_id,
        s_day,
        quantity,
        LAG(quantity) OVER (PARTITION BY product_id ORDER BY s_day) AS prev_qty,
        quantity - LAG(quantity) OVER (PARTITION BY product_id ORDER BY s_day) AS diff
    FROM daily_stock
),
restocks AS (
    SELECT
        product_id,
        COUNT(*) FILTER (WHERE diff > 0 AND (prev_qty = 0 OR diff >= GREATEST(10, prev_qty * 0.2))) AS restock_count_90d,
        COUNT(*) FILTER (WHERE quantity = 0) AS zero_stock_days,
        COUNT(*) AS tracked_days,
        -- Oscillation detection: count direction reversals
        COUNT(*) FILTER (WHERE diff > 0) AS increase_days,
        COUNT(*) FILTER (WHERE diff < 0) AS decrease_days
    FROM stock_changes
    WHERE prev_qty IS NOT NULL
    GROUP BY product_id
),

-- 3) Sales velocity from mv_product_daily_sales
sales_stats AS (
    SELECT
        product_id,
        -- 30-day averages
        AVG(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS avg_sold_30d,
        STDDEV(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS stddev_sold_30d,
        -- 7-day average
        AVG(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '7 days') AS avg_sold_7d,
        -- Total entries
        COUNT(*) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS sales_days_30d
    FROM mv_product_daily_sales
    WHERE s_day >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY product_id
),

-- 4) Price trends from price_history (last 30 days)
price_bounds AS (
    SELECT
        product_id,
        MIN(value) AS min_price_30d,
        MAX(value) AS max_price_30d,
        (ARRAY_AGG(value ORDER BY timestamp ASC))[1] AS earliest_price,
        (ARRAY_AGG(value ORDER BY timestamp DESC))[1] AS latest_price,
        COUNT(DISTINCT DATE(timestamp)) AS price_days
    FROM price_history
    WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
      AND value > 0
    GROUP BY product_id
),

-- 5) Data quality: stock entry counts and distinct days
data_quality AS (
    SELECT
        product_id,
        COUNT(*) AS total_stock_entries,
        COUNT(DISTINCT s_day) AS distinct_stock_days,
        MAX(quantity) AS max_stock_ever
    FROM mv_stock_last_per_day
    GROUP BY product_id
),

-- 6) Latest info from existing MVs
latest AS (
    SELECT
        ls.product_id,
        ls.quantity AS current_stock,
        ls.timestamp AS last_stock_date,
        lp.price AS current_price
    FROM mv_latest_stock ls
    LEFT JOIN mv_latest_price lp ON lp.product_id = ls.product_id
),

-- 7) Product metadata
prod AS (
    SELECT id, name, image, vendor, parser_id
    FROM products
),

-- ═══════════════════════════════════════════════════════════════════════
-- SCORING FORMULAS
-- ═══════════════════════════════════════════════════════════════════════
scored AS (
    SELECT
        p.id AS product_id,

        -- ─── RAW SIGNALS ───
        COALESCE(ss.avg_sold_30d, 0) AS avg_sold_30d,
        COALESCE(ss.avg_sold_7d, 0) AS avg_sold_7d,
        COALESCE(ss.stddev_sold_30d, 0) AS stddev_sold_30d,
        COALESCE(ss.sales_days_30d, 0) AS sales_days_30d,
        COALESCE(r.restock_count_90d, 0) AS restock_count_90d,
        COALESCE(r.zero_stock_days, 0) AS zero_stock_days,
        COALESCE(r.tracked_days, 0) AS tracked_days_90d,
        COALESCE(r.increase_days, 0) AS increase_days,
        COALESCE(r.decrease_days, 0) AS decrease_days,
        COALESCE(dq.total_stock_entries, 0) AS total_stock_entries,
        COALESCE(dq.distinct_stock_days, 0) AS distinct_stock_days,
        COALESCE(dq.max_stock_ever, 0) AS max_stock_ever,
        COALESCE(pb.earliest_price, 0) AS earliest_price,
        COALESCE(pb.latest_price, 0) AS latest_price,
        lt.current_stock,
        lt.current_price,
        lt.last_stock_date,

        -- ─── DIMENSION 1: Sales Velocity (0–30) ───
        LEAST(30, GREATEST(0,
            -- Base: sales volume tier
            CASE
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 5 THEN 15
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 2 THEN 10
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 0.5 THEN 5
                ELSE 0
            END
            -- Consistency bonus: low CoV
            + CASE
                WHEN COALESCE(ss.avg_sold_30d, 0) > 0
                     AND COALESCE(ss.stddev_sold_30d, 0) / GREATEST(ss.avg_sold_30d, 0.01) < 0.5
                THEN 5
                ELSE 0
            END
            -- Trend bonus/penalty: 7d vs 30d
            + CASE
                WHEN COALESCE(ss.avg_sold_7d, 0) > COALESCE(ss.avg_sold_30d, 0) * 1.2 THEN 5
                WHEN COALESCE(ss.avg_sold_7d, 0) < COALESCE(ss.avg_sold_30d, 0) * 0.5 THEN -5
                ELSE 0
            END
        )) AS sales_velocity_score,

        -- ─── DIMENSION 2: Restock Pattern (0–25) ───
        LEAST(25, GREATEST(0,
            CASE
                WHEN COALESCE(r.restock_count_90d, 0) >= 3 THEN 15
                WHEN COALESCE(r.restock_count_90d, 0) = 2 THEN 10
                WHEN COALESCE(r.restock_count_90d, 0) = 1 THEN 5
                ELSE 0
            END
            -- Never hit zero = well managed
            + CASE
                WHEN COALESCE(r.restock_count_90d, 0) > 0
                     AND COALESCE(r.zero_stock_days, 0) = 0
                THEN 5
                ELSE 0
            END
            -- Currently out of stock after restocking = demand signal
            + CASE
                WHEN COALESCE(r.restock_count_90d, 0) > 0
                     AND COALESCE(lt.current_stock, 0) = 0
                THEN 5
                ELSE 0
            END
        )) AS restock_score,

        -- ─── DIMENSION 3: Price Stability (0–20) ───
        LEAST(20, GREATEST(0,
            CASE
                WHEN pb.earliest_price IS NULL OR pb.earliest_price = 0 THEN 5
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= 0 THEN 15
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= -0.10 THEN 10
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= -0.25 THEN 5
                ELSE 0
            END
            -- Price went UP while selling = premium signal
            + CASE
                WHEN pb.earliest_price IS NOT NULL AND pb.earliest_price > 0
                     AND pb.latest_price > pb.earliest_price
                     AND COALESCE(ss.avg_sold_30d, 0) >= 1
                THEN 5
                ELSE 0
            END
        )) AS price_stability_score,

        -- ─── DIMENSION 4: Data Quality (0–15) ───
        LEAST(15, GREATEST(-10,
            CASE
                WHEN COALESCE(dq.total_stock_entries, 0) >= 30
                     AND COALESCE(dq.distinct_stock_days, 0) >= 15
                THEN 10
                WHEN COALESCE(dq.total_stock_entries, 0) >= 10
                     AND COALESCE(dq.distinct_stock_days, 0) >= 7
                THEN 5
                ELSE 0
            END
            -- Oscillation penalty
            + CASE
                WHEN COALESCE(r.tracked_days, 0) > 5
                     AND (COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0)) > 0
                     AND LEAST(COALESCE(r.increase_days, 0), COALESCE(r.decrease_days, 0))::float
                         / GREATEST(COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0), 1) > 0.4
                     AND COALESCE(dq.max_stock_ever, 0) > 0
                     AND COALESCE(dq.max_stock_ever, 0)::float / GREATEST(
                         NULLIF((SELECT MIN(ds2.quantity) FROM mv_stock_last_per_day ds2
                                 WHERE ds2.product_id = p.id AND ds2.quantity > 0), 0), 1
                     ) > 5
                THEN -10
                ELSE 5
            END
        )) AS data_quality_score,

        -- ─── DIMENSION 5: Market Position (0–10) ───
        LEAST(10, GREATEST(0,
            CASE
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '3 days' THEN 5
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '7 days' THEN 3
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1
                ELSE 0
            END
            + CASE WHEN p.image IS NOT NULL AND p.image != '' THEN 2 ELSE 0 END
            + CASE WHEN p.vendor IS NOT NULL AND p.vendor != '' THEN 2 ELSE 0 END
            + CASE
                WHEN COALESCE(lt.current_price, 0) BETWEEN 5 AND 500 THEN 1
                ELSE 0
            END
        )) AS market_position_score,

        -- ─── FLAGS ───
        -- Oscillating (multi-listing suspect) — simplified without correlated subquery
        (COALESCE(r.tracked_days, 0) > 5
         AND (COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0)) > 0
         AND LEAST(COALESCE(r.increase_days, 0), COALESCE(r.decrease_days, 0))::float
             / GREATEST(COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0), 1) > 0.4
        ) AS is_oscillating,

        -- Liquidating: price dropped >15% AND no restocks
        (pb.earliest_price IS NOT NULL AND pb.earliest_price > 0
         AND (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) < -0.15
         AND COALESCE(r.restock_count_90d, 0) = 0
        ) AS is_liquidating,

        -- Active restock cycle
        (COALESCE(r.restock_count_90d, 0) >= 2) AS is_restocking,

        -- Unrealistic stock
        (COALESCE(dq.max_stock_ever, 0) >= 1000000) AS is_unrealistic_stock,

        -- New listing (first tracked < 14 days ago)
        (COALESCE(dq.distinct_stock_days, 0) <= 14
         AND lt.last_stock_date >= CURRENT_DATE - INTERVAL '14 days'
        ) AS is_new_listing

    FROM prod p
    LEFT JOIN sales_stats ss ON ss.product_id = p.id
    LEFT JOIN restocks r ON r.product_id = p.id
    LEFT JOIN price_bounds pb ON pb.product_id = p.id
    LEFT JOIN data_quality dq ON dq.product_id = p.id
    LEFT JOIN latest lt ON lt.product_id = p.id
)

SELECT
    product_id,
    avg_sold_30d,
    avg_sold_7d,
    restock_count_90d,
    earliest_price,
    latest_price,
    total_stock_entries,
    distinct_stock_days,
    max_stock_ever,
    current_stock,
    current_price,
    last_stock_date,

    sales_velocity_score,
    restock_score,
    price_stability_score,
    data_quality_score,
    market_position_score,

    -- Composite score
    LEAST(100, GREATEST(0,
        sales_velocity_score + restock_score + price_stability_score
        + data_quality_score + market_position_score
    )) AS total_score,

    -- Grade
    CASE
        WHEN sales_velocity_score + restock_score + price_stability_score
             + data_quality_score + market_position_score >= 75 THEN 'A'
        WHEN sales_velocity_score + restock_score + price_stability_score
             + data_quality_score + market_position_score >= 55 THEN 'B'
        WHEN sales_velocity_score + restock_score + price_stability_score
             + data_quality_score + market_position_score >= 35 THEN 'C'
        WHEN sales_velocity_score + restock_score + price_stability_score
             + data_quality_score + market_position_score >= 15 THEN 'D'
        ELSE 'F'
    END AS grade,

    -- Flags
    is_oscillating,
    is_liquidating,
    is_restocking,
    is_unrealistic_stock,
    is_new_listing

FROM scored;
"""

# Simplified version without correlated subquery in data_quality_score
# V2: Improved oscillation detection, high-stock penalties, restock sanity checks
CREATE_MV_SQL_SIMPLE = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_scores AS
WITH
daily_stock AS (
    SELECT product_id, s_day, close_stock
    FROM mv_stock_last_per_day
    WHERE s_day >= CURRENT_DATE - INTERVAL '90 days'
),
stock_changes AS (
    SELECT
        product_id, s_day, close_stock,
        LAG(close_stock) OVER (PARTITION BY product_id ORDER BY s_day) AS prev_qty,
        close_stock - LAG(close_stock) OVER (PARTITION BY product_id ORDER BY s_day) AS diff
    FROM daily_stock
),
restocks AS (
    SELECT
        product_id,
        COUNT(*) FILTER (WHERE diff > 0 AND (prev_qty = 0 OR diff >= GREATEST(10, prev_qty * 0.2))) AS restock_count_90d,
        COUNT(*) FILTER (WHERE close_stock = 0) AS zero_stock_days,
        COUNT(*) AS tracked_days,
        COUNT(*) FILTER (WHERE diff > 0) AS increase_days,
        COUNT(*) FILTER (WHERE diff < 0) AS decrease_days
    FROM stock_changes
    WHERE prev_qty IS NOT NULL
    GROUP BY product_id
),
sales_stats AS (
    SELECT
        product_id,
        AVG(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS avg_sold_30d,
        STDDEV(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS stddev_sold_30d,
        AVG(units_sold) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '7 days') AS avg_sold_7d,
        COUNT(*) FILTER (WHERE s_day >= CURRENT_DATE - INTERVAL '30 days') AS sales_days_30d
    FROM mv_product_daily_sales
    WHERE s_day >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY product_id
),
price_bounds AS (
    SELECT
        product_id,
        MIN(value) AS min_price_30d,
        MAX(value) AS max_price_30d,
        (ARRAY_AGG(value ORDER BY timestamp ASC))[1] AS earliest_price,
        (ARRAY_AGG(value ORDER BY timestamp DESC))[1] AS latest_price,
        COUNT(DISTINCT DATE(timestamp)) AS price_days
    FROM price_history
    WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days' AND value > 0
    GROUP BY product_id
),
data_quality AS (
    SELECT
        product_id,
        COUNT(*) AS total_stock_entries,
        COUNT(DISTINCT s_day) AS distinct_stock_days,
        MAX(close_stock) AS max_stock_ever
    FROM mv_stock_last_per_day
    GROUP BY product_id
),
latest AS (
    SELECT ls.product_id, ls.quantity AS current_stock, ls.timestamp AS last_stock_date,
           lp.price AS current_price
    FROM mv_latest_stock ls
    LEFT JOIN mv_latest_price lp ON lp.product_id = ls.product_id
),
scored AS (
    SELECT
        p.id AS product_id,
        COALESCE(ss.avg_sold_30d, 0) AS avg_sold_30d,
        COALESCE(ss.avg_sold_7d, 0) AS avg_sold_7d,
        COALESCE(r.restock_count_90d, 0) AS restock_count_90d,
        COALESCE(pb.earliest_price, 0) AS earliest_price,
        COALESCE(pb.latest_price, 0) AS latest_price,
        COALESCE(dq.total_stock_entries, 0) AS total_stock_entries,
        COALESCE(dq.distinct_stock_days, 0) AS distinct_stock_days,
        COALESCE(dq.max_stock_ever, 0) AS max_stock_ever,
        lt.current_stock,
        lt.current_price,
        lt.last_stock_date,

        -- ═══ DIMENSION 1: Sales Velocity (0-30) ═══
        -- High-stock products get penalized: if max_stock >= 100K and sales are low,
        -- the "sales" are likely noise from stock cycling, not real demand.
        LEAST(30, GREATEST(0,
            CASE
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 5 THEN 15
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 2 THEN 10
                WHEN COALESCE(ss.avg_sold_30d, 0) >= 0.5 THEN 5
                ELSE 0
            END
            + CASE WHEN COALESCE(ss.avg_sold_30d, 0) > 0 AND COALESCE(ss.stddev_sold_30d, 0) / GREATEST(ss.avg_sold_30d, 0.01) < 0.5 THEN 5 ELSE 0 END
            + CASE WHEN COALESCE(ss.avg_sold_7d, 0) > COALESCE(ss.avg_sold_30d, 0) * 1.2 THEN 5
                   WHEN COALESCE(ss.avg_sold_7d, 0) < COALESCE(ss.avg_sold_30d, 0) * 0.5 THEN -5
                   ELSE 0 END
            -- HIGH-STOCK PENALTY: products with massive stock and moderate sales
            -- are likely dropship/multi-listing with fake stock numbers
            + CASE
                WHEN COALESCE(dq.max_stock_ever, 0) >= 100000
                     AND COALESCE(ss.avg_sold_30d, 0) < 10 THEN -15
                WHEN COALESCE(dq.max_stock_ever, 0) >= 50000
                     AND COALESCE(ss.avg_sold_30d, 0) < 5 THEN -10
                ELSE 0
              END
        )) AS sales_velocity_score,

        -- ═══ DIMENSION 2: Restock Pattern (0-25) ═══
        -- Capped for high-stock products: frequent "restocks" with massive stock
        -- are stock cycling, not genuine inventory replenishment.
        LEAST(25, GREATEST(0,
            CASE
                -- High-stock rapid cycling: cap at 0 (these aren't real restocks)
                WHEN COALESCE(dq.max_stock_ever, 0) >= 50000
                     AND COALESCE(r.restock_count_90d, 0) >= 6 THEN 0
                -- Normal restock tiers
                WHEN COALESCE(r.restock_count_90d, 0) >= 3 THEN 15
                WHEN COALESCE(r.restock_count_90d, 0) = 2 THEN 10
                WHEN COALESCE(r.restock_count_90d, 0) = 1 THEN 5
                ELSE 0
            END
            + CASE
                -- No bonus for high-stock products (stock cycling)
                WHEN COALESCE(dq.max_stock_ever, 0) >= 50000 THEN 0
                WHEN COALESCE(r.restock_count_90d, 0) > 0 AND COALESCE(r.zero_stock_days, 0) = 0 THEN 5
                ELSE 0
              END
            + CASE
                WHEN COALESCE(dq.max_stock_ever, 0) >= 50000 THEN 0
                WHEN COALESCE(r.restock_count_90d, 0) > 0 AND COALESCE(lt.current_stock, 0) = 0 THEN 5
                ELSE 0
              END
        )) AS restock_score,

        -- ═══ DIMENSION 3: Price Stability (0-20) ═══
        -- Added: price volatility penalty when min/max spread is too wide
        LEAST(20, GREATEST(0,
            CASE
                WHEN pb.earliest_price IS NULL OR pb.earliest_price = 0 THEN 5
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= 0 THEN 15
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= -0.10 THEN 10
                WHEN (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) >= -0.25 THEN 5
                ELSE 0
            END
            + CASE WHEN pb.earliest_price > 0 AND pb.latest_price > pb.earliest_price AND COALESCE(ss.avg_sold_30d, 0) >= 1 THEN 5 ELSE 0 END
            -- PRICE VOLATILITY PENALTY: if min/max price spread > 50%, something is wrong
            + CASE
                WHEN pb.min_price_30d IS NOT NULL AND pb.min_price_30d > 0
                     AND (pb.max_price_30d - pb.min_price_30d) / pb.min_price_30d > 0.5
                THEN -10
                ELSE 0
              END
        )) AS price_stability_score,

        -- ═══ DIMENSION 4: Data Quality (0-15) ═══
        -- Improved oscillation detection: also catches high-stock rapid cycling
        LEAST(15, GREATEST(-10,
            CASE
                WHEN COALESCE(dq.total_stock_entries, 0) >= 30 AND COALESCE(dq.distinct_stock_days, 0) >= 15 THEN 10
                WHEN COALESCE(dq.total_stock_entries, 0) >= 10 AND COALESCE(dq.distinct_stock_days, 0) >= 7 THEN 5
                ELSE 0
            END
            + CASE
                -- Classic oscillation: balanced increase/decrease days
                WHEN COALESCE(r.tracked_days, 0) > 5
                     AND CAST(LEAST(COALESCE(r.increase_days, 0), COALESCE(r.decrease_days, 0)) AS float)
                         / GREATEST(COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0), 1) > 0.4
                THEN -10
                -- HIGH-STOCK CYCLING: many "restocks" + huge stock = fake cycling
                WHEN COALESCE(dq.max_stock_ever, 0) >= 50000
                     AND COALESCE(r.restock_count_90d, 0) >= 6
                THEN -10
                -- UNREALISTIC STOCK: max_stock >= 100K is suspicious
                WHEN COALESCE(dq.max_stock_ever, 0) >= 100000
                THEN -5
                ELSE 5
              END
        )) AS data_quality_score,

        -- ═══ DIMENSION 5: Market Position (0-10) ═══
        LEAST(10, GREATEST(0,
            CASE
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '3 days' THEN 5
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '7 days' THEN 3
                WHEN lt.last_stock_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1
                ELSE 0
            END
            + CASE WHEN p.image IS NOT NULL AND p.image != '' THEN 2 ELSE 0 END
            + CASE WHEN p.vendor IS NOT NULL AND p.vendor != '' THEN 2 ELSE 0 END
            + CASE WHEN COALESCE(lt.current_price, 0) BETWEEN 5 AND 500 THEN 1 ELSE 0 END
        )) AS market_position_score,

        -- ═══ FLAGS ═══
        -- Oscillating: classic balanced oscillation OR high-stock rapid cycling
        (COALESCE(r.tracked_days, 0) > 5
         AND (
           -- Classic: balanced increase/decrease
           CAST(LEAST(COALESCE(r.increase_days, 0), COALESCE(r.decrease_days, 0)) AS float)
               / GREATEST(COALESCE(r.increase_days, 0) + COALESCE(r.decrease_days, 0), 1) > 0.4
           -- OR high-stock rapid cycling
           OR (COALESCE(dq.max_stock_ever, 0) >= 50000 AND COALESCE(r.restock_count_90d, 0) >= 6)
         )
        ) AS is_oscillating,

        -- Liquidating
        (pb.earliest_price IS NOT NULL AND pb.earliest_price > 0
         AND (pb.latest_price - pb.earliest_price) / GREATEST(pb.earliest_price, 0.01) < -0.15
         AND COALESCE(r.restock_count_90d, 0) = 0
        ) AS is_liquidating,

        -- Active restock cycle (only for reasonable stock levels)
        (COALESCE(r.restock_count_90d, 0) >= 2
         AND COALESCE(dq.max_stock_ever, 0) < 50000
        ) AS is_restocking,

        -- Unrealistic stock (lowered from 1M to 100K)
        (COALESCE(dq.max_stock_ever, 0) >= 100000) AS is_unrealistic_stock,

        -- High stock (new flag: 50K-100K range, suspicious but not necessarily fake)
        (COALESCE(dq.max_stock_ever, 0) >= 50000) AS is_high_stock,

        -- New listing
        (COALESCE(dq.distinct_stock_days, 0) <= 14
         AND lt.last_stock_date >= CURRENT_DATE - INTERVAL '14 days'
        ) AS is_new_listing

    FROM products p
    LEFT JOIN sales_stats ss ON ss.product_id = p.id
    LEFT JOIN restocks r ON r.product_id = p.id
    LEFT JOIN price_bounds pb ON pb.product_id = p.id
    LEFT JOIN data_quality dq ON dq.product_id = p.id
    LEFT JOIN latest lt ON lt.product_id = p.id
)

SELECT
    product_id,
    avg_sold_30d, avg_sold_7d, restock_count_90d,
    earliest_price, latest_price,
    total_stock_entries, distinct_stock_days, max_stock_ever,
    current_stock, current_price, last_stock_date,
    sales_velocity_score, restock_score, price_stability_score,
    data_quality_score, market_position_score,
    LEAST(100, GREATEST(0,
        sales_velocity_score + restock_score + price_stability_score
        + data_quality_score + market_position_score
    )) AS total_score,
    CASE
        WHEN sales_velocity_score + restock_score + price_stability_score + data_quality_score + market_position_score >= 75 THEN 'A'
        WHEN sales_velocity_score + restock_score + price_stability_score + data_quality_score + market_position_score >= 55 THEN 'B'
        WHEN sales_velocity_score + restock_score + price_stability_score + data_quality_score + market_position_score >= 35 THEN 'C'
        WHEN sales_velocity_score + restock_score + price_stability_score + data_quality_score + market_position_score >= 15 THEN 'D'
        ELSE 'F'
    END AS grade,
    is_oscillating, is_liquidating, is_restocking, is_unrealistic_stock, is_high_stock, is_new_listing
FROM scored;
"""

CREATE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_product_scores_pid ON mv_product_scores (product_id);
CREATE INDEX IF NOT EXISTS idx_mv_product_scores_total ON mv_product_scores (total_score DESC);
CREATE INDEX IF NOT EXISTS idx_mv_product_scores_grade ON mv_product_scores (grade);
"""


def create_scoring_mv(db: Session) -> bool:
    """Create the mv_product_scores materialized view if it doesn't exist."""
    try:
        # Check if it exists
        exists = db.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_product_scores')")
        ).scalar()

        if exists:
            logger.info("mv_product_scores already exists")
            return True

        logger.info("Creating mv_product_scores materialized view (this may take several minutes for large datasets)...")
        # Use raw psycopg2 cursor to completely bypass SQLAlchemy's text()
        # parameter parsing which misinterprets PostgreSQL :: casts and CTE names
        raw_conn = db.connection().connection
        cursor = raw_conn.cursor()
        cursor.execute(CREATE_MV_SQL_SIMPLE)
        raw_conn.commit()
        cursor.close()
        logger.info("mv_product_scores created successfully")

        # Create indexes via raw cursor too
        for idx_sql in CREATE_INDEX_SQL.strip().split(";"):
            idx_sql = idx_sql.strip()
            if idx_sql:
                try:
                    cursor = raw_conn.cursor()
                    cursor.execute(idx_sql)
                    raw_conn.commit()
                    cursor.close()
                except Exception:
                    raw_conn.rollback()

        logger.info("Indexes created on mv_product_scores")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create mv_product_scores: {e}")
        return False


def refresh_scoring_mv(db: Session) -> bool:
    """Refresh the mv_product_scores materialized view."""
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_product_scores"))
        db.commit()
        logger.info("Refreshed mv_product_scores (concurrent)")
        return True
    except Exception:
        db.rollback()
        try:
            db.execute(text("REFRESH MATERIALIZED VIEW mv_product_scores"))
            db.commit()
            logger.info("Refreshed mv_product_scores (blocking)")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to refresh mv_product_scores: {e}")
            return False


def get_product_score(db: Session, product_id: int) -> dict | None:
    """Get the score breakdown for a single product."""
    row = db.execute(text("""
        SELECT * FROM mv_product_scores WHERE product_id = :pid
    """), {"pid": product_id}).fetchone()

    if not row:
        return None

    return {
        "product_id": row.product_id,
        "total_score": row.total_score,
        "grade": row.grade,
        "dimensions": {
            "sales_velocity": {"score": row.sales_velocity_score, "max": 30,
                               "avg_sold_30d": round(float(row.avg_sold_30d or 0), 2),
                               "avg_sold_7d": round(float(row.avg_sold_7d or 0), 2)},
            "restock_pattern": {"score": row.restock_score, "max": 25,
                                "restock_count_90d": row.restock_count_90d},
            "price_stability": {"score": row.price_stability_score, "max": 20,
                                "earliest_price": round(float(row.earliest_price or 0), 2),
                                "latest_price": round(float(row.latest_price or 0), 2)},
            "data_quality": {"score": row.data_quality_score, "max": 15,
                             "total_entries": row.total_stock_entries,
                             "distinct_days": row.distinct_stock_days},
            "market_position": {"score": row.market_position_score, "max": 10},
        },
        "flags": {
            "is_oscillating": bool(row.is_oscillating),
            "is_liquidating": bool(row.is_liquidating),
            "is_restocking": bool(row.is_restocking),
            "is_unrealistic_stock": bool(row.is_unrealistic_stock),
            "is_new_listing": bool(row.is_new_listing),
        },
    }


def get_score_distribution(db: Session) -> dict:
    """Get grade distribution counts."""
    rows = db.execute(text("""
        SELECT grade, COUNT(*) as cnt
        FROM mv_product_scores
        GROUP BY grade
        ORDER BY grade
    """)).fetchall()

    return {row.grade: row.cnt for row in rows}
