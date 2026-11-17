-- Q2: Top 10 sellers per month by revenue, with late-delivery rate.
-- Defined once as the view analytics.top_sellers_monthly (sql/ddl/07_analytics_views.sql).
SELECT month, revenue_rank, seller_id, revenue, orders, delivered_orders, late_orders, late_pct
FROM analytics.top_sellers_monthly
ORDER BY month, revenue_rank
