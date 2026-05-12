# Manual de Usuario Agentica

Manual operativo para usuarios, builders, owners y equipos que administran agentes en Agentica.

Estado del manual: mayo de 2026  
Cobertura: funcionalidad actualmente visible en la aplicación y comportamiento operativo conocido.

## 1. Qué es Agentica

Agentica es una consola para:

- crear agentes de IA desde un wizard funcional
- elegir el framework de ejecución del agente
- probarlo en un sandbox antes de exponerlo
- conectarlo con conocimiento, tools, skills y servidores MCP
- observar uso, invocaciones y costo
- desplegar chats por enlace o por API key

En la práctica, la plataforma separa el trabajo en cuatro capas:

1. diseño del agente
2. build del runtime
3. prueba y evaluación
4. despliegue y operación

## 2. Conceptos base

### 2.1 Tenant

Un tenant representa un workspace aislado. Cada tenant tiene:

- sus propios usuarios
- sus agentes
- su bóveda de modelos y llaves
- su conocimiento y configuraciones
- su observabilidad y billing

### 2.2 Usuario

La sesión siempre pertenece a un usuario real. En distintas pantallas se muestra:

- nombre visible, si existe
- email
- user_id interno

### 2.3 Roles

Los permisos visibles en la interfaz se agrupan, de forma práctica, así:

- `viewer`: puede entrar al workspace, revisar agentes y observabilidad, pero no ve las áreas de construcción avanzada
- usuarios con permisos de edición: pueden crear agentes y usar librerías operativas
- `owner`: además de lo anterior, puede acceder a Accesos y a configuraciones globales sensibles

### 2.4 Agente

Un agente en Agentica combina:

- una `spec` funcional
- un `framework` seleccionado
- un `system prompt`
- un `graph_blueprint`
- casos de prueba
- estado operativo (`draft`, `building`, `testing`, `deployed`, `archived`)

### 2.5 Framework

Hoy Agentica trabaja principalmente con dos familias:

- `LangChain`
- `CrewAI`

No significan solo una etiqueta técnica: cambian la forma en que se construye y ejecuta el runtime.

## 3. Navegación principal

La barra lateral del workspace expone estas áreas:

- `Agentes`
- `Crear agente`
- `Observabilidad`
- `Cuenta`
- `Accesos` para owners
- `Bóveda IA`
- `Mis tools`
- `API Keys`
- `Skills`
- `MCPs`
- `Conocimiento`

Además, desde la barra lateral hay un enlace a `API Docs`.

## 4. Inicio de sesión y contexto de cuenta

## 4.1 Login

El login autentica la sesión y redirige al workspace principal.

## 4.2 Pantalla Cuenta

La sección `Cuenta` sirve para ver el contexto actual de sesión. En lugar de mostrar solo IDs internos, ahora expone:

- nombre o email del usuario actual
- tenant por nombre y slug cuando está disponible
- `tenant_id` y `user_id` como datos internos de referencia

Uso recomendado:

- validar en qué tenant estás trabajando antes de modificar agentes o librerías
- confirmar con qué identidad quedó abierta la sesión

## 5. Gestión de tenants, owners y usuarios

La sección `Accesos` es la consola administrativa del tenant y, para owners, también la puerta a capacidades más globales.

### 5.1 Qué se ve

Según los permisos, podés encontrar:

- tenant activo por nombre visible y slug
- owner actual por nombre o email
- IDs internos del tenant y del usuario como referencia secundaria
- lista de usuarios del tenant
- gestión de planes y límites para owners

### 5.2 Buen uso

- usá el nombre y email para gestión diaria
- dejá los IDs para debugging, soporte o trazabilidad técnica

## 6. Dashboard de agentes

La pantalla `Agentes` funciona como control room del workspace.

### 6.1 Qué muestra

- acceso a `Crear agente`
- acceso rápido a agentes desplegados
- listado de agentes del tenant
- framework
- modo operativo
- estado
- métricas resumidas del workspace, incluyendo costo agregado

### 6.2 Para qué sirve

- ver qué agentes existen
- filtrar o localizar los que están desplegados
- entrar rápido al monitor de un agente específico

