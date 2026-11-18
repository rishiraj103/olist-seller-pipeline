-- Fact rows pointing to a -1 "Unknown" dimension row. Expected: no rows.
SELECT 'fact_order_item' AS table_name, key_name, count(*) AS problem_rows
FROM dw.fact_order_item,
     LATERAL (VALUES ('purchase_date_key', purchase_date_key), ('customer_key', customer_key),
                     ('seller_key', seller_key), ('product_key', product_key)) k(key_name, key_value)
WHERE key_value = -1
GROUP BY key_name
UNION ALL
SELECT 'fact_order_fulfilment', key_name, count(*)
FROM dw.fact_order_fulfilment,
     LATERAL (VALUES ('customer_key', customer_key), ('purchase_date_key', purchase_date_key)) k(key_name, key_value)
WHERE key_value = -1
GROUP BY key_name
