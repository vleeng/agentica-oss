# Plan de Desarrollo - Operatividad de Tools

Plan interno para llevar el sistema de tools de Agentica desde su estado actual a una operacion consistente entre UI, runtime y observabilidad.

Estado del documento: mayo de 2026

## 1. Objetivo

Queremos que toda tool visible en la plataforma cumpla estas condiciones:

1. el usuario entiende si esta lista, limitada o pendiente de configuracion
2. el framework real soporta lo que la UI promete
3. la configuracion necesaria puede resolverse de forma clara
4. el runtime falla de manera controlada cuando falta setup
5. hay smoke tests minimos para evitar regresiones silenciosas

## 2. Alcance

Este plan cubre:

- built-in tools
- custom tools
- RAG como capacidad operativa
- MCP tools asignadas a agentes
- skills en su rol de inyector de tools y prompt
- compatibilidad LangChain / CrewAI
- validacion visible en UI
- observabilidad minima por tool

## 3. Estado actual resumido

### Herramientas razonablemente listas

- `calculator`
- custom tools
- skills
- RAG en LangChain

### Herramientas ofrecidas pero no cerradas como producto

- `web_search`
- `sql_query`
- `rest_api_call`
- `send_email`
- RAG en CrewAI
- MCP en CrewAI

### Problemas transversales

- la UI ofrece tools que requieren configuracion que hoy no tiene una experiencia clara
- hay diferencias reales entre LangChain y CrewAI que no siempre estan explicitadas
- varias capacidades existen en codigo pero no como experiencia autoservicio

## 4. Estrategia general

Vamos a dividir el trabajo en tres releases:

- **Release A**: alinear catalogo con realidad y cerrar `web_search`
- **Release B**: cerrar RAG y MCP en CrewAI, y rehacer `send_email`
- **Release C**: endurecer `sql_query`, cerrar `rest_api_call`, agregar smoke tests, observabilidad y documentacion viva

## 5. Workstreams

### WS1 - Catalogo y UX

Responsable principal:

- frontend
- apoyo backend para metadata de compatibilidad

Objetivo:

- que el catalogo visual refleje estado real por tool

### WS2 - Runtime y compatibilidad

Responsable principal:

- backend

Objetivo:

- que LangChain y CrewAI ejecuten las tools que prometen

### WS3 - Configuracion operativa

Responsable principal:

- backend
- frontend

Objetivo:

- que las tools con secretos o endpoints tengan una via clara de configuracion

### WS4 - Calidad y observabilidad

Responsable principal:

- backend
- QA / smoke tests

Objetivo:

- medir, registrar y prevenir regresiones

## 6. Roadmap por fases

## Fase 1 - Alinear catalogo y estado real

Objetivo:

- dejar de ofrecer tools sin semaforo de operatividad

Tickets:

### TOOL-01 - Modelo de estado por tool

- Prioridad: P0
- Estimacion: M
- Workstream: WS1
- Dueño sugerido: Backend
- Dependencias: ninguna

Trabajo:

- definir metadata por tool:
  - `ready`
  - `needs_config`
  - `framework_limited`
  - `disabled`
- declarar compatibilidad por framework
- decidir si la fuente vive en backend, frontend o ambos

Criterio de aceptacion:

- existe un contrato claro que describe estado y compatibilidad de cada tool

### TOOL-02 - Mostrar estado de tools en la UI

- Prioridad: P0
- Estimacion: M
- Workstream: WS1
- Dueño sugerido: Frontend
- Dependencias: TOOL-01

Trabajo:

- reflejar el estado en:
  - wizard
  - StepCrew
  - paneles de configuracion cuando aplique
- mostrar si una tool:
  - esta lista
  - requiere configuracion
  - no esta soportada en ese framework

Criterio de aceptacion:

- un usuario puede distinguir visualmente entre tool lista y tool pendiente

### TOOL-03 - Matriz de compatibilidad visible

- Prioridad: P1
- Estimacion: S
- Workstream: WS1
- Dueño sugerido: Frontend
- Dependencias: TOOL-01

Trabajo:

- agregar mensajes o badges de compatibilidad LangChain / CrewAI

Criterio de aceptacion:

- la UI no trata a ambas familias de runtime como equivalentes cuando no lo son

## Fase 2 - Cerrar `web_search`

Objetivo:

- dejar `web_search` operativa end-to-end

Tickets:

### TOOL-04 - Resolver fuente de credencial Tavily

- Prioridad: P0
- Estimacion: M
- Workstream: WS3
- Dueño sugerido: Backend
- Dependencias: TOOL-01

Trabajo:

- decidir fuente de la credencial:
  - config global
  - vault
  - config por tenant
  - config por tool
- implementar resolver unico

Criterio de aceptacion:

- `web_search` ya no depende de config vacia por defecto para funcionar

### TOOL-05 - UX de configuracion para `web_search`

