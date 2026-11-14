"""Run SQL in Athena (workgroup `olist`) and print results with bytes scanned.

Usage: python -m tools.athena_query sql/athena/curated_tables.sql
       python -m tools.athena_query "SELECT count(*) FROM olist_lake.order_items WHERE batch_id='2018-01'"
${BUCKET} in the SQL is replaced with $S3_BUCKET; statements are split on ';'.
"""
import os
import sys
import time
from pathlib import Path

import boto3
from dotenv import load_dotenv


def run(athena, sql: str) -> None:
    qid = athena.start_query_execution(QueryString=sql, WorkGroup="olist")["QueryExecutionId"]
    while True:
        q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = q["Status"]["State"]
        if state not in ("QUEUED", "RUNNING"):
            break
        time.sleep(1)
    print(f"-- {sql.splitlines()[0][:80]} ... {state}, scanned {q['Statistics'].get('DataScannedInBytes', 0):,} bytes")
    if state != "SUCCEEDED":
        raise SystemExit(q["Status"].get("StateChangeReason"))
    if q.get("StatementType") == "DML":
        for row in athena.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"]:
            print(" | ".join(c.get("VarCharValue", "") for c in row["Data"]))


def main() -> None:
    load_dotenv()
    arg = sys.argv[1]
    text = Path(arg).read_text() if arg.endswith(".sql") else arg
    text = text.replace("${BUCKET}", os.environ["S3_BUCKET"])
    athena = boto3.client("athena")
    for chunk in text.split(";"):
        sql = "\n".join(line for line in chunk.splitlines() if not line.strip().startswith("--")).strip()
        if sql:
            run(athena, sql)


if __name__ == "__main__":
    main()
