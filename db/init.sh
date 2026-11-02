#!/bin/sh
set -eu
# psql variables quote credentials as SQL literals; no string-built SQL passwords.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v reader="$READER_USER" -v reader_password="$READER_PASSWORD" <<'SQL'
CREATE ROLE :"reader" LOGIN PASSWORD :'reader_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'reader') \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"reader";
ALTER ROLE :"reader" SET default_transaction_read_only = on;
ALTER ROLE :"reader" SET statement_timeout = '3s';
ALTER ROLE :"reader" SET temp_file_limit = '32MB';
ALTER ROLE :"reader" SET search_path = pg_catalog;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /seed/schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v reader="$READER_USER" <<'SQL'
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"reader";
SQL