- Prioridad: P1
- Estimacion: M
- Workstream: WS3
- Dueño sugerido: Frontend
- Dependencias: TOOL-04

Trabajo:

- mostrar prerequisito de configuracion
- indicar de donde sale la credencial

Criterio de aceptacion:

- el usuario entiende como habilitar `web_search`

### TOOL-06 - Corregir uso de `web_search` en CrewAI

- Prioridad: P0
- Estimacion: M
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: TOOL-04

Trabajo:

- revisar adapter / serializacion de input
- evitar errores de parseo de action input
- validar en agentes crew

Criterio de aceptacion:

- un crew con `web_search` puede usar la tool sin romper el loop de agente

### TOOL-07 - Smoke test de `web_search`

- Prioridad: P1
- Estimacion: S
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: TOOL-04, TOOL-06

Trabajo:

- test en LangChain
- test en CrewAI
- test de fallback sin credencial

Criterio de aceptacion:

- la tool queda cubierta por smoke tests minimos

## Fase 3 - Llevar RAG a CrewAI

Objetivo:

- que `rag.enabled` tenga efecto operativo en CrewAI

Tickets:

### TOOL-08 - Definir estrategia de inyeccion RAG en CrewAI

- Prioridad: P0
- Estimacion: S
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: ninguna

Trabajo:

- decidir si RAG se inyecta:
  - en todos los roles
  - en roles seleccionados
  - en el coordinador

Criterio de aceptacion:

- hay una decision tecnica explicita, no implícita

### TOOL-09 - Implementar RAG en builder CrewAI

- Prioridad: P0
- Estimacion: M
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: TOOL-08

Trabajo:

- agregar wiring en `CrewAIAgentBuilder`
- respetar `top_k` y `agent_id`

Criterio de aceptacion:

- un agente crew con RAG habilitado puede consultar conocimiento indexado

### TOOL-10 - Ajustar UX y documentacion de RAG por framework

- Prioridad: P1
- Estimacion: S
- Workstream: WS1
- Dueño sugerido: Frontend
- Dependencias: TOOL-09

Trabajo:

- actualizar textos y estados para que RAG en CrewAI deje de aparecer como limitada

Criterio de aceptacion:

- la UI refleja correctamente el nuevo soporte

## Fase 4 - Llevar MCP a CrewAI

Objetivo:

- que asignar un MCP a un crew tenga efecto real

Tickets:

### TOOL-11 - Pasar tools MCP al builder CrewAI

- Prioridad: P0
- Estimacion: M
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: ninguna

Trabajo:

- consumir tools MCP descubiertas tambien en CrewAI
- definir alcance por rol

Criterio de aceptacion:

- los MCP asignados aparecen en el runtime crew

### TOOL-12 - Probar MCP en crew

- Prioridad: P1
- Estimacion: M
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: TOOL-11

Trabajo:

- test con servidor MCP real o fixture
- test de error controlado si el servidor falla

Criterio de aceptacion:

- un crew invoca una tool MCP sin romper el runtime

## Fase 5 - Rehacer `send_email`

Objetivo:

- dejar el envio de email apoyado en el mailer global de la plataforma

Tickets:

### TOOL-13 - Integrar `send_email` con `core.mailer`

- Prioridad: P1
- Estimacion: M
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: ninguna

Trabajo:

- reemplazar credenciales SMTP por tool
- reutilizar configuracion global

Criterio de aceptacion:

- si el mailer global esta configurado, la tool funciona sin setup adicional por agente

### TOOL-14 - Fallback claro de `send_email`

- Prioridad: P1
- Estimacion: S
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: TOOL-13

Trabajo:

- definir mensaje de error coherente si falta SMTP

Criterio de aceptacion:

- el agente no crashea y el usuario entiende la limitacion

## Fase 6 - Endurecer `sql_query`

Objetivo:

- que `sql_query` sea segura y gobernable

Tickets:

### TOOL-15 - Definir estrategia de datasource para SQL

- Prioridad: P1
- Estimacion: M
- Workstream: WS3
- Dueño sugerido: Backend
- Dependencias: TOOL-01

Trabajo:

- decidir de donde sale el `dsn`
- decidir nivel de aislamiento por tenant o fuente

Criterio de aceptacion:

- hay una estrategia de configuracion aprobada

### TOOL-16 - Aplicar restricciones reales a `sql_query`

- Prioridad: P1
- Estimacion: M
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: TOOL-15

Trabajo:

- mantener solo `SELECT`
- aplicar allowlist de tablas
- endurecer validaciones

Criterio de aceptacion:

- la tool rechaza tablas no permitidas y consultas fuera de politica

### TOOL-17 - Definir exposicion de `sql_query` en UI

- Prioridad: P2
- Estimacion: S
- Workstream: WS1
- Dueño sugerido: Frontend + Producto
- Dependencias: TOOL-15

Trabajo:

- decidir si se muestra:
  - siempre
  - solo cuando hay datasource
  - solo para ciertos roles

Criterio de aceptacion:

