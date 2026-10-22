#!/bin/bash
set -euo pipefail
umask 077
MARIADB_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump --user=root   --single-transaction --quick --skip-lock-tables "$MARIADB_DATABASE"   > /backups/slurm.sql.tmp
mv /backups/slurm.sql.tmp /backups/slurm.sql
