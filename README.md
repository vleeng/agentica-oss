# AGENTICA

Plataforma de construcción, prueba y despliegue automático de agentes IA.

## Stack

- **Backend**: Python 3.11 + FastAPI + LangChain + CrewAI
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **DB**: PostgreSQL 16 (schema por tenant) + Redis + Qdrant
- **Infra**: Docker Compose + Traefik

## Arranque rápido (desarrollo)

```bash
# 1. Clonar y configurar variables
cp .env.example .env
# Editar .env con ANTHROPIC_API_KEY y JWT_SECRET

# 2. Levantar infra
docker compose up -d postgres redis qdrant

# 3. Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Deploy en producción (VPS Axenova)

```bash
# Primera vez
bash infra/scripts/setup_vps.sh

# Deploys siguientes
bash infra/scripts/deploy.sh

# Solo backend
bash infra/scripts/deploy.sh --only backend

# Rollback
bash infra/scripts/deploy.sh --rollback
```

## Estructura del proyecto

```
agentica/
├── backend/app/
│   ├── api/v1/endpoints/     # FastAPI routers (agents, auth, keys, usage, knowledge...)
│   ├── core/                 # config, security (JWT), plan_limits, rate_limiter
│   ├── db/                   # session (multi-tenancy), repository
│   ├── schemas/              # Pydantic models (AgentSpec, AgentDesign, EvalReport...)
│   ├── services/             # selector, designer, evaluator, optimizer, deployer
│   ├── runtime/              # AgentRuntime (ABC) + LangChain + CrewAI + store (Redis)
│   ├── builders/             # LangChainBuilder, CrewAIBuilder + Jinja2 templates
│   ├── components/           # tools (5), memory adapters (3), RAG + knowledge_builder
│   ├── channels/             # WhatsApp (Twilio) + Telegram handlers
│   └── tasks/                # Celery: build_agent, eval_agent, deploy_agent
├── frontend/src/
│   ├── components/wizard/    # RequirementWizard (6 pasos) + StepCrew (modo equipo)
│   ├── components/monitor/   # AgentMonitor (sandbox+eval+optimize) + UsageDashboard
│   ├── components/builder/   # AgentDashboard + APIKeysPanel
│   ├── lib/api.ts            # Axios client + WebSocket helper
│   └── types/agent.ts        # TypeScript types del dominio
├── widget/src/
│   └── agentica-chat.ts      # Web Component autónomo (sin dependencias)
├── infra/
│   ├── postgres/init.sql     # Schema public + tablas globales
│   └── scripts/              # deploy.sh, setup_vps.sh, backup.sh
├── docker-compose.yml        # Stack de desarrollo
└── docker-compose.prod.yml   # Stack de producción (Traefik)
```

## API — endpoints principales

```
POST   /api/v1/auth/register              Registro + provisioning de tenant
POST   /api/v1/auth/login                 Login → JWT
GET    /api/v1/auth/me                    Usuario actual

POST   /api/v1/agents/spec                Crear agente desde spec (→ AgentDesign)
POST   /api/v1/agents/{id}/build          Construir runtime
POST   /api/v1/agents/{id}/invoke         Invocar agente (REST)
WS     /api/v1/agents/{id}/ws             WebSocket streaming (web chat)
POST   /api/v1/agents/{id}/eval           Evaluar con test cases
POST   /api/v1/agents/{id}/optimize       Optimizar según EvalReport
GET    /api/v1/agents/{id}/design         Ver diseño generado
GET    /api/v1/agents/{id}/history        Historial de conversación

POST   /api/v1/knowledge/{id}/ingest      Ingerir fuentes RAG
GET    /api/v1/knowledge/{id}/stats       Stats de la colección

GET    /api/v1/keys/                      Listar API keys
POST   /api/v1/keys/                      Crear API key
DELETE /api/v1/keys/{id}                  Revocar API key

GET    /api/v1/usage/summary              Plan + límites + uso
GET    /api/v1/usage/billing              Detalle de billing por día
GET    /api/v1/usage/agents               Uso por agente
GET    /api/v1/usage/rate-limits          Estado de rate limits

GET    /api/v1/tools/custom/              Listar custom tools del tenant
POST   /api/v1/tools/custom/              Crear custom tool (valida código)
GET    /api/v1/tools/custom/{id}          Detalle + source_code
PUT    /api/v1/tools/custom/{id}          Actualizar (revalida si cambia código)
DELETE /api/v1/tools/custom/{id}          Eliminar
POST   /api/v1/tools/custom/validate      Validar código sin guardar
POST   /api/v1/tools/custom/{id}/test     Ejecutar tool con input de prueba

GET    /api/v1/knowledge/{id}/sources     Listar fuentes indexadas en Qdrant
DELETE /api/v1/knowledge/{id}/source      Eliminar fuente específica
POST   /api/v1/knowledge/{id}/ingest/file Ingestar archivo (PDF/TXT) subido

GET    /api/v1/tenants/me/agents          Listar agentes del tenant
GET    /api/v1/tenants/me/billing         Resumen de billing
POST   /api/v1/tenants/register           Registrar tenant con usuario owner
POST   /api/v1/tenants/login              Login por tenant
```

## Sprints completados

| Sprint | Contenido |
|--------|-----------|
| 1 | Multi-tenancy (schema por tenant), JWT + RBAC, Requirement Wizard, Framework Selector, Design Generator |
| 2 | LangChain Builder, CrewAI Builder, RuntimeFactory, Memory Adapters (3), Tools built-in (5), Celery tasks |
| 3 | Deploy Engine (Docker+Traefik), WebSocket streaming, Web Chat Widget (Web Component), canales WhatsApp/Telegram |
| 4 | RAG Knowledge Builder (Qdrant), RAG Tool, Repository (persistencia DB), Eval Engine, Optimizer, Wizard modo crew |
| 5 | Auth real contra DB, API Keys (SHA-256, scopes), RuntimeStore en Redis, Dashboard frontend, observabilidad básica |
| 6 | Plan limits middleware, Rate limiter (sliding window Redis), Deploy scripts VPS, UsageDashboard, docker-compose.prod.yml |
