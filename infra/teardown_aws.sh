#!/usr/bin/env bash
# Delete every AWS resource this project created (irreversible: all lake data, the RDS warehouse, logs).
# Usage: set -a; . ./.env; set +a; CONFIRM=delete bash infra/teardown_aws.sh
set -uo pipefail
[ "${CONFIRM:-}" = delete ] || { echo "refusing: set CONFIRM=delete to delete all project resources"; exit 1; }
: "${S3_BUCKET:?set S3_BUCKET}"
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}
export AWS_DEFAULT_REGION=${AWS_REGION:-ap-southeast-2}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
q() { "$@" >/dev/null 2>&1 && echo "  deleted: ${*:2:2}" || echo "  (not found or already gone: ${*:2:2})"; }

echo "== RDS (deletion runs in the background)"
q aws rds delete-db-instance --db-instance-identifier olist-warehouse --skip-final-snapshot --delete-automated-backups

echo "== pipeline"
q aws stepfunctions delete-state-machine --state-machine-arn "arn:aws:states:$AWS_DEFAULT_REGION:$ACCOUNT:stateMachine:olist-batch-pipeline"
for fn in on_batch_arrival check_dq; do q aws lambda delete-function --function-name "$fn"; done
q aws sns delete-topic --topic-arn "arn:aws:sns:$AWS_DEFAULT_REGION:$ACCOUNT:olist-pipeline-alerts"
q aws glue delete-job --job-name raw_to_curated

echo "== Athena"
aws athena start-query-execution --work-group olist --query-string "DROP DATABASE IF EXISTS olist_lake CASCADE" >/dev/null 2>&1 && sleep 5
q aws glue delete-database --name olist_lake
q aws athena delete-work-group --work-group olist --recursive-delete-option

echo "== S3 bucket $S3_BUCKET (all versions)"
$PY - "$S3_BUCKET" <<'PY'
import sys, boto3
bucket = boto3.resource("s3").Bucket(sys.argv[1])
try:
    bucket.object_versions.delete()
    bucket.delete()
    print("  deleted bucket")
except Exception as e:
    print("  bucket:", e)
PY

echo "== IAM roles"
for role in glue-etl-role lambda-ingest-role lambda-dq-role sfn-pipeline-role; do
  for pol in $(aws iam list-role-policies --role-name "$role" --query PolicyNames --output text 2>/dev/null); do
    aws iam delete-role-policy --role-name "$role" --policy-name "$pol"
  done
  q aws iam delete-role --role-name "$role"
done

echo "== CloudWatch log groups"
for lg in $(aws logs describe-log-groups --query "logGroups[?starts_with(logGroupName, '/aws/lambda/on_batch_arrival') || starts_with(logGroupName, '/aws/lambda/check_dq') || starts_with(logGroupName, '/aws-glue/')].logGroupName" --output text); do
  q aws logs delete-log-group --log-group-name "$lg"
done

echo "== security group (after RDS is gone, up to ~10 min)"
aws rds wait db-instance-deleted --db-instance-identifier olist-warehouse 2>/dev/null
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=olist-rds-sg --query "SecurityGroups[0].GroupId" --output text)
[ "$SG" != None ] && q aws ec2 delete-security-group --group-id "$SG"
echo "done"
