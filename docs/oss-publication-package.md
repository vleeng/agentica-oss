# Paquete de publicacion OSS

Este paquete prepara la apertura del fork publico de Agentica para la UNICABA, Universidad de la Ciudad de Buenos Aires.

## Objetivo

Dejar listo un repositorio publico separado, basado en la linea `platform`, con:

- perfil `oss` por defecto
- UI sobria y comunitaria
- Moodle aislado y habilitado solo en OSS
- sin billing ni planes comerciales
- documentacion de instalacion y contribucion

## Archivos que debe tener el repo publico

- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `docs/oss-fork-guide.md`
- `docs/oss-public-readme-draft.md`

## Checklist previo a abrir el repo

1. Confirmar que `PRODUCT_PROFILE=oss` es el valor por defecto del fork.
2. Verificar que el frontend no muestre planes, billing ni lenguaje SaaS.
3. Confirmar que Moodle no dependa de headers del cliente.
4. Revisar que la documentacion publica no exponga detalles privados de Vleeng.
5. Verificar que `README.md` explique instalacion y primeros pasos.
6. Validar build backend y frontend en limpio.
7. Definir la URL del repo publico y la licencia final.

## Bootstrap del fork

1. Crear el repo publico en GitHub.
2. Hacer push desde la rama base definida para OSS.
3. Ajustar `README.md` para que sea la portada publica.
4. Configurar secretos y variables de entorno del server universitario.
5. Crear el tenant inicial y validar login.
6. Publicar la primera version etiquetada.

## Criterio de salida

El paquete queda listo cuando:

- el README publico ya no necesita contexto privado
- la instalacion base funciona en un servidor nuevo
- la ruta de contribucion esta documentada
- el fork puede publicarse sin referencias comerciales innecesarias
