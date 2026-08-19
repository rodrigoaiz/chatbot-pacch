# Chatbot PACCH

MVP local para descubrir, limpiar e indexar objetos de aprendizaje del Portal
Academico del CCH. La primera validacion se concentra en Historia Universal
Moderna y Contemporanea I.

El proyecto no es un servicio oficial de la UNAM. Conserva las URL de origen y
esta disenado para uso academico local.

## Funcionalidad

Implementado:

- Configuracion local mediante `.env`.
- SQLite con FTS5 y registro de ingestiones.
- Comprobacion de Ollama y modelos instalados.
- Descubrimiento desde el catalogo y los sitemaps del portal.
- Filtro por asignatura.
- Descarga respetuosa de `robots.txt`, pausas y reintentos.
- Extraccion de contenido principal.
- Fragmentacion por secciones.
- Actualizacion incremental por `lastmod` y hash.
- API local de estado y corpus.
- Embeddings multilingues con `embeddinggemma`.
- Busqueda hibrida mediante FTS5 y similitud coseno.
- Respuestas RAG en streaming con fuentes verificadas.
- Rechazo de preguntas sin evidencia suficiente.
- Interfaz responsive inspirada en el lenguaje visual del Portal Academico.
- Evaluacion reproducible de recuperacion y rechazos.

## Requisitos

- Python 3.14.
- Ollama activo en `127.0.0.1:11434`.
- `qwen2.5:1.5b` instalado para generar respuestas.
- `embeddinggemma` instalado para busqueda semantica.
- Al menos 8 GB libres en disco durante la ingestión.

## Instalacion

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
```

Los modelos se descargan una sola vez:

```bash
ollama pull embeddinggemma
ollama pull qwen2.5:1.5b
```

## Estado local

```bash
.venv/bin/chatbot-pacch status
```

## Ingestion

Primero se recomienda una prueba pequena:

```bash
.venv/bin/chatbot-pacch ingest --limit 5
```

Despues se puede ejecutar el piloto completo de Historia Universal I:

```bash
.venv/bin/chatbot-pacch ingest
```

Para indexar todo el catalogo en una fase posterior:

```bash
.venv/bin/chatbot-pacch ingest --all
```

La base generada se guarda en `data/pacch.sqlite3` y no se versiona.

## Embeddings

Despues de incorporar paginas nuevas o actualizadas:

```bash
.venv/bin/chatbot-pacch embed
```

El comando solo procesa fragmentos pendientes. Puede interrumpirse y reanudarse
sin perder los vectores ya generados.

## Diagnostico RAG

Probar la recuperacion sin invocar el modelo generativo:

```bash
.venv/bin/chatbot-pacch search "¿Que fue la Comuna de Paris?"
```

Probar una respuesta completa desde la terminal:

```bash
.venv/bin/chatbot-pacch ask "¿Que son los derechos naturales?"
```

En este equipo la generacion puede tardar alrededor de un minuto. La busqueda y
las fuentes aparecen antes en la interfaz web mediante streaming.

## Evaluacion

```bash
.venv/bin/chatbot-pacch evaluate
```

El conjunto `evaluation/historia_universal_1.json` contiene preguntas
contestables y fuera de alcance. El resultado esperado para el corpus piloto es
100 % de recuperacion `Recall@5` y 100 % de rechazo en ese conjunto pequeno; no
representa una evaluacion academica exhaustiva.

## Servidor

```bash
.venv/bin/chatbot-pacch serve
```

Abrir `http://127.0.0.1:8765`. El comando rechaza cualquier `APP_HOST` distinto
de `127.0.0.1` para evitar una publicacion accidental.

Endpoints actuales:

- `GET /api/health`
- `GET /api/corpus`
- `POST /api/search`
- `POST /api/chat` (`application/x-ndjson` en streaming)

## Pruebas

```bash
.venv/bin/pytest
```

## Seguridad de red

El servicio usa `127.0.0.1:8765`, no los puertos `4321` a `4326` reservados por
otros servicios del equipo. Ollama debe permanecer en `127.0.0.1:11434`.

No se debe agregar una ruta a Nginx durante el MVP local. La publicacion futura
requiere autorizacion sobre contenidos, autenticacion o control de acceso,
limites de solicitudes y una revision separada de Nginx y TLS.

`deploy/nginx-location.example.conf` es solamente una referencia. No modifica
`/etc/nginx/sites-available/astro`, `location /`, los puertos `4321` a `4326`,
el Help Desk ni PostgreSQL.

## Servicio opcional

`deploy/chatbot-pacch.service` permite iniciar el servidor con systemd cuando se
decida mantenerlo activo. Debe revisarse antes de instalarse y no es necesario
para desarrollo. La aplicacion sigue escuchando exclusivamente en
`127.0.0.1:8765`.
