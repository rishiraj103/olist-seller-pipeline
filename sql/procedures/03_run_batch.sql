-- Staging vs warehouse: row counts and price total for the batch.
CREATE OR REPLACE PROCEDURE dw.reconcile_batch(p_batch text)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO audit.reconciliation (batch_id, check_name, staging_value, warehouse_value)
    VALUES
      (p_batch, 'order_rows',
       (SELECT count(*) FROM staging.orders),
       (SELECT count(*) FROM dw.fact_order_fulfilment WHERE batch_id = p_batch)),
      (p_batch, 'order_item_rows',
       (SELECT count(*) FROM staging.order_items),
       (SELECT count(*) FROM dw.fact_order_item WHERE batch_id = p_batch)),
      (p_batch, 'order_item_price_total',
       (SELECT COALESCE(sum(price), 0) FROM staging.order_items),
       (SELECT COALESCE(sum(price), 0) FROM dw.fact_order_item WHERE batch_id = p_batch)),
      (p_batch, 'review_rows',
       (SELECT count(*) FROM staging.order_reviews),
       (SELECT count(*) FROM dw.review_text WHERE batch_id = p_batch));
END $$;

-- Loads one staged batch end to end. All loads run in one sub-transaction: on error they roll back,
-- the error is logged and committed, then re-raised. Call with autocommit on: CALL dw.run_batch('2018-03');
CREATE OR REPLACE PROCEDURE dw.run_batch(p_batch text)
LANGUAGE plpgsql AS $$
DECLARE
    v_run   integer;
    v_date  date;
    v_step  text;
    v_state text;
    v_error text;
    v_diffs integer;
BEGIN
    INSERT INTO audit.batch_log (batch_id, status) VALUES (p_batch, 'RUNNING') RETURNING run_id INTO v_run;
    COMMIT;

    BEGIN
        v_step := 'check_staging';
        SELECT min(order_purchase_timestamp)::date INTO v_date FROM staging.orders WHERE batch_id = p_batch;
        IF v_date IS NULL THEN
            RAISE EXCEPTION 'staging has no orders for batch %', p_batch;
        END IF;
        v_step := 'load_dim_customer';          CALL dw.load_dim_customer(p_batch);
        v_step := 'load_dim_product';           CALL dw.load_dim_product(p_batch);
        v_step := 'load_dim_seller_scd2';       CALL dw.load_dim_seller_scd2(p_batch, v_date);
        v_step := 'load_fact_order_item';       CALL dw.load_fact_order_item(p_batch);
        v_step := 'load_fact_order_fulfilment'; CALL dw.load_fact_order_fulfilment(p_batch);
        v_step := 'load_review_text';           CALL dw.load_review_text(p_batch);
        v_step := 'reconcile_batch';            CALL dw.reconcile_batch(p_batch);
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_error = MESSAGE_TEXT;
    END;

    IF v_error IS NOT NULL THEN
        INSERT INTO audit.etl_error_log (batch_id, step, sqlstate, message) VALUES (p_batch, v_step, v_state, v_error);
        UPDATE audit.batch_log SET status = 'FAILED', ended_at = now(), message = v_step || ': ' || v_error
        WHERE run_id = v_run;
        COMMIT;
        RAISE EXCEPTION 'run_batch % failed at %: %', p_batch, v_step, v_error;
    END IF;

    SELECT count(*) INTO v_diffs FROM audit.reconciliation
    WHERE batch_id = p_batch AND difference <> 0
      AND checked_at = (SELECT max(checked_at) FROM audit.reconciliation WHERE batch_id = p_batch);

    UPDATE audit.batch_log
    SET status = CASE WHEN v_diffs = 0 THEN 'SUCCESS' ELSE 'FAILED' END, ended_at = now(),
        message = CASE WHEN v_diffs = 0 THEN 'ok' ELSE v_diffs || ' reconciliation differences' END
    WHERE run_id = v_run;
    COMMIT;
END $$;
