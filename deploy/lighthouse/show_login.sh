#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo bash "$0"
fi

if [[ ! -f /opt/mamatch/DEMO_LOGIN.txt ]]; then
  echo "No demo login file was found. Run the Lighthouse installer first."
  exit 1
fi

cat /opt/mamatch/DEMO_LOGIN.txt
