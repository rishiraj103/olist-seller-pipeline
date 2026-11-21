# RDS warehouse setup

```bash
set -a; . ./.env; set +a
bash infra/setup_rds.sh      # security group + instance; prints the endpoint -> put it in RDS_HOST
bash infra/init_rds_db.sh    # all DDL, procedures and users (rerun-safe)
python -m loader.curated_to_warehouse --batch 2018-04 --target rds
```

## Instance

| Setting | Value |
| --- | --- |
| Engine | PostgreSQL 16.15, `db.t4g.micro`, 20 GB gp2, encrypted, single-AZ |
| Backups | 1 day; no Performance Insights or enhanced monitoring |
| Network | default VPC, publicly accessible; security group `olist-rds-sg` allows 5432 from the developer's IP only; SSL required |
| Users | `olist_admin` (master, DDL only); `etl_writer` (staging/dw/audit read-write, runs procedures; used by the loader); `app_reader` (SELECT on `dw` and `audit`, including future views) |

Passwords live only in the local `.env`; `sql/admin/users.sql` takes them as psql variables.

## Loading

`--target rds` reads the batch's curated Parquet and `dq_summary.json` from `s3://$S3_BUCKET/` and connects with the `RDS_*` settings (`etl_writer`). Everything else is the same code path as the local load: refill `staging.*`, record DQ results, `CALL dw.run_batch(...)`.

Verified: batches 2018-01 and 2018-04 loaded with `SUCCESS` and 0 reconciliation difference; reloading 2018-04 changed no counts; `app_reader` can read facts and is denied `DELETE`.

Full clean run (`sql/admin/reset_warehouse.sql`, emptied lake, `tools/run_all_batches.sh`): all 9 batches passed the
pipeline and loaded with `SUCCESS`, 0 reconciliation difference, 10 sellers with exactly two versions, and row counts
equal to the local warehouse (112,600 items, 99,418 orders, 99,201 reviews, 3,106 seller versions). The app runs
against RDS as `app_reader`.

## Why the load runs from the laptop

Running it inside AWS needs Glue (or Lambda) inside the VPC with a JDBC connection, VPC endpoints for S3 and security-group rules. That is a lot of setup with little to show in a demo. Future work: a Glue Python shell job in the VPC, started by Step Functions after `NotifySuccess`.

## Cost

About $0.03 per hour while running. The instance is stopped when not in use (`aws rds stop-db-instance --db-instance-identifier olist-warehouse`; AWS starts it again after 7 days) and deleted at the end of the project.
