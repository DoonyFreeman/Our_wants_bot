#!/usr/bin/env bash
# Бэкап SQLite-базы our-wants-bot. Запускается по cron.
set -euo pipefail

PROJECT_DIR="/root/Projects/Our_wants_bot"
DB="${PROJECT_DIR}/wants.db"
BACKUP_DIR="/root/backups"

mkdir -p "${BACKUP_DIR}"

if [[ -f "${DB}" ]]; then
    # Консистентная копия через SQLite .backup (на случай записи во время копирования)
    STAMP="$(date +%Y-%m-%d_%H%M)"
    sqlite3 "${DB}" ".backup '${BACKUP_DIR}/wants_${STAMP}.db'"
    # Чистим бэкапы старше 14 дней
    find "${BACKUP_DIR}" -name 'wants_*.db' -mtime +14 -delete
fi
