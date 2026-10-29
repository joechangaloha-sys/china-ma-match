#!/usr/bin/env bash
set -Eeuo pipefail

SERVER_IP="${1:-}"
if [[ ! "$SERVER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: sudo bash install.sh SERVER_PUBLIC_IP"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo bash "$0" "$SERVER_IP"
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/opt/mamatch"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Use the Ubuntu 24.04 + Docker Lighthouse image."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Installing the Docker Compose helper..."
  apt-get update
  if ! apt-get install -y docker-compose-v2; then
    apt-get install -y docker-compose-plugin
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but is not running. Start it with: systemctl enable --now docker"
  exit 1
fi

if [[ "$SOURCE_DIR" != "$TARGET_DIR" ]]; then
  mkdir -p "$TARGET_DIR"
  cp -a "$SOURCE_DIR/." "$TARGET_DIR/"
fi
cd "$TARGET_DIR"

PUBLIC_HOST="${SERVER_IP}.sslip.io"
if [[ ! -f .env ]]; then
  if ! command -v openssl >/dev/null 2>&1; then
    apt-get update
    apt-get install -y openssl
  fi
  umask 077
  {
    printf 'APP_HTTP_PORT=80\n'
    printf 'APP_HTTPS_PORT=443\n'
    printf 'POSTGRES_DB=mamatch_demo\n'
    printf 'POSTGRES_USER=mamatch\n'
    printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'MAMATCH_DEMO_ACCESS_KEY=%s\n' "$(openssl rand -hex 24)"
    printf 'MAMATCH_PUBLIC_HOST=%s\n' "$PUBLIC_HOST"
    printf 'MAMATCH_PUBLIC_URL=https://%s\n' "$PUBLIC_HOST"
    printf 'MAMATCH_SECURE_COOKIES=true\n'
  } > .env
  chmod 600 .env
else
  # Upgrade an existing HTTP demo without replacing its secrets or database settings.
  cp .env ".env.before-https"
  if grep -q '^MAMATCH_PUBLIC_HOST=' .env; then
    sed -i "s|^MAMATCH_PUBLIC_HOST=.*$|MAMATCH_PUBLIC_HOST=$PUBLIC_HOST|" .env
  else
    printf 'MAMATCH_PUBLIC_HOST=%s\n' "$PUBLIC_HOST" >> .env
  fi
  if grep -q '^MAMATCH_PUBLIC_URL=' .env; then
    sed -i "s|^MAMATCH_PUBLIC_URL=.*$|MAMATCH_PUBLIC_URL=https://$PUBLIC_HOST|" .env
  else
    printf 'MAMATCH_PUBLIC_URL=https://%s\n' "$PUBLIC_HOST" >> .env
  fi
  if grep -q '^MAMATCH_SECURE_COOKIES=' .env; then
    sed -i 's|^MAMATCH_SECURE_COOKIES=.*$|MAMATCH_SECURE_COOKIES=true|' .env
  else
    printf 'MAMATCH_SECURE_COOKIES=true\n' >> .env
  fi
  if ! grep -q '^APP_HTTPS_PORT=' .env; then
    printf 'APP_HTTPS_PORT=443\n' >> .env
  fi
fi

# Keep the existing database, demo passcode and uploads on repeat installations.
docker compose -f compose.lighthouse.yaml up -d --build

READY=0
for attempt in $(seq 1 60); do
  if docker compose -f compose.lighthouse.yaml exec -T web python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=3)" \
    >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 5
done

if [[ "$READY" -ne 1 ]]; then
  echo "The website did not become ready in time. Recent logs follow."
  docker compose -f compose.lighthouse.yaml logs --tail=80
  exit 1
fi

set -a
# This file is generated locally on the server with alphanumeric secrets only.
. ./.env
set +a
umask 077
{
  printf '\nmamatch demo is running.\n'
  printf 'Website: %s\n' "$MAMATCH_PUBLIC_URL"
  printf 'Outer demo passcode: %s\n' "$MAMATCH_DEMO_ACCESS_KEY"
  printf 'Demo role password: demo-pass-2026\n'
  printf 'Use fictional test information only.\n'
} | tee DEMO_LOGIN.txt
chmod 600 DEMO_LOGIN.txt
