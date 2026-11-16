# AWS setup (lake and pipeline)

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
| IAM `lambda-ingest-role` | read `landing/`, write `raw/`, start the state machine, own log group ([policy](../infra/policies/lambda-ingest.json)) |
| IAM `glue-etl-role` | read `raw/` and `scripts/`, write `curated/ rejected/ dq/`, `/aws-glue/*` logs ([policy](../infra/policies/glue-etl.json)) |
| IAM `lambda-dq-role` | read `dq/`, own log group ([policy](../infra/policies/lambda-dq.json)) |
| IAM `sfn-pipeline-role` | run/poll the Glue job, invoke `check_dq`, publish to the alert topic ([policy](../infra/policies/sfn-pipeline.json)) |
| Lambda `on_batch_arrival` | Python 3.12, not in a VPC, 256 MB, 60 s; S3 trigger on `landing/…manifest.json`; starts the pipeline |
| Lambda `check_dq` | returns the batch's reject rate from `dq_summary.json` |
| Glue job `raw_to_curated` | Glue 5.0, 2 × G.1X, 15 min timeout, no retries; script and `rules.py` in `scripts/` |
| SNS topic `olist-pipeline-alerts` | email subscription to `$ALERT_EMAIL` (confirm the email once) |
| Step Functions `olist-batch-pipeline` | Standard; [definition](../orchestration/state_machine.json): RawToCurated → CheckDQ → reject rate > 5% ? NotifyFailure : NotifySuccess; every task catches into NotifyFailure → Fail |
| Athena workgroup `olist` | results in `athena-results/`, 100 MB scan limit per query, settings enforced |

The RDS warehouse is created separately: see [rds_setup.md](rds_setup.md).

## Running a batch

```bash
bash tools/upload_batch.sh 2018-04      # CSVs first, manifest last -> Lambda checks MD5s, copies to raw/, starts the pipeline
# ... email "Olist batch 2018-04 ready to load" arrives a few minutes later
python -m loader.curated_to_warehouse --batch 2018-04 --target rds
python -m tools.athena_query sql/athena/curated_tables.sql   # MSCK REPAIR picks up new batches
python -m tools.athena_query "SELECT count(*) FROM olist_lake.order_items WHERE batch_id='2018-04'"
```

## Verified

- Lambda log: `manifest OK: batch 2018-01, 7 files copied to raw/`. A manifest listing missing files logs `manifest FAILED` and copies nothing.
- Glue run on 2018-01 **Succeeded** in 115 s (231 DPU-seconds, about $0.03). Its `dq_summary.json` is identical to the local run.
- Athena: `order_items` 8,208 rows, price total 950,030.36; `orders` 7,269; `products` 4,088, all equal to local. The query scanned 17 KB.
- Uploading 2018-04 and 2018-05 ran RawToCurated → CheckDQ → NotifySuccess with no manual step; the success email arrived.
- A broken batch (`order_status` renamed in `orders.csv`, valid MD5s) failed at RawToCurated with `CSV header does not conform to the schema`, went to NotifyFailure and sent the failure email. Bad data is not retried: retries cover only transient Glue/Lambda service errors.

## Notes

- Tables are defined with `CREATE EXTERNAL TABLE … STORED AS PARQUET` instead of a Glue crawler (no crawler charges).
- The Glue script is the same file as the local job; it ignores Glue's own arguments (`parse_known_args`) and imports `rules.py` flat when shipped with `--extra-py-files`.
- Cleanup at the end of the project: delete the state machine, SNS topic, Glue job, Lambdas, roles, workgroup, `olist_lake` database, the RDS instance and the bucket (all versions).
