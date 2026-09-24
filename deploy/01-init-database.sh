#!/usr/bin/env bash
set -euo pipefail
# Executado somente na inicialização de um volume PostgreSQL NOVO.
# A aplicação não utiliza a conta superusuária do cluster.
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$NEXO_DB_PASSWORD" <<'SQL'
CREATE ROLE nexo LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
GRANT CONNECT ON DATABASE nexo TO nexo;
ALTER SCHEMA public OWNER TO nexo;
GRANT USAGE, CREATE ON SCHEMA public TO nexo;
SQL
