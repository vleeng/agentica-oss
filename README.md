# Agentica OSS

Agentica OSS es una plataforma open source para crear, configurar, ejecutar y monitorear agentes de IA en instalaciones propias. Esta linea publica esta pensada para cualquier organizacion o comunidad que quiera desplegar su propia base operativa.

## Que incluye

- wizard clasico
- wizard asistido por chat
- agentes `direct`, `react` y `crew`
- knowledge bases y RAG
- skills, tools y MCP
- editor de flujo
- monitor del agente
- monitor de ejecuciones
- observabilidad de uso por agente
- integracion Moodle para la linea OSS

## Que no incluye

- billing
- planes comerciales
- limites de plan
- onboarding SaaS
- branding premium de Vleeng

## Requisitos

- Python 3.11
- Node.js 20
- PostgreSQL 16
- Redis 7
- Qdrant

## Inicio rapido

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

## Configuracion OSS

Antes de iniciar, ajustar:

- `PRODUCT_PROFILE=oss`
- llaves LLM
- `MOODLE_URL` y `MOODLE_API_KEY` si se usa Moodle
- `MOODLE_USER_MAP_JSON` para mapear usuarios de Agentica a Moodle

## Bootstrap del fork

Seguir [OSS bootstrap checklist](docs/oss-bootstrap-checklist.md) para la publicacion inicial y el primer arranque en el servidor de destino.

Tambien ayuda revisar:

- [Guia del fork OSS publico](docs/oss-fork-guide.md)
- [Paquete de publicacion OSS](docs/oss-publication-package.md)
- [Borrador de README publico OSS](docs/oss-public-readme-draft.md)

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

Ver [LICENSE](LICENSE).
