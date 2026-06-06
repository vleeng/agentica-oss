# Funcional de modulos 2026-06-06

## Alcance

Este documento resume como funciona Agentica hoy desde producto y operacion.

## 1. Creacion de agentes

### Wizard clasico

Es el flujo por formulario paso a paso.

Permite definir:

- tipo de agente,
- objetivo,
- modelo,
- tools,
- skills,
- KBs,
- canales,
- restricciones.

Puntos vigentes:

- ya no muestra el panel lateral viejo de ayuda AI,
- si el agente requiere conocimiento interno, exige asociar al menos una KB,
- en agentes simples el usuario no necesita pensar en arquitectura interna si no quiere.

### Wizard asistido por chat

Es una segunda opcion de entrada que convive con el wizard clasico.

Caracteristicas:

- conversa con el usuario,
- pregunta en lenguaje funcional,
- interpreta necesidades,
- completa un `draft_state` estructurado,
- muestra un resumen vivo,
- crea el agente con el mismo pipeline de `spec`.

Preguntas funcionales tipicas:

- que problema queres resolver,
- si necesita conocimiento propio,
- si necesita datos externos,
- si debe usar herramientas o acciones.

No deberia basarse en preguntas tecnicas tipo:

- queres direct o react.

## 2. Modos de agente

### Agente simple

Tiene dos comportamientos internos:

- `direct`
- `react`

#### Direct

Uso esperado:

- responder rapido,
- sin herramientas operativas,
- skills como contexto de prompt.

#### React

Uso esperado:

- razonar por pasos,
- usar tools,
- consultar KBs,
- buscar en web,
- dejar progreso visible.

### Equipo de agentes

Camino multiagente basado en CrewAI.

Uso esperado:

- tareas mas largas o especializadas,
- division por roles,
- proceso coordinado.

## 3. Bases de conocimiento

La UX actual ya empuja el modelo de KBs compartidas como contenedor principal.

### Tipos de KB

- `global`: disponible para todos los agentes
- `restricted`: disponible solo para agentes asignados

### Gestion

Desde `Libreria -> Conocimiento` se puede:

- crear KB,
- editar metadata,
- subir archivos,
- reindexar,
- borrar fuentes,
- asignar visibilidad.

### Regla funcional importante

Si un agente requiere conocimiento interno:

- debe tener al menos una KB asociada antes de crearse.

## 4. Tools

Las tools pueden venir de varias fuentes:

- built-in
- skills
- MCP
- custom tools

Ejemplos relevantes hoy:

- `knowledge_base`
- `web_search`
- `calculator`
- `send_email`

En agentes `react`:

- pueden ejecutarse como parte del flujo,
- pueden ser llamadas por el agente,
- quedan reflejadas en la bitacora y en `Ejecuciones`.

## 5. Skills

Los skills son reutilizables y se aplican al agente por asignacion.

Comportamiento actual:

- siempre pueden aportar contexto/prompt,
- solo aportan tools ejecutables cuando el modo lo permite.

Regla vigente:

- en `direct`, skills si como prompt, tools no
- en `react`, skills si como prompt y tools

## 6. MCP

Agentica puede montar tools provenientes de servidores MCP.

El usuario configura servidores MCP y luego los asigna al agente.

En runtime:

- las tools MCP se inyectan antes del build,
- quedan disponibles para agentes compatibles.

## 7. Editor de flujo

El editor permite inspeccionar y modificar el flujo LangChain del agente.

Mejoras ya activas:

- autovalidacion,
- mejor conexion entre nodos,
- borrado de nodos,
- editor de ramas para decisiones,
- scroll lateral y viewport mas previsibles.

Validaciones funcionales actuales:

- nodo tool sin `tool_name`,
- decisiones mal conectadas,
- nodos huerfanos,
- estructura incompleta.

## 8. Chat del agente

En el monitor del agente existe un sandbox/chat operativo.

Comportamiento relevante hoy:

- streaming de respuesta,
- progreso visible en agentes `react`,
- resumen de pasos utiles,
- cita de fuentes web cuando se usa `web_search`,
- render enriquecido para respuestas tipo receta.

## 9. Monitor de ejecuciones

La pestana `Ejecuciones` muestra:

- runs recientes,
- estado,
- errores,
- uso de KB,
- uso de web,
- timeline,
- respuesta final.

Metricas actuales:

- cantidad de runs,
- fallidas,
- con KB,
- con web.

Y por evento puede mostrar:

- resultados encontrados,
- hallazgos,
- fuentes,
- errores.

## 10. Evaluacion y optimizacion

El monitor conserva las acciones de:

- evaluar
- optimizar

Estas siguen apoyandose en el `AgentDesign` generado y en los test cases del disenio.

## 11. Accesos y usuarios

La gestion de usuarios del tenant se hace desde `Accesos`.

Capacidades vigentes:

- alta de usuarios,
- asignacion de roles del tenant,
- operacion dentro del mismo tenant.

## 12. Deploy y versionado

El sistema soporta despliegue por:

- branch
- tag
- commit

Mediante:

- `infra/scripts/deploy.sh --ref ...`

La version desplegada puede consultarse via:

- `/health`
- `/health/version`

## 13. Estado funcional general

Lo mas maduro hoy es:

- agentes reactivos,
- KBs compartidas,
- tools,
- chat,
- monitoreo de ejecuciones,
- deploy por ref.

Lo principal que queda como siguiente bloque mayor es:

- agentes proactivos como segunda entidad.
