-- Transaction fact. Grain: one item in one order.
-- order_id is a degenerate dimension (no dim_order table).
CREATE TABLE IF NOT EXISTS dw.fact_order_item (
    order_id           text     NOT NULL,
    order_item_id      smallint NOT NULL CHECK (order_item_id > 0),
    purchase_date_key  integer  NOT NULL REFERENCES dw.dim_date (date_key),
    customer_key       integer  NOT NULL REFERENCES dw.dim_customer (customer_key),
    seller_key         integer  NOT NULL REFERENCES dw.dim_seller (seller_key),   -- version valid on purchase date
    product_key        integer  NOT NULL REFERENCES dw.dim_product (product_key),
    price              numeric(10,2) NOT NULL CHECK (price > 0),
    freight_value      numeric(10,2) NOT NULL CHECK (freight_value >= 0),
    batch_id           text     NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

-- Accumulating snapshot. Grain: one order with all its milestone dates.
-- Milestones not reached point to date_key -1.
CREATE TABLE IF NOT EXISTS dw.fact_order_fulfilment (
    order_id            text     PRIMARY KEY,
    customer_key        integer  NOT NULL REFERENCES dw.dim_customer (customer_key),
    order_status        text     NOT NULL CHECK (order_status IN
                          ('created','approved','invoiced','processing','shipped','delivered','canceled','unavailable')),
    purchase_date_key   integer  NOT NULL REFERENCES dw.dim_date (date_key),
    approved_date_key   integer  NOT NULL REFERENCES dw.dim_date (date_key),
    shipped_date_key    integer  NOT NULL REFERENCES dw.dim_date (date_key),
    delivered_date_key  integer  NOT NULL REFERENCES dw.dim_date (date_key),
    estimated_date_key  integer  NOT NULL REFERENCES dw.dim_date (date_key),
    delay_days          integer,                 -- delivered - estimated, in days; NULL if not delivered
    is_late             boolean,                 -- delay_days > 0; NULL if not delivered
    review_score        smallint CHECK (review_score BETWEEN 1 AND 5),  -- latest review; NULL if none
    batch_id            text     NOT NULL
);

-- Supporting table for GenAI. One review can cover several orders.
CREATE TABLE IF NOT EXISTS dw.review_text (
    review_id                text      NOT NULL,
    order_id                 text      NOT NULL,
    review_score             smallint  NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title     text,
    review_comment_message   text,
    review_creation_date     date      NOT NULL,
    review_answer_timestamp  timestamp NOT NULL,
    batch_id                 text      NOT NULL,
    PRIMARY KEY (review_id, order_id)
);

-- Foreign-key indexes. The composite (seller_key, purchase_date_key) index is added in the Step 9 experiment.
CREATE INDEX IF NOT EXISTS ix_foi_purchase_date ON dw.fact_order_item (purchase_date_key);
CREATE INDEX IF NOT EXISTS ix_foi_customer      ON dw.fact_order_item (customer_key);
CREATE INDEX IF NOT EXISTS ix_foi_seller        ON dw.fact_order_item (seller_key);
CREATE INDEX IF NOT EXISTS ix_foi_product       ON dw.fact_order_item (product_key);
CREATE INDEX IF NOT EXISTS ix_foi_batch         ON dw.fact_order_item (batch_id);
CREATE INDEX IF NOT EXISTS ix_fof_customer      ON dw.fact_order_fulfilment (customer_key);
CREATE INDEX IF NOT EXISTS ix_fof_purchase_date ON dw.fact_order_fulfilment (purchase_date_key);
CREATE INDEX IF NOT EXISTS ix_fof_delivered     ON dw.fact_order_fulfilment (delivered_date_key);
CREATE INDEX IF NOT EXISTS ix_rt_order          ON dw.review_text (order_id);
