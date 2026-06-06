# Matriz de implementacion del product profile 2026-06-06

## Objetivo

Traducir el plan de separacion `Platform / SaaS / OSS` a una matriz de trabajo ejecutable por modulo.

Esta matriz sirve para arrancar la Fase 1:

- introducir `product profile`
- desacoplar modulos comerciales del core
- preparar el fork OSS desde una base limpia

## Regla general

Antes de separar por ramas o repos, cada modulo debe clasificarse asi:

- `Core compartido`
- `SaaS only`
- `Platform only`
- `OSS adaptado`

Y luego resolverse tecnicamente por:

1. feature flags
2. configuracion
3. branding o tema
4. modulos opcionales

## Matriz por modulo

| Modulo | Core compartido | SaaS | Platform | OSS | Accion tecnica principal |
|---|---|---|---|---|---|
| Runtime de agentes | Si | Si | Si | Si | mantener comun; no bifurcar runtime |
| Modos `direct/react/crew` | Si | Si | Si | Si | mantener comun; solo ajustar defaults por perfil |
| Wizard clasico | Si | Si | Si | Si | separar branding y textos por perfil |
| Wizard por chat | Si | Si | Si | Si | parametrizar prompts, tono y ejemplos por perfil |
| Knowledge Bases y RAG | Si | Si | Si | Si | mantener comun; variar copy y onboarding |
| Skills | Si | Si | Si | Si | mantener comun |
| MCP | Si | Si | Si | Si | mantener comun |
| Tools built-in | Si | Si | Si | Si | mantener comun; flags solo para tools sensibles si hiciera falta |
| Editor de flujo | Si | Si | Si | Si | mantener comun; revisar tema visual en OSS |
| Monitor del agente | Si | Si | Si | Si | mantener comun |
| Monitor de ejecuciones | Si | Si | Si | Si | mantener comun; agregar metricas por perfil mas adelante si hiciera falta |
| Multi-tenant backend | Si | Si | Si | Si | mantener comun; defaults simples en OSS |
| Auth base | Si | Si | Si | Si | mantener comun; variar signup/onboarding |
| Accesos por tenant | Si | Si | Si | Si | mantener comun; simplificar UI en OSS |
| Billing | No | Si | No | No | extraer modulo y apagarlo por feature flag |
| Planes comerciales | No | Si | No | No | desacoplar del core y condicionar UI/endpoints |
| Usage limits comerciales | No | Si | No | No | desacoplar middleware del core y activarlo por perfil |
| Rate limiting comercial | No | Si | No | No | separar limite operativo de limite comercial |
| Signup autoservicio | No | Si | Opcional | Opcional/minimo | flag de producto y flujo distinto en frontend |
| White-label | No | No | Si | No | feature enterprise separada |
| SSO enterprise | No | Futuro | Si | No | hook de integracion opcional, fuera del core inicial |
| Telemetria comercial | No | Si | No | No | encapsular analytics y apagarlo por perfil |
| Frontend premium | No | Si | Medio | No | sistema de tema y branding por perfil |
| Frontend sobrio negro | No | No | No | Si | tema OSS dedicado |
| Documentacion publica | No | Parcial | Parcial | Si | paquete docs separado para OSS |
| Instalacion on-prem | No | No | Si | Si | docs y scripts especificos |
| Licencia open source | No | No | No | Si | resolver antes del fork |

## Modulos y tareas detalladas

## 1. Product profile central

### Objetivo

Introducir una fuente unica de verdad para el perfil:

- `saas`
- `platform`
- `oss`

### Backend

- crear modulo central, por ejemplo:
  - `app/core/product_profile.py`
- exponer:
  - perfil activo
  - feature flags derivadas
  - helpers de consulta

### Frontend

- resolver perfil en boot
- propagarlo por contexto global
- habilitar condicionales de UI de forma centralizada

### Resultado esperado

El sistema puede correr con un perfil activo sin cambios manuales de codigo dispersos.

## 2. Feature flags de negocio

### Flags iniciales sugeridas

- `FEATURE_BILLING`
- `FEATURE_PLANS`
- `FEATURE_USAGE_LIMITS`
- `FEATURE_SIGNUP`
- `FEATURE_ENTERPRISE_AUTH`
- `FEATURE_WHITE_LABEL`
- `FEATURE_COMMUNITY_THEME`

### Backend

- condicionar endpoints y servicios
- evitar que billing o planes entren al runtime de agentes

### Frontend

- ocultar entradas de menu
- ocultar componentes
- adaptar onboarding

### Resultado esperado

