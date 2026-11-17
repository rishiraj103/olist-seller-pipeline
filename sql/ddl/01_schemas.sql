-- staging: one batch at a time, emptied before each load
-- dw:      star schema
-- audit:   batch, data-quality, reconciliation and error logs
-- analytics: views the app reads
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS analytics;