## 7. Crear un agente con el Requirement Wizard

La creación de agentes parte del `Requirement Wizard`.

## 7.1 Estructura del wizard

El wizard cambia levemente según el modo elegido.

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

Opciones:

- `Agente simple`
- `Equipo de agentes`

Guía práctica:

- elegí `Agente simple` para asistentes, soporte, automatizaciones y tareas directas
- elegí `Equipo de agentes` para investigación, análisis multi-paso o coordinación por roles

## 7.3 Paso: Identidad

Campos principales:

- nombre del agente
- objetivo principal
- descripción
- restricciones

Consejo:

- el objetivo debe describir el problema que resuelve, no solo el nombre del área
- las restricciones conviene escribirlas en forma concreta

Ejemplo:

- "No revelar información confidencial"
- "Responder solo en español"

## 7.4 Paso: Herramientas o equipo

### En modo simple

Podés seleccionar:

- tools de librería
- custom tools activas creadas en `Mis tools`

### En modo crew

Definís:

- roles del equipo
- nombre del rol
- objetivo del rol
- backstory o contexto
- tools por rol
- permiso de delegación

## 7.5 Paso: Memoria y canales

La configuración funcional incluye:

- tipo de memoria
- canales disponibles

Opciones de memoria visibles en el dominio:

- `none`
- `session`
- `persistent`
- `summary`

Canales admitidos por la spec:

- `web_chat`
- `whatsapp`
- `telegram`
- `slack`
- `rest_api`

Nota práctica:

La presencia del canal en la spec no reemplaza la configuración real del canal en infraestructura o integración externa.

## 7.6 Paso: Modelo

El wizard toma sus modelos desde la `Bóveda IA`.

Si no hay modelos cargados, el wizard no puede ofrecer opciones útiles de ejecución.

## 7.7 Paso: Revisión

La pantalla final resume la configuración antes de generar el diseño.

Acción principal:

- `Generar diseño`

Resultado:

- se crea el `AgentDesign`
- se selecciona framework
- se genera prompt, grafo y casos de prueba
- se redirige al monitor del agente

## 8. Modos de agente

## 8.1 Agente simple

Se orienta a un solo agente con tools y runtime directo.

Casos típicos:

- soporte
- consulta documental
- automatizaciones puntuales
- copilotos internos

## 8.2 Equipo de agentes

Se orienta a varios roles especializados.

Casos típicos:

- investigación
- análisis con varias etapas
- control de calidad por revisión
- workflows con retrabajo

## 9. Bóveda IA

La `Bóveda IA` es la biblioteca cifrada de credenciales LLM del tenant.

## 9.1 Qué permite hacer

- guardar credenciales por proveedor
- definir defaults por proveedor
- cargar modelos por credencial
- definir costo de cada modelo
- exponer esos modelos al wizard y a la edición del agente

## 9.2 Proveedores admitidos en la UI

Actualmente la interfaz contempla, entre otros:

- OpenAI
- Anthropic
- OpenRouter
- DeepSeek
- Qwen / Alibaba
- Moonshot / Kimi
- Zhipu / GLM
- OpenAI compatible custom

## 9.3 Modelos por credencial

Cada clave puede tener una lista de modelos. Para cada modelo hoy podés configurar:

- `input_cost_per_million`
- `output_cost_per_million`

Esto define el costo por millón de tokens de entrada y salida.

## 9.4 Qué impacto tiene en observabilidad

Si un agente usa un modelo con costo configurado:

- las invocaciones pueden calcular costo estimado
- observabilidad y billing muestran acumulado monetario

Si el costo del modelo está en `0`:

- las invocaciones igual pueden registrarse
- el costo seguirá en cero

## 9.5 Builder Config

Para owners existe además una configuración complementaria del builder, útil para defaults operativos del sistema.

## 10. API Keys

La sección `API Keys` genera llaves públicas asociadas a un agente específico.

## 10.1 Para qué sirven

- widgets
- integraciones externas
- accesos controlados por agente

## 10.2 Cómo funcionan

Cada key:

