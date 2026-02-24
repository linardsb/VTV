#!/usr/bin/env bash
# Automated PostgreSQL backup with retention policy
# Usage: ./scripts/db-backup.sh [retention_days]
# Cron example: 0 2 * * * /path/to/vtv/scripts/db-backup.sh 90
#
# Environment variables (optional):
#   BACKUP_DIR    - Directory for backups (default: ./backups)
#   DB_CONTAINER  - Docker container name (default: vtv-db-1)
#   PG_USER       - PostgreSQL user (default: postgres)
#   PG_DB         - PostgreSQL database (default: vtv_db)
#
# NOTE: Backups are not encrypted at rest. For production deployments with PII,
# pipe through gpg or store on an encrypted volume. Accepted risk for local dev.

set -euo pipefail

RETENTION_DAYS="${1:-90}"
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
DB_CONTAINER="${DB_CONTAINER:-vtv-db-1}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-vtv_db}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/vtv_db_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting backup of ${PG_DB}..."

# Dump and compress
if ! docker exec "${DB_CONTAINER}" pg_dump -U "${PG_USER}" "${PG_DB}" | gzip > "${BACKUP_FILE}"; then
    echo "[$(date -Iseconds)] ERROR: Backup failed" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Verify backup is non-empty
BACKUP_SIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat --printf="%s" "${BACKUP_FILE}" 2>/dev/null)
if [ "${BACKUP_SIZE}" -lt 100 ]; then
    echo "[$(date -Iseconds)] ERROR: Backup file suspiciously small (${BACKUP_SIZE} bytes)" >&2
    exit 1
fi

echo "[$(date -Iseconds)] Backup created: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Prune old backups
PRUNED=0
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    while IFS= read -r old_backup; do
        rm -f "${old_backup}"
        PRUNED=$((PRUNED + 1))
    done < <(find "${BACKUP_DIR}" -name "vtv_db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -type f 2>/dev/null)
fi

if [ "${PRUNED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] Pruned ${PRUNED} backups older than ${RETENTION_DAYS} days"
fi

# Summary
TOTAL=$(find "${BACKUP_DIR}" -name "vtv_db_*.sql.gz" -type f | wc -l | tr -d ' ')
echo "[$(date -Iseconds)] Backup complete. ${TOTAL} backups in ${BACKUP_DIR}"
