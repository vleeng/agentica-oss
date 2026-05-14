# Implementar Agentica baseline 2026-05-14 en otro server

Esta guía explica cómo instalar en otro server la versión funcional de Agentica identificada como baseline del 14 de mayo de 2026.

La idea es poder seguir evolucionando `main` sin perder la posibilidad de desplegar exactamente la versión actual.

## 1. Versión a implementar

Versión funcional:

- `Agentica baseline 2026-05-14`

Commit recomendado:

- `2ab7941`

Repositorio:

- `https://github.com/vleeng/agentica`

Documentos asociados:

- `docs/version-agentica-2026-05-14.md`
- `docs/manual-usuario-agentica.md`

## 2. Recomendación: crear tag estable

Antes de usar esta versión en varios servers, conviene crear un tag Git con nombre humano.

Desde una máquina que tenga el repo actualizado:

```bash
git checkout main
git pull origin main
git tag agentica-2026-05-14-baseline 2ab7941
git push origin agentica-2026-05-14-baseline
```

Después, cualquier server puede instalar por tag:

```bash
git clone https://github.com/vleeng/agentica.git
cd agentica
git checkout agentica-2026-05-14-baseline
```

Si no se usa tag, se puede instalar directamente por commit:

```bash
git clone https://github.com/vleeng/agentica.git
cd agentica
git checkout 2ab7941
```

## 3. Variables requeridas

Crear `.env` desde el ejemplo:

```bash
cp .env.example .env
```

Variables mínimas a revisar:

- `ANTHROPIC_API_KEY` o la key del proveedor builder que se vaya a usar
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET`
- `ADMIN_PASSWORD`
- `ENCRYPTION_KEY`
- `BASE_DOMAIN`
- `CORS_ORIGINS`
- `VITE_API_URL`
- `VITE_WS_URL`

Importante:

- `JWT_SECRET` debe ser fuerte y único por ambiente.
- `ENCRYPTION_KEY` debe mantenerse estable; si cambia, las credenciales cifradas existentes pueden dejar de leerse.
- `ADMIN_PASSWORD` se usa para crear el superusuario inicial si no existe.

## 4. Instalación en desarrollo

Desde la raíz del repo:

```bash
cp .env.example .env
cp .env backend/.env
docker compose up -d postgres redis qdrant
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

En Windows PowerShell, activar entorno con:

```powershell
.\.venv\Scripts\Activate.ps1
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

URL local esperada:

- `http://localhost:5173`

API local esperada:

- `http://localhost:8000/docs`

## 5. Instalación en producción con scripts del repo

Primera instalación:

```bash
sudo REPO_URL=https://github.com/vleeng/agentica.git bash infra/scripts/setup_vps.sh
```

Entrar al directorio de deploy:

```bash
cd /opt/agentica
```

Fijar la versión baseline:

```bash
git fetch origin
git checkout 2ab7941
```

Si existe el tag recomendado:

```bash
git fetch origin --tags
git checkout agentica-2026-05-14-baseline
```

Editar variables:

```bash
sudo nano /opt/agentica/.env
```

Ejecutar deploy:

```bash
sudo bash infra/scripts/deploy.sh
```

## 6. Verificación posterior

Verificar API:

```bash
curl -f http://localhost:8000/health
```

Verificar contenedores:

```bash
docker compose ps
```

Verificar commit desplegado:

```bash
git log --oneline -1
```

Debe mostrar:

```text
2ab7941 Document Agentica baseline
```

## 7. Checklist funcional

Después del deploy, validar:

- login con usuario admin
- creación o acceso al tenant inicial
- carga de una credencial en `Boveda IA`
- carga de al menos un modelo para esa credencial
- creación de un agente simple desde el wizard
- build automático del runtime
- prueba en sandbox
- deploy del agente
- apertura del chat standalone `/c/{agent_id}`
- observabilidad básica

## 8. Qué no incluye esta versión

Esta versión no incluye todavía:

- wizard asistido por IA
- agentes goal-based como entidad propia
- automatizaciones recurrentes
- scheduler de objetivos
- historial formal de runs
- approvals globales
- observabilidad por step de automatización

Esas capacidades quedan como evolutivos posteriores y deberían implementarse sobre una rama o versión nueva.

## 9. Cómo seguir evolutivos sin perder este baseline

Flujo recomendado:

```bash
git checkout main
git pull origin main
git checkout -b codex/wizard-ai-advisor
```

Para volver al baseline en cualquier momento:

```bash
git checkout 2ab7941
```

O, si se creó el tag:

```bash
git checkout agentica-2026-05-14-baseline
```

## 10. Nota operativa

Si el server donde se implementa esta versión ya tenía una versión posterior de Agentica, revisar antes:

- cambios de schema
- migraciones aplicadas
- volúmenes Docker existentes
- compatibilidad de `.env`
- datos cifrados con `ENCRYPTION_KEY`

Para una instalación limpia, lo más seguro es usar volúmenes nuevos o backups claramente separados.
