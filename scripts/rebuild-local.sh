#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

command -v python3 >/dev/null || {
  printf 'Error: python3 no esta instalado.\n' >&2
  exit 1
}
command -v ollama >/dev/null || {
  printf 'Error: Ollama no esta instalado.\n' >&2
  exit 1
}

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'

ollama pull embeddinggemma
ollama pull qwen2.5:1.5b

.venv/bin/chatbot-pacch sync "$@"

printf '\nReconstruccion terminada. Inicia la web con:\n'
printf '  .venv/bin/chatbot-pacch serve\n'
