-- One batch of curated rows at a time; the loader truncates and refills these before CALL dw.run_batch.
CREATE TABLE IF NOT EXISTS staging.orders (
    order_id text, customer_id text, order_status text,
    order_purchase_timestamp timestamp, order_approved_at timestamp, order_delivered_carrier_date timestamp,
    order_delivered_customer_date timestamp, order_estimated_delivery_date timestamp,
    batch_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.order_items (
    order_id text, order_item_id smallint, product_id text, seller_id text,
    shipping_limit_date timestamp, price numeric(10,2), freight_value numeric(10,2),
    batch_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.order_reviews (
    review_id text, order_id text, review_score smallint, review_comment_title text,
    review_comment_message text, review_creation_date timestamp, review_answer_timestamp timestamp,
    batch_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.customers (
    customer_id text, customer_unique_id text, customer_zip_code_prefix text, customer_city text,
    customer_state text, batch_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.sellers (
    seller_id text, seller_zip_code_prefix text, seller_city text, seller_state text,
    batch_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.products (
    product_category_name text, product_id text, product_name_length smallint,
    product_description_length integer, product_photos_qty smallint, product_weight_g integer,
    product_length_cm smallint, product_height_cm smallint, product_width_cm smallint,
    product_category_name_english text, batch_id text NOT NULL
);
