# Changelog

## v0.10-genai — 2026-11-19
- `genai/llm_client.py`: local Ollama (`qwen2.5:7b`) by default, Bedrock Converse as a drop-in swap (`LLM_PROVIDER=bedrock`); logs tokens and response time.
- `genai/insights.py` `explain_seller`: two fixed parameterised queries (seller monthly metrics vs. category average; up to 30 low-star review texts), "not enough data" below 10 reviews, no customer identifiers sent.
- Number-check guardrail: an answer with a number not found in the data is replaced by the metrics and a warning (unit-tested).
- `docs/genai_eval.md`: 5 sellers checked by hand; 4 of 5 fully traceable, themes found but counts approximate; prompt and model changes measured.

## v0.9-analytics — 2026-11-18
- Six business queries in `sql/analytics/` (window functions, CTEs, SCD2 history); Q1, Q2, Q6 are views in the `analytics` schema for the app; `app_reader` can read them.
- `tools/run_analytics.py` saves results to `docs/results/*.csv` and runs the validation queries in `sql/checks/` (all return no rows).
- Index experiment: composite `(seller_key, purchase_date_key)` makes the seller scorecard query 7× faster than a scan and replaces the single-column seller index; Q2 is a full aggregation and is not helped by indexes.
- Athena query on the curated lake scans 51 KB and matches the warehouse.

## v0.8-aws-pipeline — 2026-11-16
- Step Functions `olist-batch-pipeline`: Glue → `check_dq` Lambda → reject-rate gate (5%) → SNS email; every task catches into a failure email; retries only on transient service errors.
- `on_batch_arrival` starts the pipeline after the manifest check: uploading a batch needs no other step.
- The transform now fails on a CSV header that does not match the schema (`enforceSchema=False`); a broken batch fails at RawToCurated and emails.
- RDS PostgreSQL 16 warehouse (`infra/setup_rds.sh`, `infra/init_rds_db.sh`) with `etl_writer` and read-only `app_reader` users.
- Loader `--target rds` reads curated Parquet from S3 into RDS; batches 2018-01 and 2018-04 loaded with 0 reconciliation difference.

## v0.7-aws-lake — 2026-11-14
- `infra/setup_aws.sh` (rerun-safe) creates the S3 lake (private, encrypted, versioned, lifecycle rules), least-privilege IAM roles, the ingest Lambda, the Glue 5.0 job and an Athena workgroup with a 100 MB scan limit.
- Lambda `on_batch_arrival` checks every manifest file's MD5 and copies the batch from `landing/` to `raw/`; a bad manifest fails and copies nothing.
- Glue `raw_to_curated` runs the Step 5 script unchanged; batch 2018-01 succeeded and its DQ summary equals the local run.
- Athena external tables over curated Parquet (`sql/athena/`); counts and price totals for 2018-01 match local.

## v0.6-warehouse-local — 2026-11-12
- `loader/curated_to_warehouse.py` refills `staging.*` from curated Parquet (COPY), records DQ results and calls `dw.run_batch`.
- PL/pgSQL procedures: SCD1 customer/product, SCD2 seller, idempotent fact loads with point-in-time seller lookup, reconciliation, `run_batch` with error logging.
- All 9 batches loaded locally: 0 reconciliation difference, 10 sellers with two versions, no fact rows on `-1` keys; rerunning a batch changes no row count (integration test).

## v0.5-transform — 2026-11-09
- `transform/rules.py`: data-quality rules as pure functions returning `(good, bad)`; 11 unit tests.
- `transform/raw_to_curated.py`: explicit schemas, curated Parquet, rejected rows with `reject_reason`, `dq_summary.json`; same script for local and Glue.
- Batch 2018-02 rejects exactly the 7 injected item rows; 23 real `delivered_before_shipped` orders (and their 50 items, 23 reviews) are rejected.

## v0.4-batches — 2026-11-07
- `tools/make_batches.py` splits the source into 9 batches (2017-12 initial, 2018-01 .. 2018-08) with MD5 manifests; order totals match the source (99,441).
- 10 simulated seller moves from batch 2018-03 (`docs/simulated_changes.csv`); 7 injected bad items in batch 2018-02 (`docs/injected_rows.csv`).

## v0.3-design — 2026-11-06
- Star schema DDL in `sql/ddl/`: schemas `staging`, `dw`, `audit`; dimensions with `-1` Unknown rows; transaction and accumulating-snapshot facts; `review_text`; audit tables; FK indexes.
- `dim_seller` is SCD Type 2 with one current row per seller enforced by a partial unique index.
- `dim_date` populated for 2016–2020. All DDL is rerun-safe and tested on local PostgreSQL.
- `docs/warehouse_design.md`: grains, star diagram and design decisions.

## v0.2-profiling — 2026-11-04
- `tools/profile_data.py` profiles all 9 source files and checks each known data problem.
- `docs/data_profile.md`: row counts, nulls, duplicates and a pipeline rule for every confirmed problem.
- `docs/source_er.md`: source ER diagram.
- Finding: repeated `review_id`s are one review shared by several orders, not duplicate rows; rule is the latest review per order.
- Development moved to WSL (Ubuntu 24.04): Windows Smart App Control blocks pandas native libraries.

## v0.1-setup — 2026-11-02
- Repo structure, `.gitignore`, `.env.example`, requirements (PySpark 3.5 to match Glue 5.0).
- GitHub Actions runs `unittest` on every push.
- Local PostgreSQL 16 in Docker; AWS CLI configured.
- AWS region is `ap-southeast-2`: the AWS Free plan locks the account to one region.
- GenAI will use a local Ollama model instead of Bedrock: Bedrock quotas are 0 and not adjustable on the Free plan.
