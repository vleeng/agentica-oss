# Manual de Usuario Agentica

Manual operativo para usuarios, builders, developers y owners que administran agentes en Agentica.

Estado del manual: mayo de 2026  
Cobertura: interfaz y comportamiento operativo visibles hoy en la aplicación.

## 1. Qué es Agentica

Agentica es una consola para diseñar, probar, configurar y operar agentes de IA dentro de un workspace aislado.

La plataforma hoy permite:

- crear agentes desde un wizard guiado
- elegir el modo del agente: simple o equipo de agentes
- seleccionar modelo y llave desde la Bóveda IA
- asignar tools, skills, conocimiento y servidores MCP
- probar el runtime en sandbox antes de desplegar
- evaluar y optimizar el agente
- desplegar chats y generar API keys por agente
- seguir uso, costo y límites del plan

En la práctica, el flujo operativo se organiza en cuatro capas:

1. diseño del agente
2. build del runtime
3. prueba y ajuste
4. despliegue y operación

## 2. Conceptos base

### 2.1 Tenant

Un tenant representa un workspace aislado. Cada tenant tiene:

- sus propios usuarios
- sus agentes
- su Bóveda IA
- sus skills, tools, MCPs y conocimiento
- su observabilidad, límites y consumo

### 2.2 Usuario

La sesión siempre pertenece a un usuario real. En la interfaz pueden verse:

- nombre visible
- email
- rol
- `user_id` interno

### 2.3 Roles

Los roles visibles hoy son:

- `viewer`: acceso de lectura; puede ver dashboard, observabilidad y cuenta
- `developer`: puede crear agentes y operar las pantallas de construcción
- `owner`: además de lo anterior, accede a `Accesos`

Importante:

- la UI oculta varias pantallas de builder para `viewer`
- la sección `Accesos` solo aparece para `owner`
- dentro de `Accesos`, algunas capacidades globales adicionales dependen de permisos administrativos más altos del backend

### 2.4 Agente

Un agente en Agentica combina:

- una `spec` funcional
- un modo (`single` o `crew`)
- un framework seleccionado por el sistema
- un `system_prompt`
- un `graph_blueprint`
- casos de prueba
- un estado operativo

Estados visibles más comunes:

- `draft`
- `building`
- `testing`
- `deployed`
- `archived`

### 2.5 Framework

Hoy Agentica trabaja principalmente con dos familias:

- `LangChain`
- `CrewAI`

No es solo una etiqueta técnica. El framework afecta:

- cómo se construye el runtime
- qué tools o flujos tienen soporte pleno
- cómo se interpreta el diseño interno del agente

## 3. Navegación principal

La barra lateral expone estas áreas principales:

- `Agentes`
- `Crear agente`
- `Observabilidad`
- `Cuenta`
- `Accesos` para owners
- `Boveda IA`
- `Mis tools`
- `API Keys`

Además, la consola separa una sección `Libreria` con:

- `Skills`
- `MCPs`
- `Conocimiento`

En el pie de la barra lateral también aparecen:

- `API Docs`
- `Cerrar sesion`

## 4. Inicio de sesión y cuenta

### 4.1 Login

El login autentica la sesión y redirige al workspace.

Si olvidás la contraseña, el flujo de recuperación parte desde la pantalla de login.

### 4.2 Cuenta

La pantalla `Cuenta` hoy sirve para dos cosas:

- validar qué identidad está activa
- cambiar la contraseña del usuario actual

La vista muestra:

- nombre o email del usuario autenticado
- rol actual
- tenant por nombre o slug
- `tenant_id` interno
- `user_id` interno

La sección de seguridad permite:

- ingresar contraseña actual
- definir nueva contraseña
- confirmar la nueva contraseña

## 5. Accesos, tenants y usuarios

La sección `Accesos` es la consola administrativa visible para `owner`.

Según permisos efectivos del backend, hoy puede incluir tres capas:

1. gestión del equipo del tenant actual
2. alta de tenants nuevos
3. administración global de planes y solicitudes free

### 5.1 Equipo del tenant actual

La primera parte de `Accesos` muestra:

- tenant actual
- owner o usuario autenticado
- rol actual
- usuarios cargados en el tenant
- conteo de developers y viewers

También permite crear usuarios nuevos dentro del tenant con:

