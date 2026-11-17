-- Least-privilege users (rerun-safe). Passwords come from psql variables, never from this file:
--   psql -v etl_pw=... -v app_pw=... -f sql/admin/users.sql
SELECT format('CREATE ROLE %I LOGIN', r) FROM unnest(ARRAY['etl_writer', 'app_reader']) r
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) \gexec
ALTER ROLE etl_writer PASSWORD :'etl_pw';
ALTER ROLE app_reader PASSWORD :'app_pw';

-- etl_writer: load staging, run the procedures, write dw and audit
GRANT CONNECT ON DATABASE olist TO etl_writer, app_reader;
GRANT USAGE ON SCHEMA staging, dw, audit TO etl_writer;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA staging, dw, audit TO etl_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dw, audit TO etl_writer;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA dw TO etl_writer;

-- app_reader: read only (analytics views for the app, dw/audit for drill-down); also objects created later
GRANT USAGE ON SCHEMA dw, audit, analytics TO app_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dw, audit, analytics TO app_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA dw, audit, analytics GRANT SELECT ON TABLES TO app_reader;

-- etl_writer also runs the analytics queries and checks
GRANT USAGE ON SCHEMA analytics TO etl_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO etl_writer;
