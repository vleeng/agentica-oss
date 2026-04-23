#!/bin/bash
# deploy.sh — Deploy de AGENTICA en VPS Axenova
# Compatible con el stack Docker+Traefik existente de Axenova
#
# Uso:
#   ./deploy.sh                    # deploy completo
#   ./deploy.sh --only backend     # solo backend
#   ./deploy.sh --only frontend    # solo frontend
#   ./deploy.sh --rollback         # rollback al tag anterior

set -euo pipefail

# ── Configuración ─────────────────────────────────────────────────────────────

DEPLOY_DIR="/opt/agentica"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.prod.yml"
ENV_FILE="$DEPLOY_DIR/.env"
BACKUP_DIR="/opt/agentica-backups"
LOG_FILE="/var/log/agentica-deploy.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

# ── Parseo de argumentos ──────────────────────────────────────────────────────

ONLY=""
ROLLBACK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --only)     ONLY="$2"; shift 2 ;;
        --rollback) ROLLBACK=true; shift ;;
        *)          err "Argumento desconocido: $1" ;;
    esac
done

# ── Funciones ─────────────────────────────────────────────────────────────────

check_requirements() {
    log "Verificando requisitos..."
    command -v docker    >/dev/null 2>&1 || err "Docker no instalado"
    command -v git       >/dev/null 2>&1 || err "Git no instalado"
    [[ -f "$ENV_FILE" ]]                 || err "Archivo .env no encontrado en $DEPLOY_DIR"
    [[ -f "$COMPOSE_FILE" ]]             || err "docker-compose.prod.yml no encontrado en $DEPLOY_DIR"

    # Verificar variables críticas
    source "$ENV_FILE"
    [[ -n "${ANTHROPIC_API_KEY:-}" || -n "${OPENROUTER_API_KEY:-}" || -n "${OPENAI_API_KEY:-}" || -n "${BUILDER_API_KEY:-}" ]] \
        || err "No hay ninguna API key LLM definida en .env (ANTHROPIC_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY o BUILDER_API_KEY)"
    [[ -n "${JWT_SECRET:-}" ]]        || err "JWT_SECRET no definida en .env"
    [[ -n "${POSTGRES_PASSWORD:-}" ]] || err "POSTGRES_PASSWORD no definida en .env"
    [[ -n "${REDIS_PASSWORD:-}" ]]    || err "REDIS_PASSWORD no definida en .env"
    [[ -n "${ADMIN_PASSWORD:-}" ]]    || err "ADMIN_PASSWORD no definida en .env"
    [[ -n "${ENCRYPTION_KEY:-}" ]]    || err "ENCRYPTION_KEY no definida en .env"
    log "Requisitos OK"
}

backup_database() {
    log "Haciendo backup de PostgreSQL..."
    mkdir -p "$BACKUP_DIR"
    source "$ENV_FILE"

    BACKUP_FILE="$BACKUP_DIR/agentica_${TIMESTAMP}.sql.gz"
    docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dumpall -U agentica 2>/dev/null \
        | gzip > "$BACKUP_FILE" \
        && log "Backup guardado: $BACKUP_FILE" \
        || warn "No se pudo hacer backup (¿primera vez?)"

    # Mantener solo los últimos 7 backups
    ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +8 | xargs rm -f || true
}

pull_latest() {
    log "Actualizando código..."
    cd "$DEPLOY_DIR"
    git fetch origin main
    git reset --hard origin/main
    log "Código actualizado a $(git rev-parse --short HEAD)"
}

build_images() {
    local service="${1:-}"
    log "Construyendo imágenes${service:+ ($service)}..."
    cd "$DEPLOY_DIR"

    if [[ -n "$service" ]]; then
        docker compose -f "$COMPOSE_FILE" build "$service"
    else
        docker compose -f "$COMPOSE_FILE" build --parallel
    fi
    log "Imágenes construidas"
}

run_migrations() {
    log "Ejecutando migraciones de base de datos..."
    docker compose -f "$COMPOSE_FILE" run --rm backend \
        python -c "
import asyncio
from app.db.session import engine, Base
async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migraciones aplicadas')
asyncio.run(migrate())
" && log "Migraciones OK" || warn "Error en migraciones (puede ser primera vez)"
}

deploy_services() {
    local service="${1:-}"
    log "Desplegando servicios${service:+ ($service)}..."
    cd "$DEPLOY_DIR"

    if [[ -n "$service" ]]; then
        docker compose -f "$COMPOSE_FILE" up -d --no-deps "$service"
    else
        docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
    fi
}

health_check() {
    log "Verificando health del backend..."
    local retries=15
    local wait=4

    for i in $(seq 1 $retries); do
        if docker compose -f "$COMPOSE_FILE" exec -T backend python - <<'PY' > /dev/null 2>&1
import json
import urllib.request

with urllib.request.urlopen("http://localhost:8000/health", timeout=3) as response:
    payload = json.loads(response.read().decode("utf-8"))
    raise SystemExit(0 if payload.get("status") == "ok" else 1)
PY
        then
            log "Backend healthy ✓"
            return 0
        fi
        echo -n "."
        sleep $wait
    done

    err "Backend no responde después de $((retries * wait))s"
}

rollback() {
    warn "Iniciando rollback..."
    cd "$DEPLOY_DIR"
    PREV_COMMIT=$(git log --oneline -2 | tail -1 | awk '{print $1}')
    git reset --hard "$PREV_COMMIT"
    build_images
    deploy_services
    health_check
    log "Rollback completado a $PREV_COMMIT"
}

show_status() {
    log "Estado del stack:"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    log "Logs recientes del backend:"
    docker compose -f "$COMPOSE_FILE" logs --tail=20 backend
}

# ── Main ──────────────────────────────────────────────────────────────────────

mkdir -p "$(dirname "$LOG_FILE")"
log "=== Deploy AGENTICA $TIMESTAMP ==="

if [[ "$ROLLBACK" == true ]]; then
    rollback
    exit 0
fi

check_requirements

if [[ -z "$ONLY" ]]; then
    # Deploy completo
    backup_database
    pull_latest
    build_images
    run_migrations
    deploy_services
    health_check
    show_status
    log "=== Deploy completado ✓ ==="
else
    # Deploy parcial
    pull_latest
    build_images "$ONLY"
    deploy_services "$ONLY"
    [[ "$ONLY" == "backend" ]] && health_check
    log "=== Deploy de $ONLY completado ✓ ==="
fi
