-- Empty the warehouse for a clean full reload. Keeps dim_date, the -1 "Unknown" rows, users and views.
TRUNCATE dw.fact_order_item, dw.fact_order_fulfilment, dw.review_text;
DELETE FROM dw.dim_seller   WHERE seller_key   <> -1;
DELETE FROM dw.dim_customer WHERE customer_key <> -1;
DELETE FROM dw.dim_product  WHERE product_key  <> -1;
TRUNCATE audit.batch_log, audit.dq_results, audit.reconciliation, audit.etl_error_log;
TRUNCATE staging.orders, staging.order_items, staging.order_reviews, staging.customers, staging.sellers, staging.products;