- tiene nombre
- queda atada a un agente
- expone un prefijo visible
- puede revocarse

Importante:

- el valor completo de la key se muestra solo en el momento de creación
- después no vuelve a exhibirse completo

## 11. Mis tools

La sección `Mis tools` permite crear tools personalizadas en Python.

## 11.1 Qué podés hacer

- crear una tool
- editarla
- validar el código
- probarla con input de test
- activarla o desactivarla
- eliminarla

## 11.2 Uso esperado

Las custom tools son ideales para:

- llamar APIs internas
- encapsular lógica de negocio
- consultar servicios propios

## 11.3 Consideraciones operativas

- una tool desactivada no debería usarse en producción
- eliminar una tool que un agente usa puede romper el comportamiento del agente

## 11.4 Estado operativo de las tools de librería

La app muestra badges y ayudas breves para que no tengas que adivinar si una tool está lista o qué preparación necesita.

Estados visibles más comunes:

- `Lista`
- `Requiere credencial`
- `Requiere datasource`
- `Requiere política`
- `Requiere SMTP global`

Lectura recomendada:

- `Lista`: puede usarse sin preparar secretos o conexiones extra
- `Requiere credencial`: necesita una clave externa, por ejemplo Tavily
- `Requiere datasource`: necesita una conexión o DSN seguro
- `Requiere política`: conviene definir dominios, métodos o headers antes de habilitarla
- `Requiere SMTP global`: depende de la configuración de correo de la plataforma, no de una clave por tool

Matriz rápida:

| Capacidad | LangChain | CrewAI | Requisito principal |
|---|---|---|---|
| `calculator` | lista | lista | sin preparación adicional |
| `web_search` | lista | lista | clave Tavily en backend o config global |
| `sql_query` | operativa con setup | operativa con setup | DSN seguro y tablas permitidas |
| `rest_api_call` | operativa con setup | operativa con setup | dominios, métodos y headers permitidos |
| `send_email` | operativa con setup | operativa con setup | SMTP global válido |
| RAG | lista con conocimiento cargado | lista con conocimiento cargado | knowledge base o fuentes indexadas |
| MCP | lista con servidor activo | lista con servidor activo | servidor MCP registrado y testeado |

Si necesitás el detalle técnico y operativo más fino, revisá la [matriz de operatividad de tools](./matriz-operatividad-tools.md).

## 12. Skills

La librería `Skills` sirve para guardar capacidades reutilizables.

Una skill puede aportar:

- objetivo
- condiciones de uso
- tools relacionadas
- procedimiento
- reglas de calidad
- formato de salida
- guardrails

Uso recomendado:

- estandarizar comportamientos entre agentes
- encapsular procedimientos repetibles

## 13. MCPs

La sección `MCPs` administra servidores MCP.

## 13.1 Qué permite

- registrar un servidor
- definir endpoint
- elegir transporte (`http` o `sse`)
- definir autenticación
- testear conexión
- descubrir tools expuestas por el servidor

## 13.2 Integración con agentes

Los MCPs pueden asignarse a un agente desde el monitor, en la pestaña de configuración.

Buenas prácticas:

- registrá y testeá el servidor MCP antes de asignarlo a agentes
- verificá cuántas tools descubrió realmente el servidor
- si un agente usa MCP en producción, dejá trazado quién lo administra y qué endpoint expone

## 14. Conocimiento

La plataforma tiene dos niveles de gestión de conocimiento.

## 14.1 Bases de conocimiento

La pantalla `Conocimiento` administra knowledge bases reutilizables.

Permite:

- crear KBs
- editar nombre y descripción
- agregar URLs
- subir archivos
- eliminar fuentes
- borrar KBs completas

Estados visibles:

- vacía
- indexando
- lista
- error

## 14.2 Conocimiento por agente

Dentro del monitor de un agente existe además una pestaña `Conocimiento`.

Ahí podés:

- ver cuántos vectores tiene indexados el agente
- revisar estado de la colección
- agregar fuentes por URL
- subir archivos
- eliminar fuentes específicas

Uso recomendado:

- usar las KBs cuando querés un repositorio reutilizable
- usar el panel de conocimiento del agente cuando el contexto pertenece a ese agente puntual

