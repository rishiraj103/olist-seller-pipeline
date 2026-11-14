-- Athena external tables over curated Parquet (no crawler). Run: python -m tools.athena_query sql/athena/curated_tables.sql
CREATE DATABASE IF NOT EXISTS olist_lake;

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.orders (
    order_id string, customer_id string, order_status string, order_purchase_timestamp timestamp,
    order_approved_at timestamp, order_delivered_carrier_date timestamp,
    order_delivered_customer_date timestamp, order_estimated_delivery_date timestamp)
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/orders/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.order_items (
    order_id string, order_item_id int, product_id string, seller_id string, shipping_limit_date timestamp,
    price decimal(10,2), freight_value decimal(10,2))
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/order_items/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.order_reviews (
    order_id string, review_id string, review_score int, review_comment_title string,
    review_comment_message string, review_creation_date timestamp, review_answer_timestamp timestamp)
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/order_reviews/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.customers (
    customer_id string, customer_unique_id string, customer_zip_code_prefix string,
    customer_city string, customer_state string)
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/customers/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.sellers (
    seller_id string, seller_zip_code_prefix string, seller_city string, seller_state string)
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/sellers/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_lake.products (
    product_category_name string, product_id string, product_name_length int, product_description_length int,
    product_photos_qty int, product_weight_g int, product_length_cm int, product_height_cm int,
    product_width_cm int, product_category_name_english string)
PARTITIONED BY (batch_id string) STORED AS PARQUET LOCATION 's3://${BUCKET}/curated/products/';

MSCK REPAIR TABLE olist_lake.orders;
MSCK REPAIR TABLE olist_lake.order_items;
MSCK REPAIR TABLE olist_lake.order_reviews;
MSCK REPAIR TABLE olist_lake.customers;
MSCK REPAIR TABLE olist_lake.sellers;
MSCK REPAIR TABLE olist_lake.products;
