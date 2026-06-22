#!/bin/sh
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<-EOSQL
CREATE DATABASE IF NOT EXISTS document_service_db;
CREATE DATABASE IF NOT EXISTS template_service_db;

GRANT ALL PRIVILEGES ON document_service_db.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON template_service_db.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
EOSQL
