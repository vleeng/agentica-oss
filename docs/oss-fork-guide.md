# Guia del fork OSS publico

Este documento resume como publicar la linea open source de Agentica para la Universidad de la Ciudad de Buenos Aires.

## Objetivo

Publicar una version separada del producto para:

- instalacion en servidor propio
- uso comunitario y academico
- evolucion abierta en GitHub
- despliegue simple en una unica organizacion o tenant base

## Base de partida

El fork publico se toma desde la linea privada ya alineada con:

- `platform` como base tecnica
- `saas` fuera del alcance publico
- Moodle aislado solo para OSS
- branding sobrio con perfil `oss`

## Variables de entorno clave

El fork OSS debe arrancar con:

- `PRODUCT_PROFILE=oss`
- `ENVIRONMENT=production` o `development` segun el entorno
- `MOODLE_URL` y `MOODLE_API_KEY` si se usa Moodle
- `MOODLE_USER_MAP_JSON` para mapear usuarios de Agentica a Moodle

## Que incluye el fork

- runtime de agentes
- wizard clasico
- wizard asistido por chat
- KBs y RAG
- skills, tools y MCP
- editor de flujo
- monitor del agente
- monitor de ejecuciones
- observabilidad de tools, skills y KB
- integracion Moodle en perfil OSS

## Que queda fuera

- billing
- planes comerciales
- limites por plan
- flujos de signup comercial
- branding SaaS premium
- funcionalidades privadas de Vleeng no orientadas a comunidad

## Recomendaciones de publicacion

1. Revisar que el perfil por defecto del fork sea `oss`.
2. Confirmar que no queden textos de planes comerciales en pantallas publicas.
3. Verificar que Moodle no dependa de headers del cliente.
4. Documentar instalacion local y en servidor.
5. Definir licencia y politica de contribucion antes de abrir el repo.

## Primer arranque sugerido

1. Copiar `.env.example` a `.env`.
2. Ajustar `PRODUCT_PROFILE=oss`.
3. Cargar llaves LLM y, si aplica, la configuracion de Moodle.
4. Levantar servicios base con Docker Compose.
5. Crear el tenant inicial y validar login.

## Criterio minimo para publicar

El fork puede abrirse al publico cuando:

- la UI no expone planes ni billing
- el README apunta a esta guia
- existe `LICENSE`
- existe `CONTRIBUTING.md`
- la build pasa en frontend y backend

