#!/bin/bash
# backup.sh — Backup diario de AGENTICA (PostgreSQL + Qdrant snapshots)
# Ejecutado por cron: 0 3 * * * /opt/agentica/infra/scripts/backup.sh

set -euo pipefail

DEPLOY_DIR="/opt/agentica"
BACKUP_DIR="/opt/agentica-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

source "$DEPLOY_DIR/.env" 2>/dev/null || true

mkdir -p "$BACKUP_DIR"
echo "[$(date)] Iniciando backup..."

# PostgreSQL
PG_FILE="$BACKUP_DIR/pg_${TIMESTAMP}.sql.gz"
docker exec agentica-postgres pg_dumpall -U agentica 2>/dev/null \
    | gzip > "$PG_FILE" \
    && echo "PostgreSQL: $PG_FILE ($(du -sh $PG_FILE | cut -f1))" \
    || echo "WARN: Error en backup PostgreSQL"

# Qdrant snapshot
QDRANT_FILE="$BACKUP_DIR/qdrant_${TIMESTAMP}.tar.gz"
docker run --rm \
    --volumes-from agentica-qdrant-1 \
    -v "$BACKUP_DIR:/backup" \
    alpine tar czf "/backup/qdrant_${TIMESTAMP}.tar.gz" /qdrant/storage \
    && echo "Qdrant: $QDRANT_FILE" \
    || echo "WARN: Error en backup Qdrant"

# Limpiar backups viejos
find "$BACKUP_DIR" -name "*.gz" -mtime +$KEEP_DAYS -delete
echo "Backups viejos eliminados (>$KEEP_DAYS días)"

echo "[$(date)] Backup completado"
