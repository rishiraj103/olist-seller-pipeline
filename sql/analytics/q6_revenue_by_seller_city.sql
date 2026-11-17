-- Q6: Revenue by seller's city at the time of the order (SCD Type 2 history).
-- Defined once as the view analytics.revenue_by_seller_city (sql/ddl/07_analytics_views.sql).
SELECT seller_state, seller_city, sum(items) AS items, sum(revenue) AS revenue
FROM analytics.revenue_by_seller_city
GROUP BY seller_state, seller_city
ORDER BY revenue DESC