Las features comerciales pueden apagarse por perfil sin romper login, wizard ni runtime.

## 3. Billing y planes

### Estado deseado

- activo solo en `saas`
- inexistente funcionalmente en `platform`
- inexistente en `oss`

### Tareas

- localizar todos los puntos donde hoy impactan planes y limites
- separarlos del core
- apagar UI y API segun perfil

### Dependencia

Requiere `product profile` y `feature flags` primero.

## 4. Signup y onboarding

### SaaS

- signup autoservicio
- onboarding comercial

### Platform

- alta administrada
- onboarding mas tecnico

### OSS

- flujo minimo
- documentacion simple de instalacion

### Tareas

- separar flujos de login/registro
- separar textos del login
- separar CTA de creacion de cuenta

## 5. Branding y tema

### SaaS

- visual mas producto/comercial

### Platform

- visual serio, corporativo, administrable

### OSS

- sobrio
- blanco y negro
- fondo oscuro
- poco ornamento

### Tareas

- crear sistema de tema por perfil
- separar logos, nombre visible y textos
- no hardcodear branding Vleeng dentro del core

## 6. OSS readiness

### Objetivo

Preparar el producto para un fork publico limpio.

### Tareas tecnicas

- identificar referencias privadas
- limpiar branding corporativo reservado
- revisar secretos y defaults
- agregar docs publicas
- preparar licencia
- preparar `CONTRIBUTING`

### Resultado esperado

El repo OSS puede publicarse sin arrastrar modulos comerciales ni informacion privada.

## 7. Platform readiness

### Objetivo

Dejar un producto instalable para clientes Vleeng.

### Tareas

- sacar billing y planes
- reforzar deploy self-hosted
- revisar operacion de tenant
- preparar hooks para:
  - SSO
  - white-label
  - backup/restore

### Resultado esperado

`Platform` puede desplegarse como producto empresarial sin logica SaaS comercial.

## 8. SaaS readiness

### Objetivo

Conservar el producto cloud comercial sin contaminar el core comun.

### Tareas

- encapsular billing
- encapsular planes
- encapsular limites
- encapsular telemetria comercial

### Resultado esperado

`SaaS` conserva su valor comercial sin obligar a `Platform` u `OSS` a cargar esa complejidad.

## Orden de implementacion recomendado

## Tramo A. Infraestructura de perfil

1. crear `product profile`
2. crear feature flags
3. exponer perfil al frontend

## Tramo B. Desacople comercial

4. billing
5. planes
6. usage limits
7. signup comercial

## Tramo C. Branding y UX

8. tema por perfil
9. textos por perfil
10. login/onboarding por perfil

## Tramo D. Salida de lineas

11. consolidar `platform`
12. consolidar `saas`
13. preparar `oss`
14. fork publico

## Backlog tecnico concreto

## Backend

- crear `product_profile.py`
- crear `feature_flags.py`
- desacoplar plan limits comerciales del core
- desacoplar billing de servicios compartidos
- desacoplar signup comercial
- preparar feature `enterprise_auth`

## Frontend

- crear contexto de perfil
- crear tema por perfil
- crear branding por perfil
- ocultar modulos por perfil
- separar copy del login y onboarding

## Documentacion

- doc de perfiles
- doc de instalacion platform
- doc de instalacion OSS
- doc operativa SaaS
- doc de fork publico OSS

## Riesgos operativos

### 1. Flags dispersas

Si cada pantalla resuelve su propia logica de perfil, el mantenimiento se vuelve caotico.

Mitigacion:

- resolver perfil y features de forma centralizada.

### 2. Billing mezclado con runtime

Mitigacion:

- separar billing del core antes de abrir nuevas lineas.

### 3. OSS demasiado complejo

Mitigacion:

- partir desde `platform`
- simplificar onboarding y tema
- revisar dependencias innecesarias

### 4. Platform sin identidad propia

Mitigacion:

- limpiar lenguaje SaaS y reforzar narrativa de producto instalable.

## Criterio de salida de Fase 1

La Fase 1 se considera cumplida cuando:

- existe `product profile` operativo,
- las features comerciales se apagan por perfil,
- frontend y backend responden consistentemente al perfil activo,
- el core de agentes sigue intacto,
- y `platform` puede empezar a consolidarse sin cargar billing ni planes.

## Recomendacion final

La primera implementacion no deberia tocar runtime de agentes salvo para exponer perfil y feature flags si fuera necesario.

El mayor valor inicial esta en:

- desacoplar negocio del core,
- centralizar branding y visibilidad de modulos,
- y dejar la base lista para que `platform` y luego `oss` salgan ordenados.
