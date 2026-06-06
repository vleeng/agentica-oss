# Runtime y observabilidad 2026-06-06

## Objetivo

Este documento describe como se construyen, ejecutan y observan los agentes en la version actual.

## 1. RuntimeFactory

`RuntimeFactory` es el punto de entrada tecnico para construir runtimes reales desde un `AgentDesign`.

Responsabilidades principales:

- recuperar y expandir skills,
- inyectar tools de skills si el modo lo permite,
- inyectar MCP tools,
- anexar comportamiento/policies al prompt,
- delegar al builder correcto segun framework.

### Reglas importantes

- `single + direct`:
  - skills si como prompt,
  - tools no.
- `single + react`:
  - skills si,
  - tools si,
  - RAG y tools operativas disponibles.

## 2. Builders

### LangChainAgentBuilder

Es el camino principal para agentes simples.

Soporta:

- modo `direct`,
- modo `react`,
- graph runtime,
- tools built-in,
- web search,
- knowledge base,
- MCP tools.

### CrewAIAgentBuilder

Se usa para agentes tipo equipo.

Construye el runtime CrewAI a partir del spec y los agentes del equipo.

## 3. Runtime LangChain

El runtime LangChain puede operar por:

- invocacion directa,
- streaming,
- flujo graficado.

### Direct

Responde en una sola pasada con el modelo.

### React

Puede:

- razonar,
- consultar KB,
- usar web search,
- usar tools,
- emitir progreso.

### Graph runtime

Cuando hay `graph_blueprint`, el runtime recorre nodos:

- `start`
- `agent`
- `decision`
- `tool`
- `end`

El runtime actual ya:

- normaliza tipos de nodo,
- normaliza algunos labels de tools,
- ejecuta `knowledge_base` y `web_search`,
- soporta decisiones,
- reutiliza contexto de KB cuando ya se consulto en el mismo flujo.

## 4. Progreso visible

Los agentes `react` emiten progreso durante la respuesta.

Ejemplos:

- pensando,
- buscando en conocimientos,
- encontre en conocimientos,
- buscando en web,
- encontre en web,
- redactando respuesta.

La bitacora ya fue limpiada para:

- reducir duplicados,
- evitar pasos demasiado genericos,
- mostrar fuentes y hallazgos utiles.

## 5. Conversaciones y runs

Hoy el monitoreo operativo se apoya en las conversaciones.

Cada run tiene:

- `conversation_id`
- `session_id`
- canal
- mensajes
- eventos operativos
- timestamps

## 6. conversation_events

La tabla `conversation_events` permite persistir observabilidad de ejecucion.

Tipos de informacion registrada hoy:

- inicio de ejecucion,
- progreso,
- skill aplicada,
- consulta a KB,
- resultado de KB,
- consulta web,
- resultado web,
- errores,
- respuesta final.

Por cada evento se guardan datos como:

- tipo,
- actor,
- mensaje,
- payload,
- fecha,
- y en KB/web tambien cantidad de resultados encontrados.

## 7. Endpoints de observabilidad

Dentro del modulo de agentes existen endpoints para runs:

- `GET /api/v1/agents/{id}/runs`
- `GET /api/v1/agents/{id}/runs/{conversation_id}`

Esto alimenta la pestana `Ejecuciones` del monitor del agente.

## 8. Monitor de ejecuciones

La UI actual muestra:

- lista de runs,
- filtros,
- metricas rapidas,
- timeline,
- respuesta final.

Estados actuales:

- `completed`
- `completed_with_issues`
- `failed`
- `in_progress`

Filtros actuales:

- por estado,
- solo con KB,
- solo con web,
- solo con errores,
- busqueda libre.

## 9. Manejo de errores

El runtime ya persiste errores de ejecucion, incluyendo:

- errores de tools,
- errores de runtime,
- timeouts.

Eso permite que un run fallido siga siendo visible en `Ejecuciones`.

## 10. Persistencia de respuesta final

La respuesta final del agente tambien se conserva, lo que permite:

- revisar que respondio,
- contrastarlo con los eventos previos,
- entender como llego a la salida.

## 11. WebSocket y REST

### REST

`POST /api/v1/agents/{id}/invoke`

- ejecuta el runtime,
- recolecta progreso,
- persiste uso y errores,
- devuelve `AgentResponse`.

### WebSocket

`/api/v1/agents/{id}/ws`

- hace streaming de tokens,
- emite progreso incremental,
- persiste luego los eventos del run.

## 12. Que ya sirve para el futuro

La capa actual de observabilidad ya deja lista la base para:

- agentes proactivos,
- aprobaciones,
- replay de ejecuciones,
- metricas agregadas por agente,
- supervision operativa.

## 13. Limites actuales

- No existe todavia un monitor agregado cross-agent.
- No existe replay paso a paso de artefactos complejos.
- La nueva entidad de agente proactivo todavia no esta implementada.
