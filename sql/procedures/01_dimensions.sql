-- Date key for a timestamp; -1 when the date is NULL (milestone not reached) or outside dim_date.
CREATE OR REPLACE FUNCTION dw.date_key(ts timestamp) RETURNS integer
LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT date_key FROM dw.dim_date WHERE full_date = ts::date), -1)
$$;

-- SCD Type 1: one row per real customer; the address from the customer's latest order in the batch wins.
CREATE OR REPLACE PROCEDURE dw.load_dim_customer(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO dw.dim_customer (customer_unique_id, zip_code_prefix, city, state, updated_batch_id)
    SELECT DISTINCT ON (c.customer_unique_id)
           c.customer_unique_id, c.customer_zip_code_prefix, c.customer_city, c.customer_state, p_batch
    FROM staging.customers c
    LEFT JOIN staging.orders o USING (customer_id)
    ORDER BY c.customer_unique_id, o.order_purchase_timestamp DESC NULLS LAST
    ON CONFLICT (customer_unique_id) DO UPDATE
    SET zip_code_prefix = EXCLUDED.zip_code_prefix, city = EXCLUDED.city, state = EXCLUDED.state,
        updated_batch_id = EXCLUDED.updated_batch_id
    WHERE (dw.dim_customer.zip_code_prefix, dw.dim_customer.city, dw.dim_customer.state)
          IS DISTINCT FROM (EXCLUDED.zip_code_prefix, EXCLUDED.city, EXCLUDED.state);
END $$;

-- SCD Type 1: product corrections overwrite.
CREATE OR REPLACE PROCEDURE dw.load_dim_product(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO dw.dim_product (product_id, category_name, category_name_english, product_name_length,
                                product_description_length, product_photos_qty, product_weight_g,
                                product_length_cm, product_height_cm, product_width_cm, updated_batch_id)
    SELECT product_id, product_category_name, product_category_name_english, product_name_length,
           product_description_length, product_photos_qty, product_weight_g,
           product_length_cm, product_height_cm, product_width_cm, p_batch
    FROM staging.products
    ON CONFLICT (product_id) DO UPDATE
    SET category_name = EXCLUDED.category_name, category_name_english = EXCLUDED.category_name_english,
        product_name_length = EXCLUDED.product_name_length,
        product_description_length = EXCLUDED.product_description_length,
        product_photos_qty = EXCLUDED.product_photos_qty, product_weight_g = EXCLUDED.product_weight_g,
        product_length_cm = EXCLUDED.product_length_cm, product_height_cm = EXCLUDED.product_height_cm,
        product_width_cm = EXCLUDED.product_width_cm, updated_batch_id = EXCLUDED.updated_batch_id;
END $$;

-- SCD Type 2 on (city, state). p_date = first purchase date in the batch: the new version starts there,
-- the old one ends the day before, so every order is matched to the version valid on its purchase date.
-- The hash coalesces NULLs: with plain ||, one NULL makes the whole hash NULL and the change check skips the row.
CREATE OR REPLACE PROCEDURE dw.load_dim_seller_scd2(p_batch text, p_date date)
LANGUAGE plpgsql AS $$
BEGIN
    -- 1) close versions whose tracked columns changed
    UPDATE dw.dim_seller d
    SET    effective_end = p_date - 1, is_current = false
    FROM   staging.sellers s
    WHERE  d.seller_id = s.seller_id AND d.is_current
      AND  d.row_hash <> md5(coalesce(s.seller_city, '') || '|' || coalesce(s.seller_state, ''));

    -- 2) insert new sellers and new versions (sellers with no current row)
    INSERT INTO dw.dim_seller (seller_id, zip_code_prefix, city, state, row_hash, effective_start)
    SELECT s.seller_id, s.seller_zip_code_prefix, s.seller_city, s.seller_state,
           md5(coalesce(s.seller_city, '') || '|' || coalesce(s.seller_state, '')), p_date
    FROM   staging.sellers s
    LEFT JOIN dw.dim_seller d ON d.seller_id = s.seller_id AND d.is_current
    WHERE  d.seller_id IS NULL;
END $$;
