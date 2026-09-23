"""Hora grande y fecha debajo."""

from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from epaper.display import BLACK
from epaper.tiles.base import Box, Tile
from epaper.tiles.text import fit_font, strftime_es


class ClockTile(Tile):
    name = "clock"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        now = ctx["now"]
        fmt = ctx["cfg"]["display"]
        hora = strftime_es(now, fmt["clock_format"])
        fecha = strftime_es(now, fmt["date_format"]).lower()

        f_hora = fit_font(draw, hora, box.width, 120, min_size=48, bold=True)
        f_fecha = fit_font(draw, fecha, box.width, 28, min_size=18)

        # Hora arriba, fecha pegada abajo; ambas alineadas a la izquierda.
        _, top, _, bottom = draw.textbbox((0, 0), hora, font=f_hora)
        draw.text((box.x, box.y - top), hora, font=f_hora, fill=BLACK)
        draw.text(
            (box.x, box.y + (bottom - top) + 18), fecha, font=f_fecha, fill=BLACK
        )
