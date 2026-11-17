-- Q3: Month-over-month revenue growth per product category.
-- Growth is only computed against the calendar month directly before (a category with no sales in a month has no row).
WITH category_month AS (
    SELECT p.category_name_english        AS category,
           make_date(d.year, d.month, 1)  AS month,
           sum(i.price)                   AS revenue
    FROM dw.fact_order_item i
    JOIN dw.dim_product p ON p.product_key = i.product_key
    JOIN dw.dim_date d    ON d.date_key = i.purchase_date_key
    GROUP BY p.category_name_english, make_date(d.year, d.month, 1)
), with_previous AS (
    SELECT category, month, revenue,
           CASE WHEN LAG(month) OVER w = month - interval '1 month' THEN LAG(revenue) OVER w END AS prev_revenue
    FROM category_month
    WINDOW w AS (PARTITION BY category ORDER BY month)
)
SELECT category, month, revenue, prev_revenue,
       round(100.0 * (revenue - prev_revenue) / NULLIF(prev_revenue, 0), 1) AS growth_pct
FROM with_previous
ORDER BY category, month
