# epaper-dashboard

Dashboard en una pantalla e-paper de 7,5" (Waveshare V2, 800×480) colgada de una
Raspberry Pi Zero 2 W. Muestra hora, clima y lista de tareas, y se configura
desde un panel web local.

## Estado

Fase 0 completa: esqueleto del proyecto, backend de display con modo mock, y un
render mínimo con hora y fecha. Ver [PLAN.md](PLAN.md) para las fases siguientes.

## Desarrollo en la notebook (sin hardware)

No hace falta la Pi para trabajar en el diseño. El backend `mock` escribe un PNG
idéntico a lo que se vería en el panel.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

EPAPER_BACKEND=mock python3 -m epaper.main
```

Resultado: `out/preview.png`, 800×480, 1 bit.

Sin instalar el paquete también funciona: `PYTHONPATH=src python3 -m epaper.main`.

## Puesta en la Pi

```bash
git clone git@github.com:USUARIO/epaper-dashboard.git ~/epaper-dashboard
cd ~/epaper-dashboard
./scripts/setup-pi.sh
```

El script es idempotente: instala dependencias de apt, clona la librería de
Waveshare, crea el venv, enlaza `waveshare_epd`, copia `config.yaml` desde la
plantilla, verifica SPI e instala las units de systemd.

Prueba manual:

```bash
sudo systemctl start epaper.service
journalctl -u epaper.service -n 30 --no-pager
```

## Actualizar

Desde la notebook, después de pushear:

```bash
./scripts/deploy.sh
```

Hace `git pull`, reinstala dependencias, reinicia el servicio y muestra el log.

## Estructura

```
src/epaper/
├── display.py      # backends: mock (PNG) | waveshare (panel real)
├── fonts.py        # carga de DejaVu con mínimo legible
├── main.py         # entrypoint: render → display
├── tiles/          # bloques del dashboard (reloj, clima, tareas)
├── sources/        # datos externos (Open-Meteo, tareas)
└── web/            # panel de configuración (FastAPI)
systemd/            # units: servicio, timer y panel web
scripts/            # setup-pi.sh, deploy.sh
```

## Documentación

- [CLAUDE.md](CLAUDE.md) — hardware, pinout, entorno y reglas del panel
- [PLAN.md](PLAN.md) — alcance de la v1 y plan por fases