- la UI no expone una capacidad imposible de usar

## Fase 7 - Cerrar `rest_api_call`

Objetivo:

- convertirla en una integracion configurable y segura

Tickets:

### TOOL-18 - Definir configuracion operativa de `rest_api_call`

- Prioridad: P1
- Estimacion: M
- Workstream: WS3
- Dueño sugerido: Backend
- Dependencias: TOOL-01

Trabajo:

- modelar:
  - dominios permitidos
  - headers por defecto
  - metodos permitidos

Criterio de aceptacion:

- existe contrato claro de configuracion para la tool

### TOOL-19 - UI de configuracion para `rest_api_call`

- Prioridad: P2
- Estimacion: M
- Workstream: WS3
- Dueño sugerido: Frontend
- Dependencias: TOOL-18

Trabajo:

- permitir configurar la tool sin tocar codigo

Criterio de aceptacion:

- el usuario puede dejar un endpoint operativo con defaults seguros

### TOOL-20 - Enforcements de seguridad en runtime

- Prioridad: P1
- Estimacion: S
- Workstream: WS2
- Dueño sugerido: Backend
- Dependencias: TOOL-18

Trabajo:

- bloquear dominios no permitidos
- bloquear metodos fuera de politica

Criterio de aceptacion:

- el runtime respeta la configuracion definida

## Fase 8 - Smoke tests automaticos

Objetivo:

- detectar rapido si una tool visible dejo de enchufarse

Tickets:

### TOOL-21 - Smoke tests de built-in tools

- Prioridad: P1
- Estimacion: M
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: TOOL-04, TOOL-13, TOOL-16, TOOL-20

Trabajo:

- tests de instanciacion
- tests de fallback

Criterio de aceptacion:

- cada built-in visible tiene al menos un smoke test basico

### TOOL-22 - Smoke tests de wiring por framework

- Prioridad: P1
- Estimacion: M
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: TOOL-06, TOOL-09, TOOL-11

Trabajo:

- validar injection en LangChain
- validar injection en CrewAI

Criterio de aceptacion:

- la compatibilidad declarada coincide con la compatibilidad ejecutable

## Fase 9 - Observabilidad de tools

Objetivo:

- saber que tool falla, donde y con que patron

Tickets:

### TOOL-23 - Logging por tool

- Prioridad: P2
- Estimacion: S
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: ninguna

Trabajo:

- loggear nombre de tool, framework y tipo de error

Criterio de aceptacion:

- los fallos de tools se pueden rastrear sin inspeccion ciega

### TOOL-24 - Contadores de uso y error por tool

- Prioridad: P3
- Estimacion: M
- Workstream: WS4
- Dueño sugerido: Backend
- Dependencias: TOOL-23

Trabajo:

- agregar metricas agregadas por tool

Criterio de aceptacion:

- se puede responder que tools se usan y cuales fallan mas

## Fase 10 - Documentacion viva

Objetivo:

- dejar visible el estado real del sistema de tools

Tickets:

### TOOL-25 - Documentar matriz de tools

- Prioridad: P2
- Estimacion: S
- Workstream: WS4
- Dueño sugerido: Documentacion / Producto
- Dependencias: TOOL-01

Trabajo:

- agregar al manual:
  - estado
  - prerequisitos
  - compatibilidad por framework

Criterio de aceptacion:

- soporte y usuarios avanzados tienen una verdad documentada

## 7. Orden recomendado de ejecucion

### Release A

- TOOL-01
- TOOL-02
- TOOL-03
- TOOL-04
- TOOL-05
- TOOL-06
- TOOL-07

Meta del release:

- catalogo honesto y `web_search` funcional

### Release B

- TOOL-08
- TOOL-09
- TOOL-10
- TOOL-11
- TOOL-12
- TOOL-13
- TOOL-14

Meta del release:

- cerrar la brecha CrewAI para RAG, MCP y email

### Release C

- TOOL-15
- TOOL-16
- TOOL-17
- TOOL-18
- TOOL-19
- TOOL-20
- TOOL-21
- TOOL-22
- TOOL-23
- TOOL-24
- TOOL-25

Meta del release:

- seguridad, smoke tests, observabilidad y documentacion estable

## 8. Riesgos a vigilar

1. ofrecer configuracion fina de tools sin modelo claro de secretos
2. seguir mezclando "catalogo visual" con "capacidad realmente soportada"
3. cerrar LangChain mas rapido que CrewAI y volver a generar deuda de compatibilidad
4. habilitar `sql_query` o `rest_api_call` sin restricciones suficientes

## 9. Definicion de terminado

Consideraremos este plan cumplido cuando:

- toda tool visible tenga estado explicito
- `web_search` funcione de punta a punta
- RAG y MCP no queden limitados silenciosamente a un solo framework
- `send_email`, `sql_query` y `rest_api_call` tengan historia de configuracion clara
- existan smoke tests minimos por tool y por framework
- la documentacion refleje el estado real

