#!/usr/bin/env bash
# Run with bash; Ctrl-C stops only the two services started by this script.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export NEWBEE_API_ONLY=false
export MINERU_HOME="$PROJECT_ROOT/models/mineru4"
export MINERU_MODEL_BASE_DIR="$MINERU_HOME/weights"
export MINERU_MODEL_SOURCE=local
export MINERU_MODEL_SMALL_BACKEND=torch
export MINERU_MODEL_VLM_ENGINE=llama-cpp
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

MINERU_PID=""
EMBEDDING_PID=""
cleanup() {
    [ -z "$MINERU_PID" ] || kill "$MINERU_PID" 2>/dev/null || true
    [ -z "$EMBEDDING_PID" ] || kill "$EMBEDDING_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

.venv/mineru/bin/mineru-kit api-server --host 127.0.0.1 --port 8001 \
    --tier standard --concurrency 1 --retention-seconds 600 \
    --upload-dir "$PROJECT_ROOT/.tmp/mineru4-server" &
MINERU_PID=$!
.venv/embedding/bin/python -m scripts.local_embedding_server --device mps &
EMBEDDING_PID=$!
while kill -0 "$MINERU_PID" 2>/dev/null && kill -0 "$EMBEDDING_PID" 2>/dev/null; do
    sleep 1
done
echo "A local model service stopped; shutting down its companion." >&2
exit 1