## 15. Monitor del agente

El monitor es el centro operativo del agente una vez creado.

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

## 15.1 Estado visible

El monitor muestra:

- estado del runtime
- framework
- versión del diseño
- modelo base
- modo del agente
- cantidad de tools de la spec

## 16. Sandbox conversacional

La pestaña `Sandbox` sirve para probar el agente antes de desplegarlo.

## 16.1 Qué muestra ahora

Antes de la conversación aparece una cabecera de contexto con:

- nombre del agente
- id corto del agente
- usuario que está usando el sandbox
- tenant al que pertenece
- entorno
- canal

Esto ayuda a evitar pruebas "a ciegas", sobre todo cuando hay varios tenants o sesiones abiertas.

## 16.2 Cómo usarlo

1. asegurate de que el runtime esté en `ready`
2. escribí una instrucción o caso de prueba
3. observá la respuesta renderizada
4. repetí con escenarios críticos antes de desplegar

## 16.3 Cuándo no usarlo como única validación

El sandbox es muy útil, pero no reemplaza:

- evaluación formal
- prueba de canales reales
- verificación de billing

## 17. Evaluación y optimización

La pestaña `Evaluación` está pensada para benchmarkear el agente.

## 17.1 Métricas que puede mostrar

- completitud
- precisión en uso de tools
- latencia p95
- costo estimado
- score de hallucination
- score general

## 17.2 Resultado

La evaluación informa si el agente:

- está listo para producción
- requiere optimización

## 17.3 Optimización

Si el benchmark no pasa umbral, puede habilitarse `Optimizar`.

La optimización puede tocar, según el caso:

- system prompt
- temperatura
- max tokens
- tools agregadas

Después de optimizar, el sistema registra la nueva versión.

## 18. Diseño del agente

La pestaña `Diseño` reúne tres capas:

- system prompt
- decisión de framework
- flujo del agente

También muestra los casos de prueba generados.

## 18.1 System prompt

Se muestra como base operativa del runtime. En la vista se filtra el bloque Mermaid para no mezclar prompt y diagrama.

## 18.2 Decisión de framework

Explica por qué el sistema eligió ese framework para el agente.

## 18.3 Casos de prueba

Se generan casos iniciales con:

- descripción
- input
- criterio de aprobación

## 19. Flujo del agente y editor de flujo

## 19.1 Qué se ve al entrar

En la pestaña `Diseño`, el editor ya no aparece abierto de entrada.

Primero ves:

- el diagrama del flujo
- un botón `Editar flujo`

Solo al pulsarlo se abre el editor en la parte inferior de la página.

## 19.2 Fuente de verdad

El flujo real se guarda en `graph_blueprint`.

Mermaid no es la fuente de verdad. Mermaid es una vista derivada.

Esto significa:

- editar Mermaid manualmente no es el camino operativo principal
- el editor estructurado trabaja sobre nodos y edges
- al guardar, Mermaid se regenera desde el blueprint

## 19.3 Qué permite la v1 del editor

Actualmente podés:

- agregar nodos
- agregar conexiones
- editar ID, tipo, label y descripción de nodos
- editar origen, destino y condición de edges
- asignar agente en nodos `agent` del modo crew
- definir tool en nodos `tool`
- validar el flujo
- guardar el flujo

## 19.4 Tipos de nodo

La v1 usa:

- `start`
- `agent`
- `decision`
- `tool`
- `end`

## 19.5 Validación

El botón `Validar flujo` revisa estructura y reporta:

- errores
- warnings

La UI ya está endurecida para no caer si la validación llega con datos inesperados.

Además, blueprints legacy sin `edge.id` ahora pueden validarse porque el backend normaliza esos IDs.

## 19.6 Diferencia entre CrewAI y LangChain

Este punto es importante.

### En CrewAI

El `graph_blueprint` participa de forma más directa en la construcción del flujo operativo:

- tareas
- dependencias
- decisiones de revisión
- retrabajos

### En LangChain

La edición de flujo ya existe como:

- diseño persistido
- validación estructural
- base de visualización y evolución