- email
- nombre visible
- password inicial
- rol `developer` o `viewer`

### 5.2 Alta de tenant nuevo

Cuando la cuenta tiene permisos administrativos más altos, `Accesos` también permite crear un tenant nuevo con:

- nombre
- slug
- plan inicial
- owner email
- owner nombre
- owner password

Después del alta, la pantalla muestra:

- `tenant_id`
- `user_id` del owner inicial
- rol asignado

### 5.3 Solicitudes free

La consola global también puede incluir una bandeja para:

- listar solicitudes de cuenta free
- aprobarlas
- rechazarlas

### 5.4 Mapa global de tenants

Si está habilitado, el owner/admin puede ver un overview global con:

- tenants existentes
- plan activo
- owner
- agentes usados vs límite
- invocaciones usadas vs límite
- usuarios cargados por tenant

### 5.5 Límites por plan

La capa global de planes permite ajustar:

- nombre visible del plan
- máximo de agentes
- máximo de invocaciones mensuales
- precio en USD
- feature flags como `rag` y `crew`

## 6. Dashboard de agentes

La pantalla `Agentes` funciona como control room del workspace.

### 6.1 Qué muestra

- hero principal con acceso a `Crear agente`
- botón rápido para filtrar desplegados
- panorama rápido del workspace
- métricas de invocaciones, tokens y costo total
- buscador por nombre, framework, estado o modo
- listado de agentes

### 6.2 Datos por agente

Cada tarjeta de agente muestra:

- nombre
- estado
- framework
- modo
- fecha de alta
- acceso a `Abrir monitor`

### 6.3 Acciones disponibles

Según permisos, desde el dashboard se puede:

- crear agente
- abrir su monitor
- eliminarlo

## 7. Crear un agente con el Requirement Wizard

La creación de agentes parte del `Requirement Wizard`.

## 7.1 Estructura del wizard

### Modo simple

Pasos:

1. tipo de agente
2. identidad
3. herramientas
4. memoria y canales
5. modelo
6. revisión

### Modo equipo

Pasos:

1. tipo de agente
2. identidad
3. equipo de agentes
4. memoria y canales
5. modelo
6. revisión

## 7.2 Paso: Tipo de agente

Opciones visibles:

- `Agente simple`
- `Equipo de agentes`

Uso recomendado:

- `Agente simple` para asistentes, soporte, automatizaciones y consultas
- `Equipo de agentes` para investigación, análisis multi-paso o workflows largos

## 7.3 Paso: Identidad

Campos principales:

- nombre del agente
- objetivo principal
- descripción
- restricciones

Las restricciones se cargan una por línea.

Ejemplos:

- `No revelar información confidencial`
- `Responder solo en español`

## 7.4 Paso: Herramientas o equipo

### En modo simple

Podés seleccionar:

- tools built-in de librería
- tools custom activas creadas en `Mis tools`

La UI hoy también muestra por cada tool:

- categoría
- readiness o estado operativo
- nivel de soporte para LangChain
- hint de configuración cuando necesita setup

Estados de compatibilidad visibles más comunes:

- lista
- limitada
- no soportada

Estados de readiness visibles más comunes:

- `Lista`
- `Requiere credencial`
- `Requiere datasource`
- `Requiere politica`
- `Requiere SMTP global`

### En modo crew

El paso cambia a `Equipo de agentes` y permite definir roles con:

- nombre del rol
- objetivo
- contexto o backstory
- tools por rol
- delegación

## 7.5 Paso: Memoria y canales

La configuración funcional hoy permite definir:

- canales de despliegue
- tipo de memoria
- si el agente arranca con RAG habilitado

Canales visibles:

- `web_chat`
- `whatsapp`
- `telegram`
- `slack`
- `rest_api`

Notas prácticas:

- `whatsapp` requiere Twilio
- `telegram` requiere bot token
- `slack` aparece marcado como `v2`
- `rest_api` sirve para uso solo por API

Opciones de memoria visibles:

- `none`
- `session`
- `persistent`

La UI además incluye un check de `Habilitar RAG`.

## 7.6 Paso: Modelo

El wizard toma modelos desde la `Boveda IA`.

La pantalla hoy permite definir:

- modelo LLM
- llave del proveedor
- temperatura
- máximo de tokens

Comportamiento importante:

- si no hay llaves cargadas, el wizard no puede ofrecer modelos
- si una llave es default para ese proveedor, puede usarse automáticamente

## 7.7 Paso: Revisión

La pantalla final resume:

- nombre
- modo
- objetivo
- herramientas
- memoria
- canales
- RAG
- modelo
- temperatura

Acción principal:

- `Generar diseño`

Resultado esperado:

- se crea el diseño del agente
- el sistema elige framework
- se genera system prompt, flujo y casos de prueba
- se redirige al monitor

## 8. Boveda IA

La `Boveda IA` es la biblioteca cifrada de credenciales LLM del tenant.

## 8.1 Qué permite hacer

- guardar credenciales por proveedor
- nombrarlas con alias operativos
- marcar una credencial default por proveedor
- agregar modelos por credencial
- definir costo input/output por millón de tokens

## 8.2 Proveedores visibles en la UI

Actualmente la interfaz contempla:

- OpenAI
- Anthropic
- OpenRouter
- DeepSeek
- Qwen / Alibaba
- Moonshot / Kimi
- Zhipu / GLM
- OpenAI compatible custom

## 8.3 Modelos por credencial

Cada credencial puede tener su propia lista de modelos.

Para cada modelo hoy se configura:

- `input_cost_per_million`
- `output_cost_per_million`

Esto impacta directamente en observabilidad y billing.

## 8.4 Defaults por proveedor

Si un proveedor tiene una llave marcada como default:

- el wizard y el runtime pueden usarla sin que tengas que elegirla siempre a mano

## 8.5 Builder Config

Para cuentas con permisos suficientes aparece además `BuilderConfigPanel`, usado para defaults operativos del sistema.

## 9. API Keys

La sección `API Keys` genera llaves públicas asociadas a un agente específico.

## 9.1 Para qué sirven

- widgets
- integraciones externas
- accesos controlados por agente

## 9.2 Cómo funciona hoy

Para crear una key definís:

- agente
- nombre de la key

Cada key queda:

- restringida al agente seleccionado
- listada con prefijo visible
- revocable

Importante:

- el valor completo se muestra una sola vez al crearla
- después solo queda visible el prefijo

## 10. Mis tools

La sección `Mis tools` permite crear tools personalizadas en Python.

## 10.1 Qué podés hacer

- crear una tool nueva
- editar una existente
- validar el código
- definir `config_schema` en JSON
- probar la tool con input y config de test
- activarla o desactivarla
- eliminarla

## 10.2 Restricciones operativas visibles

La plantilla de la app deja claro que una custom tool debe definir:

- `TOOL_NAME`
- `TOOL_DESCRIPTION`
- `async def run(input, config)`

Además, la interfaz guía sobre imports permitidos y no permitidos.

## 10.3 Buen uso

Las custom tools son ideales para:

- APIs internas
- lógica de negocio propia
- automatizaciones específicas del tenant

Importante:

- una tool inactiva no debería asignarse operativamente
- eliminar una tool usada por un agente puede romper su comportamiento

## 11. Skills

La librería `Skills` sirve para guardar capacidades reutilizables.

Cada skill hoy puede incluir:

- nombre
- descripción
- objetivo
- condiciones de uso
- procedimiento
- tools habilitadas
- reglas de calidad
- formato de salida
- guardrails

Uso recomendado:

- estandarizar comportamientos entre agentes
- encapsular procedimientos repetibles
- reutilizar reglas de respuesta y de calidad

## 12. MCPs

La sección `MCPs` administra servidores MCP.

## 12.1 Qué permite

- registrar un servidor
- editarlo
- elegir transporte `sse` o `http`
- definir autenticación
- probar conexión
- listar tools descubiertas
- eliminar el servidor

## 12.2 Autenticación visible

Opciones disponibles:

- `none`
- `bearer`
- `basic`

## 12.3 Integración con agentes

Los MCPs pueden asignarse desde la pestaña `Configurar` del monitor.

Buenas prácticas:

- registrá primero el servidor
- probá conexión
- verificá cuántas tools descubrió realmente

## 13. Conocimiento

La plataforma hoy trabaja con dos niveles de conocimiento:

1. bases reutilizables del tenant
2. conocimiento propio del agente

## 13.1 Bases de conocimiento compartidas

