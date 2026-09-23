"""Entrypoint del dashboard: leer config → datos → render → mostrar.

Uso:
    EPAPER_BACKEND=mock      python3 -m epaper.main     # notebook
    EPAPER_BACKEND=waveshare python3 -m epaper.main     # en la Pi
    python3 -m epaper.main --clear                      # limpiar el panel
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from epaper import config
from epaper.display import get_display
from epaper.render import render
from epaper.sources import openmeteo

log = logging.getLogger(__name__)


def _now(cfg: dict[str, Any]) -> datetime:
    """Hora en la zona de la config, no la del sistema."""
    try:
        return datetime.now(ZoneInfo(cfg["location"]["timezone"]))
    except Exception as exc:
        log.warning("Zona horaria inválida (%s); se usa la del sistema", exc)
        return datetime.now().astimezone()


def build_context(cfg: dict[str, Any]) -> dict[str, Any]:
    """Junta todos los datos que necesitan los tiles. Nunca lanza."""
    weather = openmeteo.get_weather(cfg) if cfg["weather"]["enabled"] else None
    return {
        "now": _now(cfg),
        "cfg": cfg,
        "weather": weather,
        # La fuente de tareas llega en la próxima fase; por ahora, vacía.
        "tasks": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dashboard e-paper")
    parser.add_argument(
        "--clear", action="store_true", help="limpiar la pantalla y salir"
    )
    parser.add_argument(
        "--backend", default=None, help="mock | waveshare (default: $EPAPER_BACKEND)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        # Los datos se juntan antes de tocar el panel: la red puede tardar
        # hasta el timeout y no tiene sentido tenerlo despierto mientras tanto.
        image = None if args.clear else render(build_context(config.load()))
        with get_display(args.backend) as display:
            if image is None:
                display.clear()
                log.info("Pantalla limpiada")
            else:
                display.show(image)
                log.info("Dashboard actualizado")
    except Exception:
        log.exception("Falló la actualización del dashboard")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
