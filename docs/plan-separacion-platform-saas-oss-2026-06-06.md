# Plan de trabajo formal para separar Platform, SaaS y OSS

## Fecha

2026-06-06

## Objetivo

Separar Agentica en tres lineas de producto con una base comun controlada:

1. `Platform`
2. `SaaS`
3. `OSS`

La meta no es solo abrir ramas de Git, sino definir:

- que producto vive en cada linea,
- que codigo queda compartido,
- que funcionalidad se habilita o deshabilita por perfil,
- y en que orden conviene ejecutar la separacion para no romper el core.

## Decision marco

### Repositorio privado Vleeng

`Platform` y `SaaS` siguen inicialmente en el mismo repositorio privado.

Se separan por:

- `product profile`
- feature flags
- branding
- configuracion

No se recomienda forkearlos de entrada.

### Repositorio OSS publico

`OSS` se crea como repositorio aparte, publico, con despliegue propio y ownership externo a Vleeng.

El primer caso de uso y gobierno operativo sera la Universidad de la Ciudad de Buenos Aires.

### Regla de arquitectura

El runtime y el core deben seguir siendo lo mas compartidos posible.

Las diferencias entre productos deben resolverse primero por:

1. configuracion
2. flags
3. temas y branding
4. modulos opcionales

Solo despues se justifica divergencia mas fuerte.

## Vision por linea

## 1. Platform

Producto instalable para clientes de Vleeng en:

- nube privada
- VPS
- on-premise

Foco:

- crear y operar agentes empresariales
- administracion por tenant
- despliegue autogestionado
- observabilidad
- integracion empresarial

No incluye como concepto principal:

- planes comerciales
- billing por consumo
- limites `free/standard/business`

## 2. SaaS

Producto cloud operado por Vleeng para empresas usuarias.

Foco:

- autoservicio
- onboarding comercial
- limites y billing
- operacion multi-tenant administrada por Vleeng

Es la linea mas cercana al estado actual del sistema.

## 3. OSS

Producto publico, descargable y extensible por la comunidad.

Primer caso:

- Universidad de la Ciudad de Buenos Aires

Foco:

- instalacion simple
- front sobrio
- docs publicas
- extensibilidad
- sin modulos comerciales

## Alcance funcional por linea

## Compartido entre Platform y SaaS

- runtime de agentes
- modos `direct`, `react`, `crew`
- wizard clasico
- wizard asistido por chat
- KBs y RAG
- skills
- MCP
- tools built-in
- editor de flujo
- monitor del agente
- monitor de ejecuciones
- auth base
- multi-tenant backend
- observabilidad
- deploy base

## Solo SaaS

- planes
- billing
- limites de uso comerciales
- rate limiting comercial
- onboarding autoservicio
- signup comercial
- telemetria comercial
- UX mas producto/comercial

## Solo Platform

- sin billing ni planes
- sin limites comerciales
- foco admin/operacion
- soporte self-hosted
- futuro soporte enterprise:
  - SSO
  - white-label
  - backup/restore
  - dominios/config avanzada

## Solo OSS

- sin billing
- sin planes
- sin features comerciales
- UI sobria, blanco y negro, fondo oscuro
- docs de instalacion y contribucion
- defaults simples
- instalacion en server separado

## Arquitectura objetivo de separacion

## Capa 1. Core comun

Debe seguir compartiendo:

- modelos de agente
- builders
- runtime
- tools
- RAG
- skills
- MCP
- observabilidad
- editor de flujo

## Capa 2. Product profile

Se propone introducir un perfil de producto transversal:

- `saas`
- `platform`
- `oss`

Este perfil debe gobernar:

- modulos visibles,
- endpoints activos,
- branding,
- onboarding,
- billing,
- limites de uso,
- comportamiento de login/registro,
- tema visual.

## Capa 3. Modulos opcionales

Modulos que deben quedar desacoplados del core:

