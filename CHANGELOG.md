# Changelog

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
