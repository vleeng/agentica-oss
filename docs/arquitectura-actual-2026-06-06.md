# Arquitectura Actual 2026-06-06

## Proposito

Agentica es una plataforma multi-tenant para:

- definir agentes IA a partir de una especificacion funcional,
- construir y ejecutar runtimes reactivos por chat o API,
- conectar tools, skills, MCP y bases de conocimiento,
- observar ejecuciones reales,
- y preparar el camino para una segunda entidad de agentes proactivos.

Hoy el producto esta centrado en agentes reactivos y crews, con dos experiencias de creacion:

- Wizard clasico
- Wizard asistido por chat

## Arquitectura general

La solucion esta dividida en cuatro capas principales:

1. Frontend React
2. Backend FastAPI
3. Persistencia y runtime state
4. Infraestructura de despliegue

### Frontend

El frontend principal vive en `frontend/` y cubre:

- login y accesos,
- dashboard de agentes,
- wizard clasico,
- wizard asistido por chat,
- monitor del agente,
- editor de flujo,
- configuracion de KBs, skills, MCP y guardrails,
- monitor de ejecuciones.

Tambien existe un widget embebible en `widget/` para chat web.

### Backend

El backend vive en `backend/app/` y organiza la logica en:

- `api/v1/endpoints/`: routers FastAPI,
- `schemas/`: modelos Pydantic del dominio,
- `services/`: seleccion, generacion, wizard, evaluacion y optimizacion,
- `runtime/`: ejecucion de agentes,
- `builders/`: construccion de runtimes LangChain y CrewAI,
- `components/`: tools, RAG y piezas reutilizables,
- `db/`: acceso a datos y repositorio tenant-aware,
- `core/`: seguridad, config, limites y rate limiting.

### Persistencia

Hoy se usan varios stores con responsabilidades distintas:

- PostgreSQL:
  - datos transaccionales,
  - tenants,
  - usuarios,
  - agentes,
  - knowledge bases,
  - conversaciones,
  - eventos de ejecucion.
- Redis:
  - runtime store,
  - estado efimero,
  - rate limiting.
- Qdrant:
  - embeddings y retrieval de RAG.

### Infraestructura

La operacion se resuelve con Docker Compose.

- `docker-compose.yml`: desarrollo
- `docker-compose.prod.yml`: produccion
- `infra/scripts/deploy.sh`: despliegue por branch, tag o commit

El deploy actual publica metadata de version en:

- `GET /health`
- `GET /health/version`

## Multi-tenancy

Agentica usa un modelo multi-tenant con contexto de tenant en el backend.

Principios actuales:

- un usuario pertenece a un tenant,
- los recursos operativos se validan contra el tenant actual,
- las llaves LLM se resuelven por tenant,
- los KB links y configuraciones se filtran por tenant.

El primer usuario owner del tenant nace con el alta del tenant. Los usuarios adicionales se gestionan desde `Accesos`.

## Entidades principales

### Agente

Un agente se modela con `AgentSpec` y se materializa como `AgentDesign`.

Conceptos clave:

- `mode`:
  - `single`
  - `crew`
- `single_agent_mode`:
  - `direct`
  - `react`
- `channels`
- `tools`
- `skills`
- `mcp_server_ids`
- `knowledge_base_ids`
- `rag`
- `graph_blueprint`

### Knowledge Base

Las KBs son hoy la fuente principal de conocimiento reusable.

Cada KB puede ser:

- `global`
- `restricted`

Un agente consume KBs accesibles por visibilidad o por asignacion.

### Conversacion / ejecucion

Las conversaciones sirven hoy como base del monitoreo de ejecuciones.

Sobre cada conversacion se registran:

- mensajes,
- eventos operativos,
- accesos a KB,
- uso de tools,
- errores,
- respuesta final.

## Ciclo de vida de un agente

### 1. Creacion

La creacion puede venir por:

- wizard clasico,
- wizard asistido por chat,
- API `POST /api/v1/agents/spec`.

En esta etapa se define el `AgentSpec`.

### 2. Seleccion de framework

`FrameworkSelectorService` decide el framework base segun el spec.

Hoy los caminos principales son:

- LangChain para agentes simples
- CrewAI para equipos

### 3. Generacion de disenio

`DesignGeneratorService` construye el `AgentDesign` con:

- system prompt,
- framework decision,
- graph blueprint,
- test cases,
- diagrama Mermaid,
- estado inicial.

### 4. Build

`RuntimeFactory` enriquece el disenio y construye el runtime real.

Durante ese paso:

- inserta fragmentos de skills,
- expande tools de skills si aplica,
- monta MCP tools,
- agrega policy/guardrails al prompt,
- construye el runtime LangChain o CrewAI.

### 5. Ejecucion

El agente puede ser invocado por:

- REST
- WebSocket
- widget web

En modo `react`, el runtime puede usar:

- knowledge bases,
- web search,
- tools,
- MCP,
- flujo LangChain.

En modo `direct`, responde de forma inmediata con el modelo y usa skills solo como contexto de prompt.

### 6. Observabilidad

Cada run deja traza utilizable desde la pestana `Ejecuciones`.

Se persisten:

- eventos de progreso,
- accesos a KB,
- web search,
- errores,
- respuesta final.

## Runtimes vigentes

### Single direct

- respuesta inmediata,
- sin ejecucion de tools,
- sin RAG operativo como tool,
- skills solo como contexto de prompt.

### Single react

- razonamiento con tools,
- soporte de flujo LangChain,
- RAG y web search,
- bitacora de pasos visible en chat,
- monitoreo de ejecucion.

### Crew

- equipo multiagente,
- proceso secuencial hoy como camino principal,
- herramientas y conocimiento compartido segun spec.

## Modulos funcionales activos

Los modulos mas relevantes en la version actual son:

- Wizard clasico
- Wizard por chat
- KBs y RAG
- Skills
- MCP
- Editor de flujo
- Monitor del agente
- Monitor de ejecuciones
- Accesos por tenant
- Deploy por ref

## Decisiones vigentes de arquitectura

### Conocimiento

La direccion actual del producto es:

- KBs como contenedor principal de conocimiento
- sin empujar conocimiento legacy propio del agente como modelo principal

### Wizard

Conviven dos experiencias:

- clasica por formulario
- asistida por chat

La segunda no reemplaza a la primera.

### Observabilidad

La observabilidad ya no depende solo de logs del backend.

Hoy existe persistencia operativa por ejecucion con timeline visible por agente.

## Limites actuales

- No hay OCR para PDFs escaneados.
- El agente proactivo todavia no existe como segunda entidad.
- El editor de flujo mejoro, pero sigue siendo un area de evolucion.
- La documentacion historica previa a junio 2026 no refleja todos los cambios nuevos.

## Direccion inmediata

La base actual ya soporta razonablemente:

- creacion de agentes por dos caminos,
- consumo de tools y KBs,
- ejecucion monitoreada,
- despliegue por branch/tag/commit.

El siguiente salto de arquitectura previsto es:

- agentes proactivos como segunda entidad,
- apoyados en la capa de observabilidad ya incorporada.