- billing
- plans
- usage limits comerciales
- signup comercial
- analitica comercial
- white-label enterprise

## Fases del plan

## Fase 0. Alineamiento y congelamiento

### Objetivo

Definir explicitamente que se separa y que no se separa todavia.

### Tareas

- cerrar esta matriz de producto como decision oficial
- definir nombre de ramas y naming final
- definir nombre del repo OSS publico
- definir licencia OSS
- definir branding OSS
- definir alcance inicial del deployment universitario

### Entregables

- plan aprobado
- matriz funcional validada
- naming final de repos y ramas

### Riesgos

- empezar la separacion sin licencia definida
- abrir OSS arrastrando branding o logica comercial

### Criterio de salida

- Vleeng aprueba la estrategia
- existe una decision formal de nombre, licencia y alcance OSS

## Fase 1. Introduccion de product profile

### Objetivo

Separar comportamiento de producto sin forkear runtime ni core.

### Tareas backend

- agregar `product profile` central
- crear helper de feature flags por perfil
- mapear features:
  - `FEATURE_BILLING`
  - `FEATURE_PLANS`
  - `FEATURE_USAGE_LIMITS`
  - `FEATURE_SIGNUP`
  - `FEATURE_WHITE_LABEL`
  - `FEATURE_ENTERPRISE_AUTH`
  - `FEATURE_COMMUNITY_THEME`

### Tareas frontend

- resolver perfil en boot
- condicionar secciones visibles por perfil
- separar branding/textos por perfil
- preparar temas visuales diferenciados

### Tareas de integracion

- garantizar que el perfil no rompa build ni login
- documentar defaults por perfil

### Entregables

- perfil `saas`
- perfil `platform`
- perfil `oss`
- primera capa de feature flags operativa

### Riesgos

- mezclar flags de negocio con decisiones de runtime
- introducir condicionales dispersos por todo el frontend

### Criterio de salida

- el sistema puede levantar con los tres perfiles
- las features comerciales pueden apagarse sin tocar el core

## Fase 2. Consolidacion de Platform

### Objetivo

Obtener una linea instalable privada para clientes Vleeng, limpia de logica SaaS comercial.

### Tareas

- apagar billing
- apagar planes
- apagar limites comerciales
- revisar login/onboarding para entorno administrado
- reforzar docs y scripts de deploy self-hosted
- revisar admin de tenant y accesos

### Deseable en esta fase

- preparar hooks para SSO futuro
- preparar hooks para white-label basico

### Entregables

- rama `platform`
- checklist de deploy en VPS y on-prem
- documentacion tecnica de instalacion platform

### Riesgos

- dejar dependencias residuales con billing
- mantener UI con lenguaje demasiado SaaS

### Criterio de salida

- `platform` puede desplegarse y operar sin billing ni planes
- la administracion empresarial sigue funcionando

## Fase 3. Consolidacion de SaaS

### Objetivo

Dejar la linea SaaS claramente diferenciada como servicio cloud administrado por Vleeng.

### Tareas

- validar modulo de planes
- validar modulo de billing
- validar limites comerciales
- revisar signup y onboarding
- revisar UX comercial
- revisar telemetria de cuenta

### Entregables

- rama `saas`
- comportamiento comercial desacoplado del core
- documentacion operativa de entorno SaaS

### Riesgos

- acoplar demasiado billing al runtime
- que cambios SaaS vuelvan a contaminar Platform

### Criterio de salida

- `saas` conserva todo lo comercial sin bloquear al core comun

## Fase 4. Extraccion de OSS desde Platform

### Objetivo

Crear un repositorio publico limpio, instalable y comunitario.

### Base de salida

La base recomendada para OSS es `platform`, no `saas`.

### Tareas previas al fork

- limpiar branding corporativo fuerte
- confirmar licencia
- preparar `README` publico
- preparar `CONTRIBUTING`
- preparar `CODE_OF_CONDUCT`
- preparar issue templates y roadmap inicial
- remover o simplificar modulos no aptos para publico

