-- Views the Streamlit app reads (Q1, Q2, Q6 plus KPI and per-seller helpers).
-- Revenue = item price (freight excluded). Months are purchase months.

-- Q1: On-time delivery % by customer state and month (delivered orders only).
CREATE OR REPLACE VIEW analytics.on_time_delivery AS
SELECT c.state                                   AS customer_state,
       make_date(d.year, d.month, 1)             AS month,
       count(*)                                  AS delivered_orders,
       sum(CASE WHEN f.is_late THEN 0 ELSE 1 END) AS on_time_orders,
       round(100.0 * sum(CASE WHEN f.is_late THEN 0 ELSE 1 END) / count(*), 1) AS on_time_pct
FROM dw.fact_order_fulfilment f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_date d     ON d.date_key = f.purchase_date_key
WHERE f.is_late IS NOT NULL
GROUP BY c.state, make_date(d.year, d.month, 1);

-- Monthly KPIs by customer state, as additive sums so the app can filter and re-aggregate.
CREATE OR REPLACE VIEW analytics.kpi_monthly AS
SELECT c.state                                         AS customer_state,
       make_date(d.year, d.month, 1)                   AS month,
       count(*)                                        AS orders,
       coalesce(sum(r.revenue), 0)                     AS revenue,
       count(*) FILTER (WHERE f.is_late IS NOT NULL)   AS delivered_orders,
       count(*) FILTER (WHERE NOT f.is_late)           AS on_time_orders,
       count(f.review_score)                           AS rated_orders,
       coalesce(sum(f.review_score), 0)                AS rating_sum
FROM dw.fact_order_fulfilment f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_date d     ON d.date_key = f.purchase_date_key
LEFT JOIN (SELECT order_id, sum(price) AS revenue FROM dw.fact_order_item GROUP BY order_id) r ON r.order_id = f.order_id
GROUP BY c.state, make_date(d.year, d.month, 1);

-- One row per seller and purchase month (orders counted once even with several items).
CREATE OR REPLACE VIEW analytics.seller_monthly AS
WITH seller_orders AS (
    SELECT s.seller_id, i.order_id, min(i.purchase_date_key) AS purchase_date_key, sum(i.price) AS revenue
    FROM dw.fact_order_item i
    JOIN dw.dim_seller s ON s.seller_key = i.seller_key
    GROUP BY s.seller_id, i.order_id
)
SELECT so.seller_id,
       make_date(d.year, d.month, 1)                  AS month,
       sum(so.revenue)                                AS revenue,
       count(*)                                       AS orders,
       count(*) FILTER (WHERE f.is_late IS NOT NULL)  AS delivered_orders,
       count(*) FILTER (WHERE f.is_late)              AS late_orders,
       round(avg(f.review_score), 2)                  AS avg_rating
FROM seller_orders so
JOIN dw.dim_date d              ON d.date_key = so.purchase_date_key
JOIN dw.fact_order_fulfilment f ON f.order_id = so.order_id
GROUP BY so.seller_id, make_date(d.year, d.month, 1);

-- Q2: Top 10 sellers per month by revenue, with their late-delivery rate.
CREATE OR REPLACE VIEW analytics.top_sellers_monthly AS
WITH ranked AS (
    SELECT *, RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS revenue_rank
    FROM analytics.seller_monthly
)
SELECT month, revenue_rank, seller_id, revenue, orders, delivered_orders, late_orders,
       round(100.0 * late_orders / NULLIF(delivered_orders, 0), 1) AS late_pct
FROM ranked
WHERE revenue_rank <= 10;

-- Q6: Revenue by the seller's city at the time of the order.
-- fact_order_item.seller_key is the dim_seller version valid on the purchase date (SCD2),
-- so a seller who moved counts under the old city before the move and the new city after.
CREATE OR REPLACE VIEW analytics.revenue_by_seller_city AS
SELECT make_date(d.year, d.month, 1) AS month,
       s.state                       AS seller_state,
       s.city                        AS seller_city,
       count(DISTINCT s.seller_id)   AS sellers,
       count(*)                      AS items,
       sum(i.price)                  AS revenue
FROM dw.fact_order_item i
JOIN dw.dim_seller s ON s.seller_key = i.seller_key
JOIN dw.dim_date d   ON d.date_key = i.purchase_date_key
GROUP BY make_date(d.year, d.month, 1), s.state, s.city;
