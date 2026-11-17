-- Q4: Product categories with the most 1-2 star reviews on late orders.
-- An order counts once per category it contains; categories need at least 20 such orders.
SELECT p.category_name_english                                          AS category,
       count(DISTINCT f.order_id)                                       AS late_orders,
       count(DISTINCT f.order_id) FILTER (WHERE f.review_score <= 2)    AS late_low_review_orders,
       round(100.0 * count(DISTINCT f.order_id) FILTER (WHERE f.review_score <= 2)
             / count(DISTINCT f.order_id), 1)                           AS low_review_pct
FROM dw.fact_order_fulfilment f
JOIN dw.fact_order_item i ON i.order_id = f.order_id
JOIN dw.dim_product p     ON p.product_key = i.product_key
WHERE f.is_late
GROUP BY p.category_name_english
HAVING count(DISTINCT f.order_id) FILTER (WHERE f.review_score <= 2) >= 20
ORDER BY late_low_review_orders DESC
LIMIT 15