La pantalla `Conocimiento` de librería administra KBs reutilizables.

Permite:

- crear KBs
- editar nombre y descripción
- agregar fuentes por URL
- subir archivos
- eliminar fuentes
- borrar KBs completas

Estados visibles:

- `empty`
- `indexing`
- `ready`
- `error`

Por defecto, al crear una KB la app genera una `rag_spec` base con embeddings y parámetros estándar.

## 13.2 Conocimiento por agente

Dentro del monitor existe además una pestaña `Conocimiento`.

Ahí podés trabajar sobre el knowledge store específico del agente para:

- ver fuentes indexadas
- ver estado y métricas
- agregar URLs
- subir archivos
- quitar fuentes puntuales

## 13.3 Cuándo usar cada nivel

- usá KBs compartidas cuando querés reutilizar fuentes entre varios agentes
- usá conocimiento por agente cuando el contexto pertenece solo a un agente puntual

## 14. Monitor del agente

El monitor es el centro operativo una vez creado el agente.

Pestañas principales:

- `Sandbox`
- `Evaluación`
- `Diseño`
- `Conocimiento`
- `Configurar`
- `Editar`

Acciones superiores:

- `Rebuild`
- `Evaluar`
- `Optimizar`
- `Deploy`
- `Abrir chat` si ya está desplegado

## 14.1 Qué muestra arriba

La cabecera del monitor hoy muestra:

- estado del runtime
- framework
- versión del diseño
- nombre del agente
- objetivo
- modelo base
- modo
- cantidad de tools

## 15. Sandbox conversacional

La pestaña `Sandbox` sirve para probar el agente antes de desplegarlo.

## 15.1 Contexto visible

Antes del chat aparece una cabecera con:

- nombre del agente
- `agent_id`
- tenant
- usuario autenticado
- entorno
- canal

Hoy el sandbox se presenta como:

- entorno `Sandbox interno`
- canal `Web chat`

## 15.2 Cómo usarlo

1. esperá a que el runtime esté en `Runtime listo`
2. escribí una instrucción o caso de prueba
3. revisá respuesta, trazas y mensajes de estado
4. repetí escenarios críticos antes de desplegar

## 15.3 Qué no reemplaza

El sandbox no reemplaza por sí solo:

- evaluación formal
- validación de costo
- pruebas de canal real

## 16. Evaluación y optimización

La pestaña `Evaluación` sirve para benchmarkear el agente.

## 16.1 Métricas visibles

Hoy puede mostrar:

- `Completitud`
- `Tools`
- `Latencia p95`
- `Costo estimado`
- `Hallucination`
- `Score general`

## 16.2 Resultado

La evaluación clasifica el estado como:

- `Listo para producción`
- `Requiere optimización`

## 16.3 Optimización

Si el benchmark no pasa umbral, se habilita `Optimizar`.

La optimización puede tocar:

- system prompt
- temperatura
- max tokens
- tools agregadas

Al aplicarse, el monitor muestra la nueva versión y el patch resultante.

## 17. Diseño del agente

La pestaña `Diseño` reúne:

- system prompt
- justificación del framework
- diagrama Mermaid
- casos de prueba
- editor de flujo

## 17.1 System prompt

La UI filtra el bloque Mermaid para mostrar el prompt operativo sin mezclarlo con el diagrama.

## 17.2 Decisión de framework

Se muestra una justificación textual de por qué el sistema eligió ese framework.

## 17.3 Casos de prueba

Los casos iniciales incluyen:

- descripción
- input
- criterio de aprobación

## 18. Flujo del agente y editor de flujo

## 18.1 Qué se ve al entrar

En la pestaña `Diseño`, primero ves:

- el diagrama del flujo
- un botón `Editar flujo`

El editor no queda abierto por defecto.

## 18.2 Fuente de verdad

El flujo real se guarda en `graph_blueprint`.

Mermaid no es la fuente de verdad. Es una vista derivada.

Esto implica:

- no conviene editar Mermaid como mecanismo principal
- el editor trabaja sobre nodos y conexiones estructuradas
- al guardar, Mermaid se regenera

## 18.3 Qué permite la versión actual

Hoy podés:

- agregar nodos
- agregar conexiones
- editar ID, tipo, label y descripción
- editar origen, destino y condición de edges
- asignar agente en nodos `agent` del modo crew
- asignar tool en nodos `tool`
- validar flujo
- guardar flujo

