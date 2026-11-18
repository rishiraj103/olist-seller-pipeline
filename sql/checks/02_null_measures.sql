-- Missing measures. Expected: no rows.
SELECT 'item price or freight is NULL' AS problem, count(*) AS problem_rows
FROM dw.fact_order_item WHERE price IS NULL OR freight_value IS NULL
HAVING count(*) > 0
UNION ALL
SELECT 'delivered order without delay_days/is_late', count(*)
FROM dw.fact_order_fulfilment WHERE delivered_date_key <> -1 AND (delay_days IS NULL OR is_late IS NULL)
HAVING count(*) > 0
UNION ALL
SELECT 'is_late disagrees with delay_days', count(*)
FROM dw.fact_order_fulfilment WHERE is_late <> (delay_days > 0)
HAVING count(*) > 0
