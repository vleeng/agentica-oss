# Matriz de Operatividad de Tools

Referencia rápida para producto, soporte y usuarios avanzados sobre el estado real de las capacidades visibles en Agentica.

Estado del documento: mayo de 2026

## 1. Cómo leer esta matriz

- `Lista`: la capacidad está lista para usarse en el framework indicado, siempre que sus dependencias externas existan.
- `Operativa con setup`: la tool funciona, pero requiere una configuración previa concreta.
- `No aplica`: la capacidad no está pensada como tool de librería en ese nivel.

## 2. Tools de librería

| Tool | Estado general | LangChain | CrewAI | Requisito principal | Nota operativa |
|---|---|---|---|---|---|
| `calculator` | Lista | Lista | Lista | Ninguno | No requiere credenciales ni configuración extra. |
| `web_search` | Operativa con setup | Lista | Lista | Clave Tavily en backend o config global | Si falta la credencial, falla con mensaje claro. |
| `sql_query` | Operativa con setup | Lista | Lista | DSN seguro + tablas permitidas | Solo acepta `SELECT` y valida tablas permitidas. |
| `rest_api_call` | Operativa con setup | Lista | Lista | Política de dominios, métodos y headers | Bloquea destinos privados o sin política explícita. |
| `send_email` | Operativa con setup | Lista | Lista | SMTP global válido | Usa el mailer global de la plataforma. |

## 3. Capacidades relacionadas

| Capacidad | LangChain | CrewAI | Requisito principal | Nota operativa |
|---|---|---|---|---|
| RAG | Lista con conocimiento cargado | Lista con conocimiento cargado | Knowledge base o fuentes indexadas | Si no hay contenido indexado, la capacidad existe pero no aporta contexto útil. |
| MCP | Lista con servidor activo | Lista con servidor activo | Servidor MCP registrado, testeado y asignado | La cantidad de tools descubiertas depende del servidor externo. |
| Custom tools | Lista | Lista | Código válido y tool activa | Recomendado para lógica de negocio o APIs internas. |
| Skills | Lista | Lista | Skill activa y asignada | Pueden aportar tools, reglas y procedimiento. |

## 4. Requisitos operativos por tipo

### 4.1 Credenciales externas

Aplica, por ejemplo, a:

- `web_search`
- integraciones que dependan de keys de terceros

Recomendación:

- resolverlas desde backend o bóveda, no desde configuraciones dispersas por tool

### 4.2 Datasources

Aplica principalmente a:

- `sql_query`

Recomendación:

- usar conexiones de solo lectura
- limitar tablas permitidas
- evitar habilitar esta tool sin revisar el contexto del tenant

### 4.3 Políticas de salida o red

Aplica a:

- `rest_api_call`

Recomendación:

- definir allowlist de dominios
- limitar métodos
- dejar headers mínimos y controlados

### 4.4 Servicios globales de plataforma

Aplica a:

- `send_email`

Recomendación:

- validar SMTP global antes de esperar que la tool funcione en sandbox o producción

## 5. Qué mirar si algo falla

Checklist breve:

1. validar que el agente haya pasado por `Rebuild`
2. revisar el badge de estado de la tool
3. confirmar el requisito externo:
   - credencial
   - datasource
   - política
   - SMTP
   - servidor MCP
   - conocimiento indexado
4. revisar logs de observabilidad de tools en backend
5. volver a probar la tool en un caso simple antes de culpar al flujo completo del agente

## 6. Uso recomendado

- usar esta matriz para soporte y troubleshooting
- mantenerla alineada con el catálogo visible del frontend
- actualizarla cada vez que cambie el wiring real de una tool o capacidad
