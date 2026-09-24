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

ssh "$TARGET" "cd $REMOTE_DIR && ./scripts/update.sh"
