# SQL analytics

Six business questions in `sql/analytics/`; Q1, Q2 and Q6 are views in the `analytics` schema
(`sql/ddl/07_analytics_views.sql`) and are what the app reads. Run everything with:

```bash
python -m tools.run_analytics              # local warehouse; --target rds for RDS
```

It writes each result to `docs/results/<query>.csv` and runs the validation queries in `sql/checks/`,
failing if any returns a row. Results below are from the warehouse with all 9 batches (112,600 items); the RDS run
after the full AWS pipeline produced byte-identical CSVs (queries take 0.5–1.5 s on `db.t4g.micro` over the internet).

| # | Question | Technique | Rows | Headline |
| --- | --- | --- | --- | --- |
| Q1 | On-time delivery % by customer state and month | JOIN, CASE, GROUP BY | 556 | SP: 96.6% (Jan 2018) → 90.6% (Mar 2018) |
| Q2 | Top 10 sellers per month by revenue, with late-delivery rate | CTE, RANK(), fulfilment join | 215 | ties share a rank |
| Q3 | Month-over-month revenue growth per category | LAG(), NULLIF | 1,283 | growth only vs. the directly preceding month |
| Q4 | Categories with most 1–2 star reviews on late orders | multi-table join, HAVING | 15 | bed_bath_table: 432 of 689 late orders (62.7%) |
| Q5 | Share of customers who ordered more than once | subquery, COUNT DISTINCT | 1 | 2,994 of 96,076 customers (3.12%) |
| Q6 | Revenue by seller city at the time of the order | SCD2 version key | 636 | moved sellers count under the old city before the move |

Revenue is the item price (freight excluded); months are purchase months.

## Validation (`sql/checks/`)

All return no rows: no fact rows on `-1` keys, no missing measures (and `is_late` agrees with `delay_days`),
one current row per seller with no overlapping versions and every fact inside its seller version's dates,
and no non-zero reconciliation difference.

## Index experiment

Local PostgreSQL 16, `fact_order_item` = 112,600 rows; median of 7 `EXPLAIN ANALYZE` runs.

| Query | No seller index | `ix_foi_seller (seller_key)` | `ix_foi_seller_date (seller_key, purchase_date_key)` |
| --- | --- | --- | --- |
| Seller scorecard: one seller, 2018, monthly revenue | 11.3 ms (seq scan) | 2.0 ms | **1.6 ms** |
| Q2: top 10 sellers per month (whole table) | — | 302 ms | 284 ms |

- The composite index makes the per-seller query the app runs **7× faster** than a scan, and slightly faster than
  the single-column index. Because its leading column is `seller_key`, it replaces that index (one index to maintain, not two).
- Q2 aggregates every row (16,434 seller-months) so it is a full scan either way; raising `work_mem` from 4 MB to
  32 MB removed its disk sort but did not change the time (293 → 298 ms). If it ever matters, the fix is a
  pre-aggregated monthly seller table, not an index.

## Athena on the lake

`sql/athena/items_per_batch.sql` (items and revenue per batch from curated Parquet) scanned **51 KB** for three
batches and **238 KB** for all nine; per-batch counts and revenue equal the warehouse (112,600 items in total).

## Known data limitation

Seller cities are free text in the source: São Paulo also appears as `sao paulo - sp`, `sao paulo sp`, `sao paulop`.
Q6 groups by the city as written; a city-name cleanup table would merge them.
