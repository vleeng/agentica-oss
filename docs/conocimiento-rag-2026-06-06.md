# Conocimiento y RAG 2026-06-06

## Objetivo

Este documento resume el modelo actual de conocimiento y retrieval en Agentica.

## 1. Modelo vigente

La unidad principal de conocimiento es la `Knowledge Base`.

La direccion actual del producto es:

- usar KBs como contenedor principal,
- evitar duplicacion entre conocimiento de agente y conocimiento compartido,
- asociar KBs a agentes por visibilidad o asignacion.

## 2. Access mode

Cada KB puede operar en uno de dos modos:

- `global`
- `restricted`

### Global

La KB esta disponible para todos los agentes del tenant.

### Restricted

La KB solo esta disponible para los agentes asociados explicitamente.

## 3. Asociacion a agentes

La asociacion se administra por endpoints y por UI.

Comportamiento vigente:

- un agente consume KBs accesibles,
- una KB global no se desasigna desde el agente,
- una KB restricted si puede asignarse o quitarse.

## 4. Reglas de creacion

Si un agente declara que necesita conocimiento interno:

- debe tener al menos una KB asociada antes de crearse.

Esta regla hoy ya se aplica en:

- wizard clasico,
- wizard por chat,
- backend `POST /agents/spec`.

## 5. Ingesta de archivos

Cuando se sube un archivo a una KB:

1. se guarda en el storage de la KB,
2. se lanza un proceso de ingesta,
3. se parsea el archivo,
4. se fragmenta en chunks,
5. se generan embeddings,
6. se guarda en Qdrant.

## 6. Tipos de archivo soportados

El cargador actual soporta:

- PDF
- PPTX / PPT
- DOCX / DOC
- XLSX / XLS
- CSV
- texto plano

## 7. Parseo de PDF

El parseo actual de PDF usa `PyPDFLoader`.

Consecuencias:

- funciona bien con PDFs que tienen texto real,
- no hace OCR,
- en PDFs escaneados puede extraer poco o nada.

## 8. Chunks y embeddings

El splitter actual usa `RecursiveCharacterTextSplitter`.

Parametros base del spec:

- `chunk_size`
- `chunk_overlap`
- `top_k`

Los embeddings se resuelven hoy con proveedor OpenAI-compatible configurado para embeddings.

Nota:

- Anthropic no se usa para embeddings en la implementacion actual.

## 9. Store vectorial

Los chunks embebidos se guardan en Qdrant.

El nombre de la coleccion se deriva del owner del conocimiento.

En la version actual ese esquema sirve tanto para agentes como para KBs.

## 10. Retrieval actual

El retrieval ya esta orientado a KBs accesibles por agente.

Eso incluye:

- KBs globales,
- KBs restricted asignadas al agente.

En runtime:

- el agente puede consultar KB como tool,
- o recibir contexto RAG dentro del nodo `agent`.

## 11. React y graph runtime

En agentes `react` el conocimiento puede intervenir de dos maneras:

- como `knowledge_base` tool explicita,
- como contexto automatico del nodo `agent`.

En flujo LangChain:

- si ya se consulto la KB en un paso previo,
- el runtime puede reutilizar ese contexto y evitar una consulta redundante.

## 12. Observabilidad de KB

Los accesos a conocimiento ya quedan reflejados en:

- bitacora visible del chat,
- monitor `Ejecuciones`,
- `conversation_events`.

Para cada acceso hoy puede verse:

- consulta usada,
- hallazgos resumidos,
- cantidad de resultados,
- fuentes o titulos cuando estan disponibles.

## 13. Limites actuales

- no hay OCR,
- no hay edicion in-place de contenido ya indexado,
- la calidad de hallazgos depende del parseo del documento de origen,
- no existe todavia upload temporal de documentos dentro del chat.

## 14. Direccion recomendada

La direccion actual y recomendada del producto es:

- KBs como unica unidad fuerte de conocimiento reusable,
- asociaciones claras por agente,
- monitoreo de accesos,
- y luego, si se necesita, documentos temporales por sesion de chat como evolucion separada.
