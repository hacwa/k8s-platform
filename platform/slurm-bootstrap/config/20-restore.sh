#!/bin/bash
# Sourced by the official MariaDB entrypoint only for a new datadir.
if [ -s /backups/slurm.sql ]; then
  echo "Restoring Slurm accounting from its logical backup"
  docker_process_sql --database="$MARIADB_DATABASE" < /backups/slurm.sql
fi
