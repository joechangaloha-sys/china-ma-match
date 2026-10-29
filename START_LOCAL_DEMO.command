#!/usr/bin/env bash
# Joe's local fictional-data demo. Keep this window open while using the website.
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-7100}
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST=$2; shift 2 ;;
    --port) PORT=$2; shift 2 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

export MAMATCH_DATABASE_URL=${MAMATCH_DATABASE_URL:-"sqlite:///$ROOT/data/local-demo.db"}
export MAMATCH_UPLOAD_DIR=${MAMATCH_UPLOAD_DIR:-"$ROOT/data/local-demo-uploads"}
export MAMATCH_DEMO_MODE=${MAMATCH_DEMO_MODE:-true}
export MAMATCH_DEMO_ACCESS_KEY=${MAMATCH_DEMO_ACCESS_KEY:-demo-gate-local-only}
export MAMATCH_SEED_DEMO=${MAMATCH_SEED_DEMO:-true}
export MAMATCH_SECURE_COOKIES=${MAMATCH_SECURE_COOKIES:-false}
export MAMATCH_LLM=${MAMATCH_LLM:-off}
mkdir -p "$ROOT/data" "$MAMATCH_UPLOAD_DIR"

printf '\nStarting mamatch at http://%s:%s\n' "$HOST" "$PORT"
printf 'Demo passcode: %s\n' "$MAMATCH_DEMO_ACCESS_KEY"
printf 'Role password: demo-pass-2026\n'
printf 'Keep this window open. Press Ctrl+C to stop the website.\n\n'
if [[ ${#EXTRA[@]} -gt 0 ]]; then
  exec uv run mamatch serve --host "$HOST" --port "$PORT" "${EXTRA[@]}"
else
  exec uv run mamatch serve --host "$HOST" --port "$PORT"
fi
