-- Q5: Share of customers who ordered more than once.
-- A real customer is customer_unique_id (customer_id changes on every order).
SELECT count(*)                                                      AS customers,
       count(*) FILTER (WHERE orders > 1)                            AS repeat_customers,
       round(100.0 * count(*) FILTER (WHERE orders > 1) / count(*), 2) AS repeat_pct
FROM (
    SELECT c.customer_unique_id, count(DISTINCT f.order_id) AS orders
    FROM dw.fact_order_fulfilment f
    JOIN dw.dim_customer c ON c.customer_key = f.customer_key
    GROUP BY c.customer_unique_id
) per_customer
