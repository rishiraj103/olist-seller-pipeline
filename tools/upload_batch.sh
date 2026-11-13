#!/usr/bin/env bash
# Upload one local batch to s3://$S3_BUCKET/landing/. The manifest goes last: its arrival triggers the ingest Lambda.
# Usage: S3_BUCKET=... bash tools/upload_batch.sh 2018-01
set -euo pipefail
: "${S3_BUCKET:?set S3_BUCKET}"
src="data/batches/batch_id=$1"
dst="s3://$S3_BUCKET/landing/batch_id=$1"
aws s3 cp "$src" "$dst" --recursive --exclude manifest.json --quiet
aws s3 cp "$src/manifest.json" "$dst/manifest.json" --quiet
echo "uploaded $src -> $dst"
