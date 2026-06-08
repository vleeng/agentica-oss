# Agentica

Plataforma multi-tenant para disenar, construir, probar, desplegar y observar agentes IA con tools, conocimiento y ejecucion monitoreada.

## Estado del proyecto

La documentacion historica del baseline de mayo 2026 sigue disponible, pero ya no describe por completo el estado actual. La referencia vigente para junio 2026 es este paquete documental:

- [Arquitectura actual 2026-06-06](docs/arquitectura-actual-2026-06-06.md)
- [Funcional de modulos 2026-06-06](docs/funcional-modulos-2026-06-06.md)
- [Runtime y observabilidad 2026-06-06](docs/runtime-observabilidad-2026-06-06.md)
- [Conocimiento y RAG 2026-06-06](docs/conocimiento-rag-2026-06-06.md)
- [Version actual 2026-06-06](docs/version-actual-2026-06-06.md)
- [Plan de separacion Platform / SaaS / OSS 2026-06-06](docs/plan-separacion-platform-saas-oss-2026-06-06.md)
- [Matriz de implementacion del product profile 2026-06-06](docs/matriz-implementacion-product-profile-2026-06-06.md)
- [Guia del fork OSS publico](docs/oss-fork-guide.md)
- [OSS bootstrap checklist](docs/oss-bootstrap-checklist.md)

## Fork OSS publico

La rama publica para la UNICABA, Universidad de la Ciudad de Buenos Aires, se prepara como un fork separado y debe arrancar con:

- `PRODUCT_PROFILE=oss`
- tema comunitario sobrio
- sin billing ni planes comerciales
- Moodle habilitado solo en esta linea

Para la publicacion inicial del fork, leer:

- [OSS bootstrap checklist](docs/oss-bootstrap-checklist.md)
- [Guia del fork OSS publico](docs/oss-fork-guide.md)
- [Paquete de publicacion OSS](docs/oss-publication-package.md)
- [Borrador de README publico OSS](docs/oss-public-readme-draft.md)
- [CONTRIBUTING](CONTRIBUTING.md)
- [SECURITY](SECURITY.md)
- [LICENSE](LICENSE)

## Que es Agentica hoy

Agentica ya soporta de forma operativa:

- wizard clasico y wizard asistido por chat,
- agentes simples `direct` y `react`,
- equipos tipo `crew`,
- knowledge bases `global` y `restricted`,
- skills, MCP y tools,
- editor de flujo,
- monitor del agente,
- monitor de ejecuciones con timeline,
- deploy por branch, tag o commit.

## Stack

- Backend: Python 3.11 + FastAPI + LangChain + CrewAI
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS
- Persistencia: PostgreSQL + Redis + Qdrant
- Infra: Docker Compose

## Mapa de lectura sugerido

### Si sos funcional o producto

Empeza por:

- [Funcional de modulos 2026-06-06](docs/funcional-modulos-2026-06-06.md)
- [Version actual 2026-06-06](docs/version-actual-2026-06-06.md)

### Si sos tecnico

Empeza por:

- [Arquitectura actual 2026-06-06](docs/arquitectura-actual-2026-06-06.md)
- [Runtime y observabilidad 2026-06-06](docs/runtime-observabilidad-2026-06-06.md)
- [Conocimiento y RAG 2026-06-06](docs/conocimiento-rag-2026-06-06.md)

### Si vas a operar deploys

Lee:

- [Operacion de ramas y deploy](docs/operacion-ramas-deploy.md)

## Documentacion historica y complementaria

- [Baseline funcional 2026-05-14](docs/version-agentica-2026-05-14.md)
- [Implementar baseline 2026-05-14 en otro server](docs/implementar-version-2026-05-14.md)
- [Manual de usuario](docs/manual-usuario-agentica.md)
- [Matriz de operatividad de tools](docs/matriz-operatividad-tools.md)
- [Plan de desarrollo de tools](docs/plan-desarrollo-tools.md)

## Arranque rapido en desarrollo

```bash
cp .env.example .env
cp .env backend/.env

docker compose up -d postgres redis qdrant

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd frontend
npm install
npm run dev
```

## Deploy

```bash
cd /opt/agentica
bash infra/scripts/deploy.sh --ref codex-wizard-ai-advisor
curl -s https://axenova.com/agentica/api/health/version
```

Para detalle completo de ramas, rollback y promocion:

- [Operacion de ramas y deploy](docs/operacion-ramas-deploy.md)

## Estructura resumida

```text
backend/app/
  api/v1/endpoints/
  builders/
  components/
  core/
  db/
  runtime/
  schemas/
  services/

frontend/src/
  components/auth/
  components/builder/
  components/monitor/
  components/wizard/
  lib/
  types/

docs/
infra/
widget/
```

## Siguiente gran evolucion

La proxima evolucion estructural prevista del producto es la incorporacion de agentes proactivos como segunda entidad, apoyados en la capa de observabilidad ya existente.
