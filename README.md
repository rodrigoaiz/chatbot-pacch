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

## Actualizacion completa

No se entrena ni se ajusta un modelo con el contenido del portal. La aplicacion
usa modelos generales de Ollama y construye una base RAG local. Para actualizar
paginas modificadas y generar todos los embeddings pendientes en una sola
operacion:

```bash
.venv/bin/chatbot-pacch sync
```

`sync` es incremental y seguro: conserva la base existente, omite paginas sin
cambios y procesa solamente contenido nuevo o actualizado. Si
`data/pacch.sqlite3` no existe, crea y reconstruye la base completa desde el
portal.

Para incorporar todos los objetos de aprendizaje, en lugar del piloto de
Historia Universal I:

```bash
.venv/bin/chatbot-pacch sync --all
```

El inventario actual del portal contiene 265 objetos distribuidos en 23
asignaturas. `--all` eleva automáticamente el límite de descubrimiento para
incluir también las páginas internas de cada objeto; `PACCH_MAX_PAGES` conserva
su función como límite de seguridad al sincronizar una sola materia.

### Agregar una materia

Consultar los nombres y slugs que publica el catalogo:

```bash
.venv/bin/chatbot-pacch subjects
```

Se puede pasar el nombre legible o el slug. La sincronizacion agrega la materia
sin borrar las que ya estan indexadas:

```bash
.venv/bin/chatbot-pacch sync --subject "Historia de México I"
.venv/bin/chatbot-pacch sync --subject "Matemáticas I"
```

El mismo comando descarga las paginas y genera sus embeddings. Al terminar, el
servidor consulta conjuntamente todas las materias almacenadas; no requiere
reiniciar ni reentrenar los modelos.

En Matematicas, el MVP puede presentar expresiones sencillas con formato LaTeX,
pero el modelo compacto no debe considerarse un solucionador fiable de
operaciones o demostraciones. Sus resultados deben validarse contra el recurso
enlazado.

## Recuperacion en otra computadora

El repositorio incluye `scripts/rebuild-local.sh`. En una computadora con Git,
Python 3.14 y Ollama, este script crea el entorno, instala la aplicacion,
descarga los modelos y reconstruye SQLite desde el Portal Academico:

```bash
git clone https://github.com/rodrigoaiz/chatbot-pacch.git
cd chatbot-pacch
./scripts/rebuild-local.sh
```

Este proceso no recupera conversaciones ni una copia anterior de SQLite: genera
un indice nuevo con el contenido que publique el portal en ese momento.

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

## Auditoria De Rutas

El sitemap es la fuente de rutas, pero la cobertura se verifica cruzando el
catalogo de objetos, las paginas del sitemap y el indice SQLite:

```bash
.venv/bin/chatbot-pacch audit --all
```

El reporte comprueba:

- Que cada objeto del catalogo tenga paginas asociadas en el sitemap.
- Que cada pagina descubierta este indexada o registrada como excluida.
- Que no existan paginas faltantes o documentos obsoletos.
- Que no haya paginas duplicadas o con `//` en el path.
- Que las asignaturas del catalogo aparezcan en SQLite.
- Que todos los fragmentos tengan embeddings.

La auditoria actual devuelve `complete: true`, con 265 objetos, 3,082 paginas
descubiertas, 3,069 paginas indexadas y 13 exclusiones conocidas. Las
exclusiones corresponden a rutas 404 o portadas sin texto academico extraible;
no son paginas faltantes silenciosas.

La auditoria valida cobertura e integridad del indice. No fuerza una peticion
HTTP a cada una de las 3,082 paginas en cada ejecucion, para consultar el portal
respetuosamente. Las ligas publicas se normalizan: las rutas antiguas
`/alumno/...` usan `e1.portalacademico.cch.unam.mx`, mientras los objetos
modernos conservan `portalacademico.cch.unam.mx`.

## Servidor

```bash
.venv/bin/chatbot-pacch serve
```

Abrir `http://127.0.0.1:8765`. El comando rechaza cualquier `APP_HOST` distinto
de `127.0.0.1` para evitar una publicacion accidental.

Endpoints actuales:

- `GET /api/health`
- `GET /api/corpus`
- `GET /api/subjects`
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
