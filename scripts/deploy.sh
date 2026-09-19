#!/usr/bin/env bash
# Despliega los cambios en la Pi desde la notebook.
#
# Uso:
#   ./scripts/deploy.sh                    # usa los valores por defecto
#   EPAPER_HOST=192.168.1.228 ./scripts/deploy.sh

set -euo pipefail

HOST="${EPAPER_HOST:-epaper.local}"
USER_NAME="${EPAPER_USER:-palessandri}"
REMOTE_DIR="${EPAPER_DIR:-~/epaper-dashboard}"

TARGET="$USER_NAME@$HOST"

echo "==> Desplegando en $TARGET:$REMOTE_DIR"

ssh "$TARGET" bash -s <<EOF
set -euo pipefail
cd $REMOTE_DIR
echo "--- git pull"
git pull --ff-only
echo "--- dependencias"
.venv/bin/pip install -q -r requirements.txt
echo "--- reiniciar servicio"
sudo systemctl restart epaper.service
sleep 3
echo "--- estado"
systemctl is-active epaper.service || true
EOF

echo "==> Últimas líneas del log"
ssh "$TARGET" "journalctl -u epaper.service -n 15 --no-pager"
