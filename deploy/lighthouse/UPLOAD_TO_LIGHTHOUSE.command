#!/usr/bin/env bash
set -Eeuo pipefail

SERVER_IP="43.153.223.242"
SERVER_USER="ubuntu"
cd "$(dirname "$0")"

printf '\nThis will install or update the mamatch demo on http://%s\n' "$SERVER_IP"
printf 'Existing form records, uploads and the demo passcode will be preserved.\n'
printf 'When asked for a password, enter the Lighthouse server password.\n'
printf 'The password will stay invisible while you type. Press Return afterward.\n\n'
read -r -p "Type YES to continue: " CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
  echo "Cancelled. Nothing was uploaded."
  exit 1
fi

for name in Dockerfile pyproject.toml compose.lighthouse.yaml install.sh; do
  if [[ ! -f "$name" ]]; then
    echo "Missing $name. Open the extracted mamatch-lighthouse-demo folder and try again."
    exit 1
  fi
done

# One SSH connection uploads the clean extracted folder and starts the installer.
# No cloud password is stored in this script or in the package.
tar --exclude='./.env' --exclude='./DEMO_LOGIN.txt' --exclude='./.DS_Store' -czf - . | \
  ssh -o StrictHostKeyChecking=accept-new "$SERVER_USER@$SERVER_IP" \
    "mkdir -p /home/ubuntu/mamatch-upload && tar -xzf - -C /home/ubuntu/mamatch-upload && sudo bash /home/ubuntu/mamatch-upload/install.sh '$SERVER_IP'"

printf '\nUpload finished. Save the website address and outer demo passcode shown above.\n'
printf 'You can close this window after confirming the website opens.\n'
