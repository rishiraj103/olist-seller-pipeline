"""Lambda: a manifest.json lands in landing/batch_id=X/ -> check every listed file's MD5 -> copy batch to raw/
-> start the Step Functions pipeline for the batch.

Trigger: S3 ObjectCreated on prefix landing/, suffix manifest.json. A bad manifest raises and nothing is copied.
"""
import hashlib
import json
import logging
import os
import posixpath
import re
import time
from urllib.parse import unquote_plus

log = logging.getLogger()
log.setLevel(logging.INFO)

BATCH_ID = re.compile(r"^\d{4}-\d{2}$")


def check_manifest(manifest: dict, md5_of) -> list[str]:
    """Return a list of problems; empty means OK. md5_of(name) returns the file's MD5 hex, or None if missing."""
    problems = []
    if not BATCH_ID.match(str(manifest.get("batch_id", ""))):
        problems.append(f"bad batch_id: {manifest.get('batch_id')!r}")
    files = manifest.get("files") or []
    if not files:
        problems.append("no files listed")
    for f in files:
        actual = md5_of(f["name"])
        if actual is None:
            problems.append(f"missing file: {f['name']}")
        elif actual != f["md5"]:
            problems.append(f"md5 mismatch: {f['name']}")
    return problems


def s3_md5(s3, bucket: str, key: str):
    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"]
    except s3.exceptions.ClientError:  # NoSuchKey, or AccessDenied for a missing key without ListBucket
        return None
    digest = hashlib.md5()
    for chunk in iter(lambda: body.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


def handler(event, context):
    import boto3
    s3 = boto3.client("s3")
    record = event["Records"][0]["s3"]
    bucket, key = record["bucket"]["name"], unquote_plus(record["object"]["key"])
    folder = posixpath.dirname(key)
    manifest = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())

    problems = check_manifest(manifest, lambda name: s3_md5(s3, bucket, f"{folder}/{name}"))
    if problems:
        log.error("manifest FAILED %s: %s", key, problems)
        raise ValueError(f"bad manifest {key}: {problems}")

    batch_id = manifest["batch_id"]
    for name in [f["name"] for f in manifest["files"]] + ["manifest.json"]:
        s3.copy_object(Bucket=bucket, Key=f"raw/batch_id={batch_id}/{name}",
                       CopySource={"Bucket": bucket, "Key": f"{folder}/{name}"})
    log.info("manifest OK: batch %s, %d files copied to raw/", batch_id, len(manifest["files"]))

    execution = boto3.client("stepfunctions").start_execution(
        stateMachineArn=os.environ["STATE_MACHINE_ARN"], name=f"{batch_id}-{int(time.time())}",
        input=json.dumps({"batch_id": batch_id}))
    log.info("pipeline started: %s", execution["executionArn"])
    return {"batch_id": batch_id, "files": len(manifest["files"])}
