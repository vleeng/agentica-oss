#!/bin/bash
# setup_vps.sh — Primera instalación de AGENTICA en el VPS Axenova
# Ejecutar como root o con sudo desde el VPS
#
# Uso:
#   curl -sSL https://raw.github.com/.../setup_vps.sh | bash
#   o
#   chmod +x setup_vps.sh && ./setup_vps.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}[SETUP]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

DEPLOY_DIR="/opt/agentica"
REPO_URL="${REPO_URL:-https://github.com/vleeng/agentica.git}"

log "=== Setup inicial AGENTICA en VPS Axenova ==="

# ── 1. Dependencias del sistema ───────────────────────────────────────────────

log "Instalando dependencias del sistema..."
apt-get update -qq
apt-get install -y -qq git curl unzip openssl python3

# ── 2. Docker (si no está instalado) ─────────────────────────────────────────

if ! command -v docker &> /dev/null; then
    log "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    log "Docker ya instalado: $(docker --version)"
fi

# ── 3. Clonar/actualizar repositorio ─────────────────────────────────────────

if [[ -d "$DEPLOY_DIR/.git" ]]; then
    log "Actualizando repositorio existente..."
    cd "$DEPLOY_DIR"
    git pull origin main
else
    log "Clonando repositorio..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
fi

# ── 4. Crear .env si no existe ────────────────────────────────────────────────

if [[ ! -f "$DEPLOY_DIR/.env" ]]; then
    log "Creando .env desde template..."
    cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"

    # Generar JWT_SECRET aleatorio
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" "$DEPLOY_DIR/.env"

    # Generar POSTGRES_PASSWORD aleatorio
    PG_PASS=$(openssl rand -hex 16)
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$PG_PASS/" "$DEPLOY_DIR/.env"

    # Generar REDIS_PASSWORD aleatorio
    REDIS_PASS=$(openssl rand -hex 16)
    sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASS/" "$DEPLOY_DIR/.env"

    # Generar ENCRYPTION_KEY compatible con Fernet sin depender de paquetes externos.
    ENC_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    sed -i "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENC_KEY/" "$DEPLOY_DIR/.env"

    sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=production|" "$DEPLOY_DIR/.env"
    sed -i "s|BASE_DOMAIN=.*|BASE_DOMAIN=axenova.com|" "$DEPLOY_DIR/.env"
    sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS='[\"https://axenova.com\"]'|" "$DEPLOY_DIR/.env"
    sed -i "s|VITE_API_URL=.*|VITE_API_URL=/agentica|" "$DEPLOY_DIR/.env"
    sed -i "s|VITE_WS_URL=.*|VITE_WS_URL=wss://axenova.com/agentica|" "$DEPLOY_DIR/.env"

    warn "=== IMPORTANTE: editá $DEPLOY_DIR/.env y completá: ==="
    warn "  - ANTHROPIC_API_KEY"
    warn "  - ADMIN_PASSWORD"
    warn "  - BASE_DOMAIN (ej: axenova.com)"
    warn "  - CORS_ORIGINS (ej: '[\"https://axenova.com\"]')"
    warn "  - VITE_WS_URL si el frontend no vive en https://axenova.com/agentica"
    warn "  - Opcionales: TWILIO_*, TELEGRAM_BOT_TOKEN, OPENAI_API_KEY"
    warn ""
    warn "⚠️  Verifica que definiste ADMIN_PASSWORD de lo contrario la aplicacion crasheara preventivamente."
    warn "Luego ejecutá: cd $DEPLOY_DIR && bash infra/scripts/deploy.sh"
else
    log ".env ya existe — no se modifica"
fi

# ── 5. Verificar red Traefik ──────────────────────────────────────────────────

if ! docker network ls | grep -q traefik_public; then
    warn "Red 'traefik_public' no encontrada."
    warn "Si Traefik usa otra red, editá docker-compose.prod.yml."
    warn "Para crear la red: docker network create traefik_public"
fi

# ── 6. Permisos ───────────────────────────────────────────────────────────────

chmod +x "$DEPLOY_DIR/infra/scripts/deploy.sh"
chmod +x "$DEPLOY_DIR/infra/scripts/backup.sh" 2>/dev/null || true

# ── 7. Cron para backups diarios ──────────────────────────────────────────────

CRON_JOB="0 3 * * * $DEPLOY_DIR/infra/scripts/backup.sh >> /var/log/agentica-backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "agentica"; echo "$CRON_JOB") | crontab -
log "Cron de backup configurado (3:00 AM diario)"

log ""
log "=== Setup completado ==="
log "Próximos pasos:"
log "  1. Editá $DEPLOY_DIR/.env con tus credenciales"
log "  2. cd $DEPLOY_DIR && bash infra/scripts/deploy.sh"
log "  3. Accedé a https://www.axenova.com/agentica"
