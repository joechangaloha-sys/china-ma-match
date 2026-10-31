#!/usr/bin/env bash
# Deploy what is on GitHub to the Lighthouse demo: the server pulls only the changes and rebuilds.
# Usage: deploy/lighthouse/deploy.sh [branch]   (default: main). Push your commits first.
set -Eeuo pipefail

SERVER="ubuntu@43.153.223.242"
REPO_URL="https://github.com/joechangaloha-sys/china-ma-match.git"
BRANCH="${1:-main}"
cd "$(dirname "$0")/../.."

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Note: you have uncommitted changes. Only what is pushed to GitHub gets deployed."
fi
git fetch --quiet origin "$BRANCH"
if [[ "$(git rev-parse --abbrev-ref HEAD)" == "$BRANCH" && -n "$(git log --oneline "origin/$BRANCH..HEAD")" ]]; then
  echo "Note: local $BRANCH has commits not on GitHub yet. Run 'git push' first to include them."
fi
echo "Deploying origin/$BRANCH ($(git log -1 --format='%h %s' "origin/$BRANCH")) to $SERVER"

# The existing /opt/mamatch/.env (database password, demo passcode) and Docker volumes are reused untouched.
ssh -o StrictHostKeyChecking=accept-new "$SERVER" "sudo bash -s -- '$BRANCH' '$REPO_URL'" <<'REMOTE'
set -Eeuo pipefail
BRANCH="$1"
REPO_URL="$2"
SRC=/opt/mamatch-src
ENV_FILE=/opt/mamatch/.env
exec 9>/opt/mamatch/deploy.lock
flock -n 9 || { echo "Another deployment is running"; exit 1; }

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Run the original Lighthouse installer once first."
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  apt-get update && apt-get install -y git
fi
if [[ ! -d "$SRC/.git" ]]; then
  git clone --quiet --branch "$BRANCH" "$REPO_URL" "$SRC"
fi
cd "$SRC"
git fetch --quiet origin "$BRANCH"
# Match GitHub exactly; nothing is edited on the server.
git checkout --quiet -B "$BRANCH" "origin/$BRANCH"
git reset --quiet --hard "origin/$BRANCH"

COMPOSE=(docker compose --env-file "$ENV_FILE"
  -f deploy/lighthouse/compose.lighthouse.yaml -f deploy/lighthouse/compose.git.yaml)
# Keep a recoverable application image. Schema changes must remain backward compatible.
if docker inspect mamatch-lighthouse-web-1 >/dev/null 2>&1; then
  OLD_IMAGE=$(docker inspect --format '{{.Image}}' mamatch-lighthouse-web-1)
  docker tag "$OLD_IMAGE" "mamatch-rollback:$(date -u +%Y%m%dT%H%M%SZ)"
fi
"${COMPOSE[@]}" build web
python3 deploy/lighthouse/recovery_check.py
"${COMPOSE[@]}" run --rm --no-deps web python -m mamatch.migrations upgrade --adopt-existing
"${COMPOSE[@]}" up -d --no-build

for attempt in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T web python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=3)" \
    >/dev/null 2>&1; then
    # Rollback images and verified backups are intentionally retained.
    echo "Deployed $(git log -1 --format='%h %s'). Website: $(grep '^MAMATCH_PUBLIC_URL=' "$ENV_FILE" | cut -d= -f2-)"
    exit 0
  fi
  sleep 5
done
echo "The website did not become ready in time. Recent logs follow."
"${COMPOSE[@]}" logs --tail=80
exit 1
REMOTE
