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
# NOTE: Set ENCRYPT_BACKUPS=true and GPG_PASSPHRASE_FILE for encrypted backups.
# Without encryption, backups are stored in plaintext. Accepted risk for local dev.

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

# Optional encryption for production deployments with PII
if [ "${ENCRYPT_BACKUPS:-false}" = "true" ]; then
    if [ -z "${GPG_PASSPHRASE_FILE:-}" ]; then
        echo "[$(date -Iseconds)] ERROR: ENCRYPT_BACKUPS=true but GPG_PASSPHRASE_FILE not set" >&2
        exit 1
    fi
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "${GPG_PASSPHRASE_FILE}" \
        "${BACKUP_FILE}"
    rm -f "${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE}.gpg"
    echo "[$(date -Iseconds)] Backup encrypted with AES-256"
fi

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
