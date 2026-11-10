"""Load one curated batch into PostgreSQL: refill staging.*, record DQ results, CALL dw.run_batch.

Usage: python -m loader.curated_to_warehouse --batch 2018-03 [--lake data/lake]
"""
import argparse
import io
import json
import logging
import os

import psycopg2
import pyarrow.parquet as pq
from dotenv import load_dotenv

log = logging.getLogger("loader")

TABLES = ["orders", "order_items", "order_reviews", "customers", "sellers", "products"]


def connect():
    return psycopg2.connect(host=os.getenv("PG_HOST", "localhost"), port=os.getenv("PG_PORT", "5432"),
                            dbname=os.getenv("PG_DB", "olist"), user=os.getenv("PG_USER", "postgres"),
                            password=os.getenv("PG_PASSWORD"))


def read_text(path: str) -> str:
    if path.startswith("s3://"):
        import boto3
        bucket, key = path[5:].split("/", 1)
        return boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read().decode()
    with open(path) as f:
        return f.read()


def load_staging(cur, lake: str, batch: str) -> None:
    for table in TABLES:
        df = pq.read_table(f"{lake}/curated/{table}/batch_id={batch}").to_pandas()
        df = df.convert_dtypes()  # nullable ints stay ints (no "1.0"); NULL is written as an empty field
        df["batch_id"] = batch
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False)
        buf.seek(0)
        cur.execute(f"TRUNCATE staging.{table}")
        cur.copy_expert(f"COPY staging.{table} ({', '.join(df.columns)}) FROM STDIN WITH (FORMAT csv)", buf)
        log.info("staging.%s: %d rows", table, len(df))


def load_dq(cur, lake: str, batch: str) -> None:
    summary = json.loads(read_text(f"{lake}/dq/batch_id={batch}/dq_summary.json"))
    rows = [(batch, table, rule, t["read"], failed)
            for table, t in summary["tables"].items()
            for rule, failed in {"total": t["rejected"], **t["by_rule"]}.items()]
    cur.execute("DELETE FROM audit.dq_results WHERE batch_id = %s", (batch,))
    cur.executemany("INSERT INTO audit.dq_results VALUES (%s, %s, %s, %s, %s)", rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--lake", default="data/lake")
    args = ap.parse_args()

    conn = connect()
    try:
        with conn, conn.cursor() as cur:  # one transaction for staging + DQ results
            load_staging(cur, args.lake, args.batch)
            load_dq(cur, args.lake, args.batch)
        conn.autocommit = True  # run_batch commits its own log rows
        with conn.cursor() as cur:
            cur.execute("CALL dw.run_batch(%s)", (args.batch,))
            cur.execute("SELECT status, message FROM audit.batch_log WHERE batch_id = %s ORDER BY run_id DESC LIMIT 1",
                        (args.batch,))
            status, message = cur.fetchone()
        log.info("batch %s: %s (%s)", args.batch, status, message)
        if status != "SUCCESS":
            raise SystemExit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
