"""Composición de la imagen a partir de los tiles.

Todo el layout vive acá: un rectángulo por tile y las líneas divisorias.
Cambiar proporciones es tocar ``LAYOUT``.

    ┌──────────────┬──────────────────┐
    │ clock        │ weather_today    │
    ├──────────────┤                  │
    │ tasks        ├──────────────────┤
    │              │ weather_forecast │
    ├──────────────┴──────────────────┤
    │ footer                          │
    └─────────────────────────────────┘
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image, ImageDraw

from epaper import fonts
from epaper.display import BLACK, new_canvas
from epaper.tiles.base import Box, Tile
from epaper.tiles.clock import ClockTile
from epaper.tiles.footer import FooterTile
from epaper.tiles.tasks import TasksTile
from epaper.tiles.weather import WeatherForecastTile, WeatherTodayTile

log = logging.getLogger(__name__)

LAYOUT: dict[str, Box] = {
    "clock": Box(16, 14, 336, 150),
    "tasks": Box(16, 190, 336, 244),
    "weather_today": Box(388, 14, 396, 262),
    "weather_forecast": Box(388, 300, 396, 136),
    "footer": Box(16, 452, 768, 28),
}

# (x0, y0, x1, y1) de cada línea divisoria, 2 px de ancho.
DIVIDERS = [
    (368, 0, 368, 446),  # columnas
    (16, 176, 352, 176),  # reloj | tareas
    (388, 286, 784, 286),  # hoy | próximos días
    (0, 446, 800, 446),  # footer
]

TILES: dict[str, Tile] = {
    t.name: t
    for t in (
        ClockTile(),
        TasksTile(),
        WeatherTodayTile(),
        WeatherForecastTile(),
        FooterTile(),
    )
}


def render(ctx: dict[str, Any]) -> Image.Image:
    """Compone el dashboard. Un tile que falla no tira abajo el resto."""
    img = new_canvas()
    draw = ImageDraw.Draw(img)

    for line in DIVIDERS:
        draw.line(line, fill=BLACK, width=2)

    for name, box in LAYOUT.items():
        try:
            TILES[name].draw(draw, box, ctx)
        except Exception:
            log.exception("Falló el tile %s", name)
            draw.rectangle((box.x, box.y, box.right, box.bottom), fill=255)
            draw.text((box.x, box.y), f"error en {name}", font=fonts.load(16), fill=BLACK)

    return img
