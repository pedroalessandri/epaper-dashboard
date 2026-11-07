"""Hora grande con el clima actual al lado, y la fecha debajo.

El clima actual sale de la misma consulta a Open-Meteo que el resto del
dashboard (``WeatherReport.current``). Si no está disponible, la hora ocupa
todo el ancho, como antes.
"""

from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from epaper import fonts
from epaper.display import BLACK
from epaper.icons import draw_icon
from epaper.tiles.base import Box, Tile
from epaper.tiles.text import fit_font, strftime_es, width

ROW_H = 100  # alto de la fila hora + clima actual; la fecha va debajo
NOW_W = 104  # ancho del bloque de clima actual
NOW_GAP = 14  # separación entre la hora y ese bloque
NOW_ICON = 48


class ClockTile(Tile):
    name = "clock"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        now = ctx["now"]
        fmt = ctx["cfg"]["display"]
        hora = strftime_es(now, fmt["clock_format"])
        fecha = strftime_es(now, fmt["date_format"]).lower()

        report = ctx.get("weather")
        current = report.current if report is not None else None
        hora_w = box.width - (NOW_W + NOW_GAP if current else 0)

        f_hora = fit_font(draw, hora, hora_w, 120, min_size=48, bold=True)
        f_fecha = fit_font(draw, fecha, box.width, 28, min_size=18)

        # Hora centrada en la fila, alineada a la izquierda; fecha debajo.
        _, top, _, bottom = draw.textbbox((0, 0), hora, font=f_hora)
        hora_y = box.y + (ROW_H - (bottom - top)) // 2 - top
        draw.text((box.x, hora_y), hora, font=f_hora, fill=BLACK)
        draw.text((box.x, box.y + ROW_H + 12), fecha, font=f_fecha, fill=BLACK)

        if current:
            self._draw_now(draw, Box(box.right - NOW_W, box.y, NOW_W, ROW_H), current)

    @staticmethod
    def _draw_now(draw: ImageDraw.ImageDraw, box: Box, current) -> None:
        """Ícono arriba, temperatura grande y sensación térmica debajo, centrados."""
        cx = box.x + box.width // 2
        temp = f"{round(current.temperature)}°"
        f_temp = fit_font(draw, temp, box.width, 40, min_size=28, bold=True)
        f_st = fonts.load(18)

        draw_icon(draw, current.icon, cx - NOW_ICON // 2, box.y, NOW_ICON)
        st = f"ST {round(current.apparent_temperature)}°"
        draw.text((cx, box.bottom), st, font=f_st, fill=BLACK, anchor="ms")
        # El "°" corre el texto a la derecha: se centra el número, no el conjunto.
        shift = width(draw, "°", f_temp) // 2
        draw.text((cx + shift, box.bottom - 22), temp, font=f_temp, fill=BLACK, anchor="ms")