### Tareas de producto

- aplicar tema visual sobrio
- simplificar frontend
- revisar login y onboarding
- dejar defaults simples de instalacion
- revisar textos funcionales para comunidad

### Tareas tecnicas

- nuevo remote/repo publico
- CI basica
- documentacion de instalacion
- variables de entorno minimizadas
- validar que no haya secretos, referencias privadas ni branding reservado

### Entregables

- repo OSS publico
- documentacion publica completa
- instalacion operativa en server de la universidad

### Riesgos

- fuga de configuracion privada
- arrastre de funciones comerciales
- sobrecarga de mantenimiento si diverge demasiado temprano

### Criterio de salida

- el repo publico puede clonarse, correr e instalarse sin dependencia del contexto Vleeng

## Fase 5. Deployment universitario

### Objetivo

Instalar la rama OSS en el server separado de la universidad y dejarla operativa para evolucion comunitaria.

### Tareas

- aprovisionar server
- configurar dominio
- setear variables
- crear usuario owner universidad
- validar login
- validar wizard
- validar KBs y RAG
- validar monitor de ejecuciones
- dejar proceso de backup
- documentar gobernanza inicial del repo

### Entregables

- instancia OSS universitaria funcionando
- owner universitario operativo
- guia de administracion inicial

### Riesgos

- documentacion insuficiente para el equipo universitario
- configuracion distinta a la esperada por el repo publico

### Criterio de salida

- la universidad puede operar, probar y extender el sistema sin depender del repo privado

## Backlog tecnico inicial

## Backend

- modulo central de `product profile`
- modulo central de feature flags
- desacople de billing/plans/limits
- separacion de modulos enterprise de modulos core
- limpieza de endpoints segun perfil

## Frontend

- branding por perfil
- tema por perfil
- menu y pantallas por perfil
- login/onboarding por perfil
- limpieza UX SaaS vs Platform vs OSS

## Docs y operacion

- doc de perfiles
- doc de instalacion Platform
- doc de instalacion OSS
- doc de operacion SaaS
- licencia OSS
- contributing OSS

## Dependencias clave

Antes de abrir OSS hay que resolver:

- licencia
- nombre del repo
- branding
- alcance funcional publico inicial
- politica de aceptacion de contribuciones

Antes de separar Platform y SaaS hay que resolver:

- ubicacion del `product profile`
- mecanismo de feature flags
- frontera exacta entre core y billing

## Riesgos transversales

### Riesgo 1. Divergencia excesiva

Si las tres lineas divergen demasiado pronto, el costo de mantenimiento crece mucho.

Mitigacion:

- proteger el core comun
- evitar forks innecesarios
- separar primero por configuracion

### Riesgo 2. Logica comercial mezclada en core

Mitigacion:

- desacoplar billing y limits antes de la separacion fuerte

### Riesgo 3. OSS con demasiado peso enterprise

Mitigacion:

- nacer desde Platform
- simplificar UI y docs
- cortar features no esenciales

### Riesgo 4. Branding y ownership confusos

Mitigacion:

- definir explicitamente identidad de cada linea antes del fork OSS

## Orden recomendado de ejecucion real

1. aprobar plan y matriz
2. introducir `product profile`
3. consolidar `platform`
4. consolidar `saas`
5. forkear `oss` desde `platform`
6. desplegar OSS universitario

## Hitos

### Hito A

`product profile` operativo en el repo privado

### Hito B

`platform` corre sin billing ni planes

### Hito C

`saas` conserva todo lo comercial desacoplado del core

### Hito D

repo `oss` publico operativo

### Hito E

instancia universitaria OSS funcionando

## Recomendacion final

No conviene arrancar creando tres ramas muy distintas al mismo tiempo.

Conviene:

- primero ordenar el producto privado en `platform` + `saas` por perfil,
- despues extraer `oss` desde una base ya limpia,
- y sostener un core comun lo mas estable posible.
