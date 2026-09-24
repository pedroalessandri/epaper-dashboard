"""Entrypoint del dashboard: leer config → datos → render → mostrar.

Uso:
    EPAPER_BACKEND=mock      python3 -m epaper.main     # notebook
    EPAPER_BACKEND=waveshare python3 -m epaper.main     # en la Pi
    python3 -m epaper.main --clear                      # limpiar el panel
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from epaper import config, refresh
from epaper.display import MockDisplay, get_display
from epaper.message_view import render_message
from epaper.render import render
from epaper.sources import openmeteo
from epaper.sources.message import MessageStore
from epaper.sources.tasks import LocalTaskSource

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
        "tasks": LocalTaskSource().get_tasks() if cfg["tasks"]["enabled"] else [],
    }


def compose():
    """La imagen que corresponde mostrar ahora: el mensaje o el dashboard."""
    state = MessageStore().get()
    if state.shows_message:
        log.info("Modo mensaje")
        return render_message(state.text)
    return render(build_context(config.load()))


def _save_preview(image) -> None:
    """Guarda lo que se mandó al panel, para verlo desde el panel web."""
    path = MockDisplay().out_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.png")
        image.save(tmp)
        tmp.replace(path)
    except OSError as exc:
        log.warning("No se pudo guardar el preview: %s", exc)


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
    # Si esta línea no aparece en el journal, el código ni llegó a correr
    # (p. ej. archivos vaciados por un corte de luz).
    log.info("Inicio del refresco")

    try:
        # Los datos se juntan antes de tocar el panel: la red puede tardar
        # hasta el timeout y no tiene sentido tenerlo despierto mientras tanto.
        image = None if args.clear else compose()
        signature = "" if image is None else hashlib.sha1(image.tobytes()).hexdigest()
        with get_display(args.backend) as display:
            real_panel = not isinstance(display, MockDisplay)
            wait = refresh.seconds_until_allowed()
            if real_panel and not args.clear and wait > 0:
                log.info("Último refresco hace menos de %d s; se saltea (faltan %.0f s)",
                         refresh.MIN_INTERVAL_S, wait)
                return 0
            if real_panel and image is not None and refresh.is_redundant(signature):
                log.info("La imagen no cambió; no se refresca el panel")
                return 0
            if image is None:
                display.clear()
                log.info("Pantalla limpiada")
            else:
                display.show(image)
                log.info("Pantalla actualizada")
            if real_panel:
                refresh.mark(signature)
                if image is not None:
                    _save_preview(image)
    except Exception:
        log.exception("Falló la actualización del dashboard")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