## 18.4 Tipos de nodo visibles

- `start`
- `agent`
- `decision`
- `tool`
- `end`

## 18.5 Validación

El botón `Validar flujo` revisa estructura y puede devolver:

- errores
- warnings

## 18.6 Diferencia entre CrewAI y LangChain

### En CrewAI

El `graph_blueprint` participa de forma más directa en la construcción del flujo operativo.

### En LangChain

El flujo hoy debe leerse como diseño persistido y validado, pero no como garantía automática de una orquestación gráfica compleja completa en todos los casos.

Lectura recomendada:

- en CrewAI, tratá el flujo como parte más ejecutiva del diseño
- en LangChain, tratá el flujo como base visual y estructural gobernada

## 19. Configurar un agente

La pestaña `Configurar` centraliza capacidades avanzadas por agente.

Hoy incluye cinco bloques:

- skills
- servidores MCP
- bases de conocimiento
- política de comportamiento
- guardrails

## 19.1 Skills

Permite:

- listar skills disponibles
- asignarlas
- desasignarlas

La UI muestra también herramientas asociadas cuando la skill las tiene.

## 19.2 Servidores MCP

Permite:

- ver servidores registrados
- asignarlos al agente
- quitarlos

Además muestra:

- endpoint
- cantidad de tools descubiertas
- tipo de transporte

## 19.3 Bases de conocimiento

Permite:

- ver KBs compartidas
- asignarlas al agente
- quitarlas

## 19.4 Política de comportamiento

Hoy la policy permite configurar:

- tono
- condiciones de escalación
- triggers de confirmación
- requisitos de formato
- reglas adicionales

## 19.5 Guardrails

Los guardrails hoy permiten crear reglas sobre:

- inputs
- outputs
- longitud
- temas restringidos

Tipos visibles:

- `input_block`
- `output_filter`
- `length_limit`
- `topic_restrict`

Acciones visibles:

- `block`
- `warn`
- `transform`

Uso recomendado:

- empezar por pocas reglas críticas
- probarlas antes de sobre-regular el agente

## 20. Editar un agente ya creado

La pestaña `Editar` permite cambios rápidos sobre el diseño.

Los cambios operativos más comunes son:

- nombre visible
- system prompt
- modelo
- temperatura
- max tokens

Importante:

- los modelos disponibles salen de la `Boveda IA`
- si no hay modelos cargados, no vas a poder seleccionar uno nuevo
- guardar cambios reconstruye el runtime

## 21. Deploy y chat desplegado

## 21.1 Deploy

Desde el monitor, `Deploy` deja al agente en estado desplegado.

## 21.2 Abrir chat

Si el agente ya fue desplegado, aparece `Abrir chat`.

La ruta standalone hoy es del estilo:

- `/c/{agent_id}`

## 21.3 Contexto del chat desplegado

El chat standalone también muestra cabecera de contexto con:

- agente
- usuario si hay sesión
- tenant cuando puede resolverse
- entorno
- canal

En escenarios públicos o con API key, el sistema puede degradar con gracia si no tiene identidad completa del usuario.

## 22. Observabilidad y billing

La pantalla `Observabilidad` resume el uso del workspace.

## 22.1 Qué muestra

- plan actual
- agentes activos vs límite
- invocaciones del mes vs límite
- costo acumulado
- features habilitadas
- uso del plan
- billing de los últimos 14 días
- uso por agente

## 22.2 Cómo leerla

### Agentes activos

Mide capacidad consumida respecto del máximo del plan.

### Invocaciones del mes

Mide uso mensual respecto del límite del plan.

### Features habilitadas

Hoy la UI destaca principalmente:

- `RAG`
- `Multi-agente`

### Billing 14 días

La pantalla muestra:

- llamadas por día
- costo por día
- total agregado del período cargado

### Uso por agente

Permite detectar:

- qué agentes consumen más
- qué estado tienen
- qué framework usan

## 22.3 Relación con costos de modelos

Para que el costo tenga lectura útil:

- el modelo debe resolverse desde la Bóveda IA
- el modelo debe tener precio input/output cargado

Si no, podés ver invocaciones pero costo en cero.

## 23. Buenas prácticas de operación

