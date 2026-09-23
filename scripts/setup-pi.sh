#!/usr/bin/env bash
# Provisiona el proyecto en la Raspberry Pi. Idempotente: se puede correr
# varias veces sin romper nada.
#
# Uso (en la Pi, desde la raíz del repo):
#   ./scripts/setup-pi.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
WAVESHARE_DIR="$HOME/e-Paper"
WAVESHARE_LIB="$WAVESHARE_DIR/RaspberryPi_JetsonNano/python/lib"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "Paquetes del sistema"
sudo apt-get update
sudo apt-get install -y \
    python3-venv python3-pil python3-numpy python3-spidev python3-gpiozero \
    fonts-dejavu-core git

say "Locale en castellano"
# Para los nombres de día y mes ("miércoles 23 de septiembre").
if ! locale -a 2>/dev/null | grep -qi '^es_AR\.utf-\?8$'; then
    sudo sed -i 's/^# *\(es_AR.UTF-8\)/\1/' /etc/locale.gen
    sudo locale-gen
else
    echo "  es_AR.UTF-8 ya está generado"
fi

say "Librería de Waveshare"
if [ ! -d "$WAVESHARE_DIR" ]; then
    git clone --depth 1 https://github.com/waveshareteam/e-Paper.git "$WAVESHARE_DIR"
else
    git -C "$WAVESHARE_DIR" pull --ff-only || echo "  (sin cambios o sin red)"
fi

say "Entorno virtual"
# --system-site-packages para reutilizar PIL, numpy y spidev de apt en vez de
# compilarlos en la Zero 2, que tardaría muchísimo.
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"
"$VENV_DIR/bin/pip" install -e "$REPO_DIR"

say "Enlazar waveshare_epd dentro del venv"
# Un .pth es más robusto que depender de sys.path en tiempo de ejecución:
# funciona igual desde systemd, desde la shell y desde el panel web.
PTH="$("$VENV_DIR/bin/python" -c 'import site; print(site.getsitepackages()[0])')/waveshare.pth"
echo "$WAVESHARE_LIB" > "$PTH"
"$VENV_DIR/bin/python" -c "from waveshare_epd import epd7in5_V2; print('  waveshare_epd OK')"

say "Configuración"
if [ ! -f "$REPO_DIR/config.yaml" ]; then
    cp "$REPO_DIR/config.example.yaml" "$REPO_DIR/config.yaml"
    echo "  config.yaml creado desde la plantilla"
else
    echo "  config.yaml ya existe, no se toca"
fi

say "Verificar SPI"
if ls /dev/spidev* >/dev/null 2>&1; then
    ls /dev/spidev*
else
    echo "  SPI no habilitado. Corriendo: sudo raspi-config nonint do_spi 0"
    sudo raspi-config nonint do_spi 0
    echo "  Reiniciar para que tome efecto: sudo reboot"
fi

say "Instalar units de systemd"
sudo cp "$REPO_DIR/systemd/"*.service "$REPO_DIR/systemd/"*.timer /etc/systemd/system/
# Las units traen rutas y usuario como placeholders; se resuelven acá.
sudo sed -i "s#__REPO_DIR__#$REPO_DIR#g; s#__USER__#$USER#g" \
    /etc/systemd/system/epaper.service \
    /etc/systemd/system/epaper-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now epaper.timer

say "Listo"
echo "  Probar ahora:   sudo systemctl start epaper.service"
echo "  Ver el log:     journalctl -u epaper.service -n 30 --no-pager"
echo "  Ver el timer:   systemctl list-timers epaper.timer"
