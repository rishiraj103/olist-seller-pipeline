# AWS setup (Step 7: the lake)

Region `ap-southeast-2` (the AWS Free plan locks the account to one region). Everything is created by one rerun-safe script:

```bash
set -a; . ./.env; set +a          # S3_BUCKET, AWS_REGION
bash infra/setup_aws.sh
```

## What it creates

| Resource | Settings |
| --- | --- |
| S3 bucket `$S3_BUCKET` | all public access blocked, SSE-S3 encryption, versioning on; prefixes `landing/ raw/ curated/ rejected/ dq/ scripts/ athena-results/` |
| Lifecycle | `landing/` objects expire after 30 days; old versions after 7 days; incomplete uploads aborted after 7 days |
| IAM `lambda-ingest-role` | read `landing/`, write `raw/`, its own CloudWatch log group ([policy](../infra/policies/lambda-ingest.json)) |
| IAM `glue-etl-role` | read `raw/` and `scripts/`, write `curated/ rejected/ dq/`, `/aws-glue/*` logs ([policy](../infra/policies/glue-etl.json)) |
| Lambda `on_batch_arrival` | Python 3.12, not in a VPC, 256 MB, 60 s; S3 trigger on `landing/…manifest.json` |
| Glue job `raw_to_curated` | Glue 5.0, 2 × G.1X, 15 min timeout, no retries; script and `rules.py` in `scripts/` |
| Athena workgroup `olist` | results in `athena-results/`, 100 MB scan limit per query, settings enforced |

## Running a batch

```bash
bash tools/upload_batch.sh 2018-01      # CSVs first, manifest last -> Lambda checks MD5s and copies to raw/
aws glue start-job-run --job-name raw_to_curated \
  --arguments '{"--batch_id":"2018-01","--input":"s3://'$S3_BUCKET'/raw/batch_id=2018-01"}'
python -m tools.athena_query sql/athena/curated_tables.sql   # once; MSCK REPAIR picks up new batches on rerun
python -m tools.athena_query "SELECT count(*) FROM olist_lake.order_items WHERE batch_id='2018-01'"
```

## Verified on batch 2018-01

- Lambda log: `manifest OK: batch 2018-01, 7 files copied to raw/`. A manifest listing missing files logs `manifest FAILED` and copies nothing.
- Glue run **Succeeded** in 115 s (231 DPU-seconds, about $0.03). Its `dq_summary.json` is identical to the local run.
- Athena: `order_items` 8,208 rows, price total 950,030.36; `orders` 7,269; `products` 4,088, all equal to local. The query scanned 17 KB.

## Notes

- Tables are defined with `CREATE EXTERNAL TABLE … STORED AS PARQUET` instead of a Glue crawler (no crawler charges).
- The Glue script is the same file as the local job; it ignores Glue's own arguments (`parse_known_args`) and imports `rules.py` flat when shipped with `--extra-py-files`.
- Cleanup at the end of the project: delete the Glue job, Lambda, roles, workgroup, `olist_lake` database and the bucket (all versions).
