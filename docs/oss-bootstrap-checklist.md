# OSS bootstrap checklist

Este documento convierte el fork publico de Agentica para UNICABA en una secuencia concreta de publicacion.

## Objetivo

Dejar preparado el repositorio publico para que pueda:

- clonarse desde GitHub
- instalarse en un servidor nuevo
- levantarse con `PRODUCT_PROFILE=oss`
- operar sin billing ni planes comerciales
- documentar su instalacion y contribucion desde el primer dia

## Entrada recomendada

La base de partida debe ser:

- la linea privada `platform`
- ya validada en build
- sin leakage SaaS visible
- con Moodle aislado solo para OSS

## Paso 1. Congelar la base privada

Antes del fork:

1. Confirmar que `platform` esta limpia.
2. Validar `npm.cmd run build` en frontend.
3. Validar backend en limpio.
4. Confirmar que no quedan textos de planes ni billing visibles para `platform`.
5. Tomar una referencia estable para el fork, idealmente un tag o commit conocido.

## Paso 2. Crear el repo publico

1. Crear el repositorio publico en GitHub.
2. Definir nombre final del repo.
3. Configurar descripcion publica y visibilidad.
4. Hacer el primer push desde la base `platform`.
5. Ajustar el remote principal del nuevo repo.

## Paso 3. Dejar OSS como perfil por defecto

En el repo publico:

1. Configurar `PRODUCT_PROFILE=oss` como valor por defecto.
2. Revisar que el frontend tome el tema comunitario sobrio.
3. Confirmar que la navegacion y el login no arrastren copy SaaS.
4. Verificar que el backend exponga solo lo permitido para OSS.

## Paso 4. Verificar dependencias OSS

1. Confirmar `LICENSE`.
2. Confirmar `CONTRIBUTING.md`.
3. Confirmar `SECURITY.md`.
4. Confirmar `README.md` publico.
5. Confirmar `docs/oss-fork-guide.md`.
6. Confirmar `docs/oss-public-readme-draft.md`.
7. Confirmar `docs/oss-publication-package.md`.

## Paso 5. Configuracion minima del servidor OSS

1. Copiar `.env.example` a `.env`.
2. Ajustar `PRODUCT_PROFILE=oss`.
3. Definir las llaves LLM necesarias.
4. Configurar Moodle si la instalacion lo requiere.
5. Crear el tenant inicial.
6. Validar login y carga del dashboard.

## Paso 6. Validacion tecnica

1. Ejecutar build frontend.
2. Ejecutar validacion backend.
3. Confirmar que no haya billing ni planes comerciales visibles.
4. Confirmar que Moodle funcione solo en OSS.
5. Confirmar que el monitor de ejecuciones y el chat respondan.

## Paso 7. Primera publicacion

1. Crear el primer tag publico.
2. Publicar la version inicial en GitHub.
3. Actualizar el README publico con el estado actual.
4. Registrar el server de la UNICABA como despliegue de referencia.

## Criterio de salida

El bootstrap queda completo cuando:

- el repo publico se puede clonar y levantar
- el perfil por defecto es `oss`
- la documentacion publica explica instalacion y contribucion
- la UI no expone planes ni billing
- Moodle queda aislado a la linea OSS