Pero hoy no equivale necesariamente a un motor completo de ejecución por grafo del lado de LangChain. En otras palabras:

- el flujo se puede editar, validar y guardar
- pero no debe asumirse todavía que cada grafo visual se ejecute como un runtime LangGraph completo

Si necesitás precisión operativa en ese punto, conviene tratar el flujo LangChain actual como diseño gobernado y base de trabajo, no como garantía de orquestación compleja total.

## 20. Configuración avanzada por agente

La pestaña `Configurar` centraliza varias capas avanzadas.

## 20.1 Skills

Permite:

- listar skills disponibles
- asignarlas al agente
- desasignarlas

## 20.2 Servidores MCP

Permite:

- ver servidores disponibles
- asignarlos al agente
- quitarlos

## 20.3 Bases de conocimiento

Permite vincular knowledge bases al agente.

## 20.4 Behavior Policy

La política de comportamiento permite configurar, entre otros:

- tono
- condiciones de escalación
- triggers de confirmación
- requisitos de formato
- reglas custom

## 20.5 Guardrails

Los guardrails permiten crear reglas activables para controlar:

- entradas
- salidas
- temas restringidos
- keywords
- patrones
- acciones de bloqueo o tratamiento

Uso recomendado:

- definir primero unas pocas reglas críticas
- evitar sobrerregular el agente sin tener casos de prueba claros

## 21. Editar un agente ya creado

La pestaña `Editar` permite cambios rápidos sobre el agente.

## 21.1 Qué se puede modificar

- nombre visible
- system prompt
- modelo
- temperature
- max tokens

## 21.2 Fuente de modelos

Los modelos disponibles en esta pantalla salen de la `Bóveda IA`.

Si no hay modelos en la bóveda:

- no vas a poder elegir uno nuevo desde el selector

## 21.3 Efecto del guardado

Guardar cambios:

- actualiza el diseño
- reconstruye el runtime

Por eso, después de un guardado exitoso es normal volver al sandbox y validar otra vez.

## 22. Deploy y chat desplegado

## 22.1 Deploy

Desde el monitor, el botón `Deploy` marca el agente como desplegado y habilita su uso por chat público/controlado según la configuración.

## 22.2 Abrir chat

Si el agente está desplegado, aparece `Abrir chat`.

La ruta de chat standalone es del estilo:

- `/c/{agent_id}`

## 22.3 Contexto del chat desplegado

En el chat desplegado también se muestra una cabecera de contexto con:

- agente
- usuario si la sesión está autenticada
- tenant cuando puede resolverse
- entorno
- canal

En escenarios públicos con API key puede degradar con gracia y no tener todos los datos de usuario.

## 23. Observabilidad y billing

La pantalla `Observabilidad` resume el uso del workspace.

## 23.1 Qué muestra

- agentes activos
- invocaciones del mes
- costo acumulado
- features habilitadas
- uso del plan
- billing de los últimos 14 días
- uso por agente

## 23.2 Cómo leerla

### Agentes activos

Muestra consumo de capacidad del plan.

### Invocaciones del mes

Muestra cuántas llamadas se realizaron respecto del límite mensual.

### Costo acumulado

Suma costo registrado en eventos de billing.

### Billing 14 días

Muestra:

- llamadas diarias
- costo por día

### Uso por agente

Permite detectar:

- qué agentes consumen más
- qué estado tienen
- qué framework usan

## 23.3 Relación con costos de modelos

Para que el costo tenga sentido:

- el modelo debe estar configurado en la bóveda
- el modelo debe tener precio de input/output

Si no, podés ver invocaciones pero costo en cero.

## 24. Buenas prácticas de operación

## 24.1 Antes de desplegar

- corré `Rebuild`
- probá en sandbox
- revisá casos de prueba
- ejecutá `Evaluar`
- verificá observabilidad básica

## 24.2 Cuando cambiás modelo

- revisá el costo por millón de tokens
- confirmá que la key de la bóveda sea la correcta
- revalidá comportamiento y latencia

## 24.3 Cuando agregás tools

