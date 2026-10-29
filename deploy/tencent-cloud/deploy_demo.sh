#!/usr/bin/env bash
# Redeploy an already configured mamatch demo service. No credentials are stored here.
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SERVICE_NAME=mamatch-demo

preflight() {
  local required=(Dockerfile .dockerignore pyproject.toml uv.lock README.md src/mamatch/container.py src/mamatch/web/app.py)
  local file
  for file in "${required[@]}"; do
    if [[ ! -f "$ROOT/$file" ]]; then
      printf 'Missing required bundle file: %s\n' "$file" >&2
      return 1
    fi
  done
  if [[ -f "$ROOT/.env" ]]; then
    printf 'Refusing to upload: remove the local .env file; enter secrets only in Tencent Cloud.\n' >&2
    return 1
  fi
  printf 'Bundle preflight passed. Dockerfile and application files are present; no local .env is included.\n'
}

if [[ "${1:-}" == "--check" ]]; then
  preflight
  exit 0
fi

if [[ $# -ne 1 || -z "${1:-}" ]]; then
  printf 'Usage: %s <ENV_ID>\n' "$0" >&2
  printf 'First deployment: follow TENCENT_UPLOAD_GUIDE.md and upload the ZIP in the console.\n' >&2
  printf 'This helper redeploys an existing, fully configured service.\n' >&2
  exit 2
fi

preflight
if ! command -v tcb >/dev/null 2>&1; then
  printf 'CloudBase CLI is missing. Run: npm install -g @cloudbase/cli && tcb login\n' >&2
  exit 1
fi

printf 'Deploying %s to environment %s. Confirm the environment before accepting any CLI prompt.\n' "$SERVICE_NAME" "$1"
tcb cloudrun deploy \
  --env-id "$1" \
  --service-name "$SERVICE_NAME" \
  --port 8080 \
  --source "$ROOT" \
  --wait
printf 'Deployment command finished. Run the acceptance checks in TENCENT_UPLOAD_GUIDE.md.\n'
