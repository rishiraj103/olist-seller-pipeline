-- One row per batch run (a rerun adds a new row).
CREATE TABLE IF NOT EXISTS audit.batch_log (
    run_id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id    text        NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT now(),
    ended_at    timestamptz,
    status      text        NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    message     text
);

-- One row per table and data-quality rule, copied from dq_summary.json.
CREATE TABLE IF NOT EXISTS audit.dq_results (
    batch_id     text    NOT NULL,
    table_name   text    NOT NULL,
    rule_name    text    NOT NULL,
    rows_read    integer NOT NULL CHECK (rows_read >= 0),
    rows_failed  integer NOT NULL CHECK (rows_failed >= 0),
    PRIMARY KEY (batch_id, table_name, rule_name)
);

-- One row per reconciliation check (staging vs warehouse).
CREATE TABLE IF NOT EXISTS audit.reconciliation (
    batch_id         text          NOT NULL,
    check_name       text          NOT NULL,     -- e.g. order_item_rows, order_item_price_total
    staging_value    numeric(14,2) NOT NULL,
    warehouse_value  numeric(14,2) NOT NULL,
    difference       numeric(14,2) GENERATED ALWAYS AS (warehouse_value - staging_value) STORED,
    checked_at       timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, check_name, checked_at)
);

-- One row per error caught in run_batch.
CREATE TABLE IF NOT EXISTS audit.etl_error_log (
    error_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id   text        NOT NULL,
    step       text        NOT NULL,
    sqlstate   text,
    message    text        NOT NULL,
    logged_at  timestamptz NOT NULL DEFAULT now()
);
