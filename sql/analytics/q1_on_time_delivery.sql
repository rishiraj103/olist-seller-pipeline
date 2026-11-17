-- Q1: On-time delivery % by customer state and month.
-- Defined once as the view analytics.on_time_delivery (sql/ddl/07_analytics_views.sql).
SELECT customer_state, month, delivered_orders, on_time_orders, on_time_pct
FROM analytics.on_time_delivery
ORDER BY customer_state, month
