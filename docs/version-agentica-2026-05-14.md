# Agentica - Baseline funcional 2026-05-14

Este documento identifica la versión funcional actual de Agentica al 14 de mayo de 2026.

Propósito:

- dejar una foto clara de lo que existe hoy
- separar alcance actual de ideas evolutivas
- facilitar una implementación equivalente en otro server
- servir como referencia antes de abrir nuevas versiones de producto

Referencia técnica:

- rama al relevar: `main`
- commit local de referencia: `d65bd7c`
- manual asociado: `docs/manual-usuario-agentica.md`

## 1. Alcance funcional actual

Agentica hoy es una consola multi-tenant para crear, probar, configurar, desplegar y observar agentes de IA.

Capacidades principales:

- autenticación de usuarios y contexto de tenant
- roles `viewer`, `developer` y `owner`
- dashboard de agentes del tenant
- wizard de creación de agentes
- agentes simples y equipos de agentes
- selección automática de framework entre LangChain y CrewAI
- Bóveda IA para credenciales, modelos y costos
- custom tools en Python
- librería de skills
- servidores MCP
- bases de conocimiento reutilizables
- conocimiento por agente
- monitor con sandbox, evaluación, diseño, configuración y edición
- editor visual de flujo basado en `graph_blueprint`
- deploy de chat standalone
- API keys por agente
- observabilidad de uso, límites, costo y consumo por agente
- administración de usuarios, tenants, solicitudes free y planes cuando el rol/permisos lo permiten

## 2. Navegación visible

Áreas principales:

- `Agentes`
- `Crear agente`
- `Observabilidad`
- `Cuenta`
- `Accesos`
- `Boveda IA`
- `Mis tools`
- `API Keys`

Librería:

- `Skills`
- `MCPs`
- `Conocimiento`

Accesos auxiliares:

- `API Docs`
- `Cerrar sesion`

## 3. Wizard actual

El `Requirement Wizard` actual es un wizard guiado, sin advisor IA embebido.

Pasos para agente simple:

1. tipo de agente
2. identidad
3. herramientas
4. memoria y canales
5. modelo
6. revisión

Pasos para equipo de agentes:

1. tipo de agente
2. identidad
3. equipo de agentes
4. memoria y canales
5. modelo
6. revisión

El wizard actual permite:

- elegir `Agente simple` o `Equipo de agentes`
- cargar nombre, objetivo, descripción y restricciones
- seleccionar tools built-in y custom tools activas
- configurar canales, memoria y RAG
- seleccionar modelo y llave desde Bóveda IA
- revisar la spec antes de generar el diseño

## 4. Monitor actual

El monitor actual incluye:

- cabecera operativa del agente
- estado del runtime
- framework
- versión
- modelo base
- modo
- cantidad de tools
- acciones `Rebuild`, `Evaluar`, `Optimizar`, `Deploy` y `Abrir chat`

Pestañas:

- `Sandbox`
- `Evaluación`
- `Diseño`
- `Conocimiento`
- `Configurar`
- `Editar`

## 5. Configuración avanzada actual

La pestaña `Configurar` permite administrar:

- skills asignadas
- servidores MCP asignados
- bases de conocimiento asignadas
- política de comportamiento
- guardrails

Guardrails actuales:

- `input_block`
- `output_filter`
- `length_limit`
- `topic_restrict`

Acciones actuales:

- `block`
- `warn`
- `transform`

## 6. Observabilidad actual

La pantalla `Observabilidad` muestra:

- plan actual
- agentes activos vs límite
- invocaciones del mes vs límite
- costo acumulado
- features habilitadas
- uso del plan
- billing de los últimos 14 días
- uso por agente

El costo depende de que los modelos tengan configurado:

- `input_cost_per_million`
- `output_cost_per_million`

## 7. Límites actuales

Límites funcionales relevantes:

- el wizard actual no tiene asistencia IA en cada paso
- no existe todavía una entidad `Automation` o `Goal`
- no existe todavía historial formal de `AutomationRun`
- no hay scheduler de automatizaciones orientadas a objetivos
- no hay bandeja general de approvals para acciones sensibles
- la observabilidad no baja todavía a nivel step/run de automatización
- el flujo LangChain debe leerse como diseño persistido y validado, no como garantía de orquestación visual compleja completa

## 8. Evolución propuesta: Wizard asistido por IA

Esta evolución queda fuera del baseline actual.

Objetivo:

- agregar un advisor IA opcional al wizard para asegurar alcances alcanzables y diseños coherentes

Componentes propuestos:

- toggle `Diseño asistido por IA`
- panel lateral `Asistente de diseño`
- análisis por paso crítico
- revisión final antes de generar diseño
- sugerencias, riesgos, preguntas y score
- proposed patch aplicable al estado del wizard

Puntos críticos a revisar:

- objetivo
- alcance
- tools
- RAG/conocimiento
- modelo
- canales
- guardrails
- aprobaciones humanas

## 9. Evolución propuesta: agentes orientados a objetivos

Esta evolución también queda fuera del baseline actual.

Entidades probables:

- `Automation`
- `AutomationRun`
- `RunStep`
- `ApprovalRequest`
- `AutomationTrigger`
- `AutomationArtifact`

Capacidades esperadas:

- definición de objetivo
- planificación de pasos
- ejecución manual supervisada
- approvals para acciones sensibles
- trazabilidad por step
- observabilidad de costo y resultado
- triggers manuales, schedule o webhooks

## 10. Criterio de versionado recomendado

Para separar evolución sin confundir deploys:

- `2026-05-14-baseline`: estado funcional actual documentado
- `2026-05-wizard-ai-advisor`: próxima versión para wizard asistido
- `2026-06-goal-automations-mvp`: próxima versión para automatizaciones orientadas a objetivos

Cada nueva versión debería documentar:

- fecha
- commit base
- cambios funcionales
- cambios de schema/API
- migraciones requeridas
- riesgos y límites nuevos
- compatibilidad con deploy existente
