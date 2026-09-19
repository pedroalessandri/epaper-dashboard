"""Entrypoint del dashboard.

Fase 0: dibuja hora y fecha, nada más. El objetivo de esta fase es validar la
cadena completa (render -> display -> panel), no el diseño final.

Uso:
    EPAPER_BACKEND=mock      python3 -m epaper.main     # notebook
    EPAPER_BACKEND=waveshare python3 -m epaper.main     # en la Pi
    python3 -m epaper.main --clear                      # limpiar el panel
"""

from __future__ import annotations

import argparse
import locale
import logging
import sys
from datetime import datetime

from PIL import ImageDraw

from epaper import fonts
from epaper.display import BLACK, WIDTH, get_display, new_canvas

log = logging.getLogger(__name__)


def _setup_locale() -> None:
    """Intenta poner el locale en castellano para los nombres de día y mes."""
    for candidate in ("es_AR.UTF-8", "es_ES.UTF-8", "es_AR", "es_ES"):
        try:
            locale.setlocale(locale.LC_TIME, candidate)
            return
        except locale.Error:
            continue
    log.info("Sin locale en castellano; los nombres de día y mes van en inglés")


def render(now: datetime | None = None):
    """Compone la imagen de la fase 0: hora grande y fecha debajo."""
    now = now or datetime.now()

    img = new_canvas()
    draw = ImageDraw.Draw(img)

    hora = now.strftime("%H:%M")
    fecha = now.strftime("%A %d de %B").lower()

    f_hora = fonts.load(180, bold=True)
    f_fecha = fonts.load(40)

    # Centrado horizontal usando la caja real del texto, no una estimación.
    for text, font, y in ((hora, f_hora, 110), (fecha, f_fecha, 300)):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        x = (WIDTH - (right - left)) // 2 - left
        draw.text((x, y - top), text, font=font, fill=BLACK)

    return img


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
    _setup_locale()

    try:
        with get_display(args.backend) as display:
            if args.clear:
                display.clear()
                log.info("Pantalla limpiada")
            else:
                display.show(render())
                log.info("Dashboard actualizado")
    except Exception:
        log.exception("Falló la actualización del dashboard")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