- definí una descripción muy clara
- revisá el badge de estado antes de asumir que está lista
- evitá tools con efectos ambiguos
- testealas aisladas antes de esperar que el agente las use bien

## 24.4 Cuando usás RAG

- empezá con pocas fuentes confiables
- revisá duplicados o fuentes de baja calidad
- no mezcles conocimiento muy heterogéneo sin necesidad

## 24.5 Cuando editás flujo

- usá labels simples y consistentes
- validá antes de guardar
- rebuild después de cambios importantes
- en LangChain, no asumas todavía soporte total de orquestación compleja por grafo

## 25. Troubleshooting

## 25.1 No veo modelos en el wizard o en editar agente

Revisá:

- que exista una clave en `Bóveda IA`
- que esa clave tenga modelos cargados
- que el modelo esté asociado a la key correcta

## 25.2 Las invocaciones no generan costo

Revisá:

- que el modelo esté resuelto desde la bóveda
- que el modelo tenga `input_cost_per_million` y `output_cost_per_million`
- que el runtime esté registrando billing events

## 25.3 El editor de flujo me muestra observaciones o no guarda

Revisá:

- IDs duplicados
- nodos desconectados
- edges con origen o destino inválido
- nodos `agent` sin asignación correcta en modo crew

## 25.4 El diagrama Mermaid no se ve bien

El diagrama se genera desde el blueprint. Si hay problemas:

- validá el flujo
- guardalo nuevamente
- revisá labels conflictivos

## 25.5 El sandbox responde, pero el comportamiento no es el esperado

Probá esta secuencia:

1. revisar system prompt
2. revisar tools asignadas y su estado operativo
3. revisar conocimiento, skills o MCP conectados
4. rebuildar si cambiaste flujo o configuración

## 25.6 Una tool aparece, pero no funciona como esperabas

Revisá:

- si el badge indica que requiere credencial, datasource, política o SMTP global
- si el framework del agente soporta esa capacidad en el estado actual
- si el builder ya fue recompilado con `Rebuild`
- si el backend registró errores de tool en logs de observabilidad
- si la dependencia externa existe de verdad, por ejemplo un servidor MCP activo o una knowledge base lista
2. revisar tools asignadas
3. revisar policy y guardrails
4. evaluar
5. optimizar si corresponde

## 25.6 Un chat público no muestra todos los datos de contexto

Eso puede ser normal si:

- entró por API key
- no hay sesión autenticada de usuario

En esos casos el sistema muestra el mejor contexto disponible sin inventar identidad.

## 26. Glosario breve

- `Tenant`: workspace aislado
- `Owner`: usuario con permisos máximos sobre el tenant y accesos administrativos
- `Viewer`: usuario de solo lectura
- `Spec`: definición funcional del agente
- `Design`: diseño resultante del wizard
- `Runtime`: implementación ejecutable del agente
- `Rebuild`: reconstrucción del runtime
- `Deploy`: habilitación operativa del agente desplegado
- `RAG`: recuperación de conocimiento indexado
- `MCP`: servidor de tools externas integradas por protocolo
- `Graph blueprint`: estructura real del flujo
- `Mermaid`: representación visual derivada del flujo

## 27. Alcance y límites actuales

Este manual describe la plataforma tal como existe hoy. Hay tres límites que conviene tener presentes:

1. no toda configuración visual implica automáticamente soporte completo de ejecución compleja en todos los frameworks
2. observabilidad depende de que el modelo y sus costos estén bien configurados
3. algunas capacidades avanzadas están disponibles solo para roles con permisos de edición u owner

## 28. Recomendación final de uso

Si estás arrancando con un tenant nuevo, una secuencia sana es:

1. cargar llaves y modelos en `Bóveda IA`
2. crear el agente con el wizard
3. revisar diseño y flujo
4. probar en sandbox
5. conectar conocimiento, skills o MCP si hace falta
6. evaluar
7. optimizar
8. desplegar
9. seguir uso y costo en `Observabilidad`

---

Si este manual se mantiene dentro del repo, conviene actualizarlo cada vez que cambien de forma visible:

- navegación
- wizard
- monitor
- editor de flujo
- observabilidad
- permisos
