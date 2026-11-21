#!/usr/bin/env bash
# Push batches through the AWS pipeline in order (upload -> Lambda -> Step Functions) and load each into RDS.
# Batches run one at a time: SCD2 needs them in date order, and the Glue job runs one job at a time.
# Usage: set -a; . ./.env; set +a; bash tools/run_all_batches.sh [batch_id ...]    (default: all local batches)
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_DEFAULT_REGION=${AWS_REGION:-ap-southeast-2}
PY=${PYTHON:-.venv/bin/python}
SFN="arn:aws:states:$AWS_DEFAULT_REGION:$(aws sts get-caller-identity --query Account --output text):stateMachine:olist-batch-pipeline"
batches=("$@")
[ ${#batches[@]} -gt 0 ] || mapfile -t batches < <(ls data/batches | sed 's/batch_id=//' | sort)

for b in "${batches[@]}"; do
  since=$(date +%s)
  bash tools/upload_batch.sh "$b"
  ex=None
  for _ in $(seq 36); do  # wait for the execution the Lambda starts (named <batch>-<epoch>)
    ex=$(aws stepfunctions list-executions --state-machine-arn "$SFN" --max-items 20 \
         --query "executions[?starts_with(name, '$b-')]|[0].executionArn" --output text | head -1)
    [ "$ex" != None ] && [ "${ex##*-}" -ge "$since" ] && break
    ex=None; sleep 5
  done
  [ "$ex" != None ] || { echo "$b: no pipeline execution started"; exit 1; }
  while st=$(aws stepfunctions describe-execution --execution-arn "$ex" --query status --output text); [ "$st" = RUNNING ]; do
    sleep 15
  done
  echo "$b: pipeline $st"
  [ "$st" = SUCCEEDED ] || exit 1
  $PY -m loader.curated_to_warehouse --batch "$b" --target rds
done
