-- Views the Streamlit app reads (Q1, Q2, Q6). Revenue = item price (freight excluded). Months are purchase months.

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

-- Q2: Top 10 sellers per month by revenue, with their late-delivery rate.
CREATE OR REPLACE VIEW analytics.top_sellers_monthly AS
WITH seller_month AS (
    SELECT s.seller_id,
           make_date(d.year, d.month, 1)                                   AS month,
           sum(i.price)                                                    AS revenue,
           count(DISTINCT i.order_id)                                      AS orders,
           count(DISTINCT i.order_id) FILTER (WHERE f.is_late IS NOT NULL) AS delivered_orders,
           count(DISTINCT i.order_id) FILTER (WHERE f.is_late)             AS late_orders
    FROM dw.fact_order_item i
    JOIN dw.dim_seller s            ON s.seller_key = i.seller_key
    JOIN dw.dim_date d              ON d.date_key = i.purchase_date_key
    JOIN dw.fact_order_fulfilment f ON f.order_id = i.order_id
    GROUP BY s.seller_id, make_date(d.year, d.month, 1)
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS revenue_rank
    FROM seller_month
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
