#!/usr/bin/env bash
# Actualiza el código en la Pi y reinicia los servicios. Se corre en la Pi
# (o desde la notebook vía deploy.sh).
#
# Uso (en la Pi, desde la raíz del repo):
#   ./scripts/update.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "--- git pull"
git pull --ff-only
echo "--- dependencias"
.venv/bin/pip install -q -r requirements.txt
# Forzar a disco lo recién bajado: la Pi se desenchufa sin apagar, y un
# archivo que quedó solo en caché aparece vacío al volver.
sync
echo "--- reiniciar servicios"
sudo systemctl restart epaper-web.service
sudo systemctl start epaper.service
echo "--- estado"
systemctl is-active epaper-web.service || true
journalctl -u epaper.service -n 8 --no-pager
