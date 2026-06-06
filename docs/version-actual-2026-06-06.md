# Version actual 2026-06-06

## Resumen ejecutivo

Agentica ya no esta en el estado del baseline de mayo 2026. La version actual tiene cambios funcionales y tecnicos importantes en conocimiento, wizard, runtime, flujo y observabilidad.

Este documento resume que queda efectivamente implementado hoy.

## 1. Lo principal que esta activo

### Creacion de agentes

- Wizard clasico
- Wizard asistido por chat
- convivencia explicita entre ambos

### Modos de agente

- `single/direct`
- `single/react`
- `crew`

### Conocimiento

- KBs globales y restricted
- asignacion de KBs a agentes
- exigencia de KB si el agente requiere conocimiento interno

### Runtime

- LangChain para agentes simples
- CrewAI para equipos
- graph runtime operativo
- tools, MCP y skills integrados en build

### Chat y progreso

- streaming de respuesta
- progreso visible para React
- citas de fuentes web cuando se usa `web_search`
- mejor render de respuestas estructuradas

### Editor de flujo

- validacion,
- mejor conexion de nodos,
- gestion de decisiones,
- viewport mas predecible.

### Observabilidad

- pestana `Ejecuciones`
- timeline por run
- errores persistidos
- accesos a KB y web
- cantidad de resultados encontrados

### Deploy

- deploy por branch, tag o commit
- metadata de version en health

## 2. Cambios fuertes respecto al baseline 2026-05-14

### Knowledge

Antes:

- coexistian mas fuerte conocimiento propio del agente y conocimiento compartido.

Ahora:

- KBs compartidas son el modelo principal,
- la UX ya fue orientada a ese modelo,
- el retrieval federado usa KBs accesibles del agente.

### Wizard

Antes:

- el asistente AI lateral complementaba el formulario.

Ahora:

- el wizard clasico sigue limpio,
- el wizard por chat es una experiencia separada y usable.

### Single agent

Antes:

- habia mas ambiguedad entre tool-calling y comportamiento del agente.

Ahora:

- `direct` y `react` estan diferenciados,
- skills y tools se aplican segun modo.

### Observabilidad

Antes:

- la trazabilidad dependia mucho de logs y del texto final.

Ahora:

- existe persistencia de runs y eventos,
- con timeline visible por agente.

## 3. Estado actual por bloque

### Muy maduro

- agentes reactivos,
- KBs,
- web search,
- chat sandbox,
- monitor de ejecuciones,
- deploy por ref.

### Maduro pero aun evolutivo

- editor de flujo,
- wizard por chat,
- render de respuestas estructuradas,
- resumen de progreso de React.

### Aun pendiente como gran evolucion

- agente proactivo como segunda entidad,
- monitoreo agregado inter-agente,
- documentos temporales subidos desde chat,
- OCR en PDFs.

## 4. Riesgos o limites conocidos

- algunos formatos de respuesta del modelo pueden requerir ajuste fino de render,
- PDFs escaneados no tienen OCR,
- el editor de flujo todavia tiene margen de mejora en UX,
- el wizard por chat puede seguir puliendose en inferencia y cierre de draft.

## 5. Documentacion relacionada

Para entender la version actual conviene leer:

- `docs/arquitectura-actual-2026-06-06.md`
- `docs/funcional-modulos-2026-06-06.md`
- `docs/runtime-observabilidad-2026-06-06.md`
- `docs/conocimiento-rag-2026-06-06.md`

Y mantener como referencia historica:

- `docs/version-agentica-2026-05-14.md`

## 6. Proximo salto de producto

La siguiente evolucion estructural prevista es:

- agentes proactivos como segunda entidad,
- con autonomia real,
- usando la capa de observabilidad actual como base.
