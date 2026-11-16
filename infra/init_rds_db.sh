#!/usr/bin/env bash
# Apply all DDL, procedures and users to RDS (rerun-safe). Uses psql from the local olist-pg container.
# Usage: set -a; . ./.env; set +a; bash infra/init_rds_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RDS_HOST:?set RDS_HOST}" "${RDS_ADMIN_PASSWORD:?}" "${RDS_PASSWORD:?}" "${APP_READER_PASSWORD:?}"
psql_rds() {
  docker exec -i -e PGPASSWORD="$RDS_ADMIN_PASSWORD" -e PGSSLMODE=require -e PGOPTIONS="-c client_min_messages=warning" olist-pg \
    psql -h "$RDS_HOST" -U "${RDS_ADMIN_USER:-olist_admin}" -d olist -v ON_ERROR_STOP=1 -q "$@"
}
cat sql/ddl/*.sql sql/procedures/*.sql | psql_rds
psql_rds -v etl_pw="$RDS_PASSWORD" -v app_pw="$APP_READER_PASSWORD" < sql/admin/users.sql
psql_rds -c "SELECT count(*) AS dim_date_rows FROM dw.dim_date"
