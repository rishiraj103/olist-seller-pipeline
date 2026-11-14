#!/usr/bin/env bash
# Create (or update) the Step 7 AWS lake: S3 bucket, IAM roles, ingest Lambda, Glue job, Athena workgroup.
# Rerun-safe. Usage: S3_BUCKET=olist-pipeline-<name> AWS_REGION=ap-southeast-2 bash infra/setup_aws.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${S3_BUCKET:?set S3_BUCKET}"
REGION=${AWS_REGION:-ap-southeast-2}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export AWS_DEFAULT_REGION=$REGION
TMP=$(mktemp -d)

policy() { sed "s/BUCKET/$S3_BUCKET/g; s/REGION/$REGION/g; s/ACCOUNT/$ACCOUNT/g" "infra/policies/$1.json"; }
trust() { echo "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"$1\"},\"Action\":\"sts:AssumeRole\"}]}"; }

echo "== S3 bucket $S3_BUCKET"
aws s3api head-bucket --bucket "$S3_BUCKET" >/dev/null 2>&1 ||
  aws s3api create-bucket --bucket "$S3_BUCKET" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
aws s3api put-public-access-block --bucket "$S3_BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$S3_BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-versioning --bucket "$S3_BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration --bucket "$S3_BUCKET" --lifecycle-configuration '{"Rules":[
  {"ID":"expire-landing","Status":"Enabled","Filter":{"Prefix":"landing/"},"Expiration":{"Days":30}},
  {"ID":"expire-old-versions","Status":"Enabled","Filter":{},"NoncurrentVersionExpiration":{"NoncurrentDays":7},
   "AbortIncompleteMultipartUpload":{"DaysAfterInitiation":7}}]}' >/dev/null
for prefix in landing raw curated rejected dq scripts athena-results; do
  aws s3api put-object --bucket "$S3_BUCKET" --key "$prefix/" >/dev/null
done

echo "== IAM roles"
for pair in glue-etl-role:glue.amazonaws.com:glue-etl lambda-ingest-role:lambda.amazonaws.com:lambda-ingest; do
  IFS=: read -r role service pol <<<"$pair"
  aws iam get-role --role-name "$role" >/dev/null 2>&1 ||
    aws iam create-role --role-name "$role" --assume-role-policy-document "$(trust "$service")" >/dev/null
  aws iam put-role-policy --role-name "$role" --policy-name "$pol" --policy-document "$(policy "$pol")"
done

echo "== Lambda on_batch_arrival"
(cd ingest && python3 -m zipfile -c "$TMP/lambda.zip" on_batch_arrival.py)
if aws lambda get-function --function-name on_batch_arrival >/dev/null 2>&1; then
  aws lambda update-function-code --function-name on_batch_arrival --zip-file "fileb://$TMP/lambda.zip" >/dev/null
else
  for try in 1 2 3 4 5 6; do  # a new IAM role takes a few seconds before Lambda can assume it
    aws lambda create-function --function-name on_batch_arrival --runtime python3.12 \
      --handler on_batch_arrival.handler --role "arn:aws:iam::$ACCOUNT:role/lambda-ingest-role" \
      --timeout 60 --memory-size 256 --zip-file "fileb://$TMP/lambda.zip" >/dev/null && break
    sleep 10
  done
  aws lambda wait function-active-v2 --function-name on_batch_arrival
  aws lambda add-permission --function-name on_batch_arrival --statement-id s3-landing \
    --action lambda:InvokeFunction --principal s3.amazonaws.com \
    --source-arn "arn:aws:s3:::$S3_BUCKET" --source-account "$ACCOUNT" >/dev/null
fi
aws s3api put-bucket-notification-configuration --bucket "$S3_BUCKET" --notification-configuration "{
  \"LambdaFunctionConfigurations\":[{\"LambdaFunctionArn\":\"arn:aws:lambda:$REGION:$ACCOUNT:function:on_batch_arrival\",
  \"Events\":[\"s3:ObjectCreated:*\"],\"Filter\":{\"Key\":{\"FilterRules\":[
  {\"Name\":\"prefix\",\"Value\":\"landing/\"},{\"Name\":\"suffix\",\"Value\":\"manifest.json\"}]}}}]}"

echo "== Glue job raw_to_curated"
aws s3 cp transform/raw_to_curated.py "s3://$S3_BUCKET/scripts/raw_to_curated.py" --quiet
aws s3 cp transform/rules.py "s3://$S3_BUCKET/scripts/rules.py" --quiet
JOB="{\"Role\":\"arn:aws:iam::$ACCOUNT:role/glue-etl-role\",
  \"Command\":{\"Name\":\"glueetl\",\"PythonVersion\":\"3\",\"ScriptLocation\":\"s3://$S3_BUCKET/scripts/raw_to_curated.py\"},
  \"DefaultArguments\":{\"--extra-py-files\":\"s3://$S3_BUCKET/scripts/rules.py\",\"--output\":\"s3://$S3_BUCKET\",
                       \"--job-language\":\"python\"},
  \"GlueVersion\":\"5.0\",\"WorkerType\":\"G.1X\",\"NumberOfWorkers\":2,\"Timeout\":15,\"MaxRetries\":0}"
if aws glue get-job --job-name raw_to_curated >/dev/null 2>&1; then
  aws glue update-job --job-name raw_to_curated --job-update "$JOB" >/dev/null
else
  aws glue create-job --name raw_to_curated --cli-input-json "$JOB" >/dev/null
fi

echo "== Athena workgroup olist"
aws athena get-work-group --work-group olist >/dev/null 2>&1 ||
  aws athena create-work-group --name olist --configuration "{
    \"ResultConfiguration\":{\"OutputLocation\":\"s3://$S3_BUCKET/athena-results/\"},
    \"EnforceWorkGroupConfiguration\":true,\"PublishCloudWatchMetricsEnabled\":false,
    \"BytesScannedCutoffPerQuery\":104857600}"

rm -rf "$TMP"
echo "done"
