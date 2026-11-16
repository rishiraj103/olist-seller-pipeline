#!/usr/bin/env bash
# Create the RDS PostgreSQL warehouse (rerun-safe): security group open on 5432 to this machine's IP only.
# Usage: set -a; . ./.env; set +a; bash infra/setup_rds.sh
set -euo pipefail
: "${RDS_ADMIN_PASSWORD:?set RDS_ADMIN_PASSWORD}"
export AWS_DEFAULT_REGION=${AWS_REGION:-ap-southeast-2}
DB=olist-warehouse
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)
MY_IP=$(curl -s https://checkip.amazonaws.com)

SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=olist-rds-sg Name=vpc-id,Values="$VPC" \
     --query "SecurityGroups[0].GroupId" --output text)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name olist-rds-sg --description "Postgres from developer IP" \
       --vpc-id "$VPC" --query GroupId --output text)
fi
aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 5432 --cidr "$MY_IP/32" \
  >/dev/null 2>&1 || echo "ingress for $MY_IP already present"

if ! aws rds describe-db-instances --db-instance-identifier "$DB" >/dev/null 2>&1; then
  aws rds create-db-instance --db-instance-identifier "$DB" --engine postgres --engine-version 16.15 \
    --db-instance-class db.t4g.micro --allocated-storage 20 --storage-type gp2 --storage-encrypted \
    --master-username "${RDS_ADMIN_USER:-olist_admin}" --master-user-password "$RDS_ADMIN_PASSWORD" --db-name olist \
    --vpc-security-group-ids "$SG" --publicly-accessible --no-multi-az --backup-retention-period 1 \
    --no-enable-performance-insights --monitoring-interval 0 --no-deletion-protection >/dev/null
fi
aws rds wait db-instance-available --db-instance-identifier "$DB"
aws rds describe-db-instances --db-instance-identifier "$DB" --query "DBInstances[0].Endpoint.Address" --output text
