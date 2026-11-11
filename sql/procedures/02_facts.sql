-- Transaction fact: delete the batch's rows, then insert, so a rerun never duplicates.
-- Seller key = the version valid on the purchase date; any missing key becomes -1.
CREATE OR REPLACE PROCEDURE dw.load_fact_order_item(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM dw.fact_order_item WHERE batch_id = p_batch;

    INSERT INTO dw.fact_order_item (order_id, order_item_id, purchase_date_key, customer_key, seller_key,
                                    product_key, price, freight_value, batch_id)
    SELECT i.order_id, i.order_item_id, dw.date_key(o.order_purchase_timestamp),
           COALESCE(dc.customer_key, -1), COALESCE(ds.seller_key, -1), COALESCE(dp.product_key, -1),
           i.price, i.freight_value, p_batch
    FROM staging.order_items i
    JOIN staging.orders o USING (order_id)
    LEFT JOIN staging.customers c ON c.customer_id = o.customer_id
    LEFT JOIN dw.dim_customer dc ON dc.customer_unique_id = c.customer_unique_id
    LEFT JOIN dw.dim_seller ds ON ds.seller_id = i.seller_id
         AND o.order_purchase_timestamp::date BETWEEN ds.effective_start AND ds.effective_end
    LEFT JOIN dw.dim_product dp ON dp.product_id = i.product_id;
END $$;

-- Accumulating snapshot: one row per order, upserted so later milestones overwrite earlier ones.
CREATE OR REPLACE PROCEDURE dw.load_fact_order_fulfilment(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO dw.fact_order_fulfilment (order_id, customer_key, order_status, purchase_date_key,
                                          approved_date_key, shipped_date_key, delivered_date_key,
                                          estimated_date_key, delay_days, is_late, review_score, batch_id)
    SELECT o.order_id, COALESCE(dc.customer_key, -1), o.order_status,
           dw.date_key(o.order_purchase_timestamp), dw.date_key(o.order_approved_at),
           dw.date_key(o.order_delivered_carrier_date), dw.date_key(o.order_delivered_customer_date),
           dw.date_key(o.order_estimated_delivery_date),
           o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date,
           o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date,
           r.review_score, p_batch
    FROM staging.orders o
    LEFT JOIN staging.customers c ON c.customer_id = o.customer_id
    LEFT JOIN dw.dim_customer dc ON dc.customer_unique_id = c.customer_unique_id
    LEFT JOIN (SELECT DISTINCT ON (order_id) order_id, review_score     -- latest review per order
               FROM staging.order_reviews
               ORDER BY order_id, review_answer_timestamp DESC) r USING (order_id)
    ON CONFLICT (order_id) DO UPDATE
    SET customer_key = EXCLUDED.customer_key, order_status = EXCLUDED.order_status,
        approved_date_key = EXCLUDED.approved_date_key, shipped_date_key = EXCLUDED.shipped_date_key,
        delivered_date_key = EXCLUDED.delivered_date_key, estimated_date_key = EXCLUDED.estimated_date_key,
        delay_days = EXCLUDED.delay_days, is_late = EXCLUDED.is_late, review_score = EXCLUDED.review_score,
        batch_id = EXCLUDED.batch_id;
END $$;

CREATE OR REPLACE PROCEDURE dw.load_review_text(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM dw.review_text WHERE batch_id = p_batch;
    INSERT INTO dw.review_text (review_id, order_id, review_score, review_comment_title, review_comment_message,
                                review_creation_date, review_answer_timestamp, batch_id)
    SELECT review_id, order_id, review_score, review_comment_title, review_comment_message,
           review_creation_date::date, review_answer_timestamp, p_batch
    FROM staging.order_reviews;
END $$;
