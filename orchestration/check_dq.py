"""Lambda check_dq: read the batch's dq_summary.json and return its reject rate (the state machine decides pass/fail)."""
import json
import os

import boto3


def handler(event, context):
    key = f"dq/batch_id={event['batch_id']}/dq_summary.json"
    summary = json.loads(boto3.client("s3").get_object(Bucket=os.environ["S3_BUCKET"], Key=key)["Body"].read())
    return {k: summary[k] for k in ("batch_id", "rows_read", "rows_rejected", "reject_rate")}