## 23.1 Antes de desplegar

- corré `Rebuild`
- probá en sandbox
- revisá casos de prueba
- ejecutá `Evaluar`
- verificá observabilidad básica

## 23.2 Cuando cambiás modelo

- revisá costos por millón de tokens
- confirmá qué llave del proveedor va a usarse
- revalidá latencia y comportamiento

## 23.3 Cuando agregás tools

- escribí descripciones claras
- mirá readiness y compatibilidad antes de asumir que una tool está lista
- testeá primero las custom tools de forma aislada

## 23.4 Cuando usás RAG

- empezá con pocas fuentes confiables
- revisá duplicados
- evitá mezclar conocimiento heterogéneo sin necesidad

## 23.5 Cuando editás flujo

- usá labels simples
- validá antes de guardar
- hacé rebuild después de cambios importantes
- en LangChain, no asumas soporte total de orquestación visual compleja

## 24. Troubleshooting

## 24.1 No veo modelos en el wizard o en editar agente

Revisá:

- que exista una credencial en `Boveda IA`
- que esa credencial tenga modelos cargados
- que el proveedor tenga una llave usable

## 24.2 Las invocaciones no generan costo

Revisá:

- que el modelo se resuelva desde la Bóveda
- que el modelo tenga `input_cost_per_million`
- que el modelo tenga `output_cost_per_million`

## 24.3 El monitor no queda listo

Revisá:

- si el `Rebuild` terminó bien
- si la configuración del modelo es válida
- si alguna tool o integración externa está fallando

## 24.4 El editor de flujo muestra errores o no guarda

Revisá:

- IDs duplicados
- nodos desconectados
- edges con origen o destino inválido
- nodos `agent` sin asignación correcta en modo crew

## 24.5 El sandbox responde, pero el comportamiento no es el esperado

Probá esta secuencia:

1. revisar system prompt
2. revisar tools asignadas y su estado operativo
3. revisar skills, conocimiento y MCP conectados
4. rebuildar si cambiaste diseño o configuración
5. correr evaluación

## 24.6 Una tool aparece, pero no funciona como esperabas

Revisá:

- si la tool requiere credencial, datasource, política o SMTP global
- si el framework del agente soporta esa capacidad
- si el agente fue rebuildado después del cambio
- si la dependencia externa existe de verdad

## 24.7 Una KB o fuente queda indexando

Revisá:

- si la URL es accesible
- si el archivo tiene formato soportado
- si la KB pasó a `ready` después de la ingesta

## 24.8 Un chat público no muestra todos los datos de contexto

Eso puede ser normal si:

- entró por API key
- no hay sesión autenticada

## 25. Glosario breve

- `Tenant`: workspace aislado
- `Viewer`: usuario de lectura
- `Developer`: usuario con acceso de construcción
- `Owner`: usuario con acceso a administración del tenant
- `Spec`: definición funcional del agente
- `Design`: diseño generado por el wizard
- `Runtime`: implementación ejecutable del agente
- `Rebuild`: reconstrucción del runtime
- `Deploy`: habilitación operativa del chat desplegado
- `RAG`: recuperación de conocimiento indexado
- `MCP`: protocolo para tools externas expuestas por servidor
- `Graph blueprint`: estructura real del flujo
- `Mermaid`: representación visual derivada del flujo

## 26. Alcance y límites actuales

Este manual describe la plataforma tal como existe hoy. Conviene tener presentes estos límites:

1. no toda configuración visual implica ejecución compleja completa en todos los frameworks
2. observabilidad económica depende de que los modelos y sus costos estén bien cargados
3. varias pantallas y acciones cambian según rol y permisos efectivos del backend

## 27. Secuencia recomendada de uso

Si estás arrancando con un tenant nuevo, una secuencia sana hoy es:

1. cargar credenciales y modelos en `Boveda IA`
2. crear el agente con el wizard
3. revisar diseño y flujo
4. probar en sandbox
5. conectar skills, conocimiento o MCP si hace falta
6. evaluar
7. optimizar si corresponde
8. desplegar
9. seguir uso y costo en `Observabilidad`

---

Si este manual se mantiene dentro del repo, conviene actualizarlo cada vez que cambien de forma visible:

- navegación
- wizard
- monitor
- editor de flujo
- librerías
- observabilidad
- permisos
