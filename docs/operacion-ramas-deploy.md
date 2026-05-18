# Operacion de ramas y deploy

Esta guia deja un criterio simple para operar Agentica entre `main`, ramas evolutivas y baselines.

## Esquema recomendado

- `main`: rama estable para produccion.
- `codex-wizard-ai-advisor`: rama evolutiva activa.
- `tags`: fotos estables para reinstalar una version exacta, por ejemplo `agentica-2026-05-14-baseline`.

## Cuando usar cada una

- Usar `main` cuando el server debe quedar en una version estable y ya validada.
- Usar una rama evolutiva cuando estamos probando cambios funcionales antes del merge.
- Usar un tag cuando queremos reinstalar o replicar una foto exacta en otro server.

## Deploy de produccion estable

```bash
cd /opt/agentica
sudo bash infra/scripts/deploy.sh --ref main
```

## Deploy de una rama evolutiva

```bash
cd /opt/agentica
sudo bash infra/scripts/deploy.sh --ref codex-wizard-ai-advisor
```

## Deploy de un baseline por tag

```bash
cd /opt/agentica
sudo bash infra/scripts/deploy.sh --ref agentica-2026-05-14-baseline
```

## Deploy de un commit exacto

```bash
cd /opt/agentica
sudo bash infra/scripts/deploy.sh --ref 2ab7941
```

## Como verificar que version esta corriendo

### 1. Desde el server

```bash
cd /opt/agentica
git rev-parse --short HEAD
docker compose -f docker-compose.prod.yml ps
```

### 2. Desde la API

```bash
curl -s https://axenova.com/agentica/api/health
curl -s https://axenova.com/agentica/api/health/version
```

La respuesta incluye:

- `version`
- `git_sha`
- `git_ref`
- `build_time`

## Flujo sugerido de promocion

1. Desarrollar y probar en `codex-wizard-ai-advisor`.
2. Validar funcionalmente en el server de prueba.
3. Cuando el bloque quede cerrado, mergear a `main`.
4. Si esa foto debe preservarse para reinstalacion futura, crear un tag.

## Ejemplo de tag de baseline

```bash
git tag agentica-2026-05-14-baseline 2ab7941
git push origin agentica-2026-05-14-baseline
```

## Nota operativa

`deploy.sh --ref ...` ahora deja trazado en el log final:

- ref desplegada
- commit desplegado
- fecha/hora UTC del build

Eso ayuda a confirmar rapidamente que el server quedo en la version correcta.
