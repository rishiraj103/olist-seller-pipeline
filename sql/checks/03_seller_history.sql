-- SCD2 integrity of dim_seller. Expected: no rows.
SELECT 'more than one current row' AS problem, seller_id, count(*) AS problem_rows
FROM dw.dim_seller WHERE is_current
GROUP BY seller_id HAVING count(*) > 1
UNION ALL
SELECT 'overlapping versions', a.seller_id, count(*)
FROM dw.dim_seller a
JOIN dw.dim_seller b ON b.seller_id = a.seller_id AND b.seller_key > a.seller_key
                    AND a.effective_start <= b.effective_end AND b.effective_start <= a.effective_end
GROUP BY a.seller_id
UNION ALL
SELECT 'fact row outside its seller version dates', i.order_id, count(*)
FROM dw.fact_order_item i
JOIN dw.dim_seller s ON s.seller_key = i.seller_key
JOIN dw.dim_date d   ON d.date_key = i.purchase_date_key
WHERE i.seller_key <> -1 AND d.full_date NOT BETWEEN s.effective_start AND s.effective_end
GROUP BY i.order_id
