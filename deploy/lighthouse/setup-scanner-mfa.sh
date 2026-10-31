#!/usr/bin/env bash
# Run as root on the existing Lighthouse server. Does not open a TCP scanner port.
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y clamav-daemon clamav-freshclam
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/clamav/clamd.conf')
settings={'LocalSocket':'/run/clamav/clamd.ctl', 'LocalSocketGroup':'clamav', 'LocalSocketMode':'660',
          'MaxThreads':'1', 'MaxQueue':'2', 'ConcurrentDatabaseReload':'false', 'StreamMaxLength':'20M',
          'MaxScanSize':'80M', 'MaxFileSize':'20M', 'MaxRecursion':'10', 'AlertExceedsMax':'true',
          'AlertEncrypted':'true', 'CommandReadTimeout':'10', 'ReadTimeout':'60', 'SendBufTimeout':'60',
          'SelfCheck':'600', 'EnableVersionCommand':'true', 'EnableShutdownCommand':'false',
          'EnableReloadCommand':'false', 'EnableStatsCommand':'false'}
lines=p.read_text().splitlines()
lines=[line for line in lines if not line.split(' ',1)[0] in settings and not line.startswith(('TCPSocket ', 'TCPAddr '))]
p.write_text('\n'.join(lines)+'\n'+'\n'.join(f'{k} {v}' for k,v in settings.items())+'\n')
# Persist a key separate from the DB; preserve it on every re-run. Never print it.
import base64, secrets, grp
p=Path('/opt/mamatch/.env')
lines=p.read_text().splitlines()
settings={'MAMATCH_CLAMD_SOCKET':'/run/clamav/clamd.ctl', 'MAMATCH_CLAMAV_GID':str(grp.getgrnam('clamav').gr_gid),
          'MAMATCH_MFA_REQUIRED':'true'}
if not any(line.startswith('MAMATCH_MFA_ENCRYPTION_KEY=') and line.split('=',1)[1] for line in lines):
    settings['MAMATCH_MFA_ENCRYPTION_KEY']=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
lines=[line for line in lines if line.split('=',1)[0] not in settings]
p.write_text('\n'.join(lines)+'\n'+'\n'.join(f'{k}={v}' for k,v in settings.items())+'\n')
p.chmod(0o600)
PY
# Bound the daemon and avoid a second in-memory signature copy on this 2 GiB host.
install -d /etc/systemd/system/clamav-daemon.service.d
cat > /etc/systemd/system/clamav-daemon.service.d/mamatch-resources.conf <<'EOF'
[Service]
Environment=TZ=UTC
MemoryHigh=1100M
MemoryMax=1400M
Restart=on-failure
RestartSec=10
EOF
systemctl stop clamav-daemon.service clamav-daemon.socket
systemctl daemon-reload
systemctl enable clamav-daemon clamav-freshclam
systemctl start clamav-daemon.socket clamav-daemon.service
systemctl start clamav-freshclam
echo 'Local scanner configured; MFA key persisted without displaying it.'
