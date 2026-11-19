#!/usr/bin/env bash
# Sobe o reranker (backend/reranker) nativo no Mac, na GPU da Apple (MPS).
# No Docker o Mac não tem GPU: em CPU são ~0,9 s por trecho, contra ~0,12 s aqui.
# Uso: scripts/reranker-mac.sh   (porta: RERANKER_PORT, padrão 18080)
# No backend/.env: RERANKER_URL=http://host.docker.internal:18080 e RERANKER_TIMEOUT=60.
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
pasta="$raiz/backend/reranker"
porta="${RERANKER_PORT:-18080}"

if ! command -v uv >/dev/null; then
    echo "Instale o uv: https://docs.astral.sh/uv/" >&2
    exit 1
fi
if [ ! -x "$pasta/.venv/bin/uvicorn" ]; then
    uv venv --python 3.12 "$pasta/.venv"
    uv pip install --python "$pasta/.venv/bin/python" -r "$pasta/requirements.txt"
fi

# O modelo (~2,3 GB) fica no cache do Hugging Face do usuário, fora do repositório.
cd "$pasta"
exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port "$porta"
