"""Clima: el día corriente por franjas y los días siguientes resumidos."""

from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from epaper import fonts
from epaper.display import BLACK
from epaper.icons import draw_icon
from epaper.tiles.base import Box, Tile
from epaper.tiles.text import DIAS_CORTOS, ellipsize, width

PERIOD_NAMES = {"morning": "mañana", "afternoon": "tarde", "evening": "noche"}


def _deg(value: float) -> str:
    return f"{round(value)}°"


def _no_data(draw: ImageDraw.ImageDraw, box: Box) -> None:
    draw.text(
        (box.x + box.width // 2, box.y + box.height // 2),
        "sin datos de clima",
        font=fonts.load(20),
        fill=BLACK,
        anchor="mm",
    )


class WeatherTodayTile(Tile):
    """Título HOY y una fila por franja: nombre, ícono, temperatura, detalle."""

    name = "weather_today"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        f_title = fonts.load(20, bold=True)
        draw.text((box.x, box.y), "HOY", font=f_title, fill=BLACK)
        report = ctx["weather"]
        body = Box(box.x, box.y + 30, box.width, box.height - 30)
        if report is None or not report.periods:
            _no_data(draw, body)
            return

        f_name = fonts.load(22, bold=True)
        f_temp = fonts.load(36, bold=True)
        f_small = fonts.load(18)

        rows = report.periods
        row_h = body.height // len(rows)
        icon = min(52, row_h - 8)
        # columnas: nombre+condición | ícono | temperatura | ST y lluvia
        # anchos medidos: "-10°" en bold 36 = 83 px, "lluvia 100%" en 18 = 105 px
        col_icon = body.x + 144
        col_temp = col_icon + icon + 10
        col_detail = col_temp + 84
        detail_w = body.right - col_detail

        for i, p in enumerate(rows):
            top = body.y + i * row_h
            mid = top + row_h // 2
            name = PERIOD_NAMES.get(p.name, p.name)
            draw.text((body.x, mid - 3), name, font=f_name, fill=BLACK, anchor="ls")
            label = ellipsize(draw, p.label, f_small, col_icon - body.x - 8)
            draw.text((body.x, mid + 5), label, font=f_small, fill=BLACK, anchor="lt")

            draw_icon(draw, p.icon, col_icon, mid - icon // 2, icon)
            draw.text((col_temp, mid), _deg(p.temperature), font=f_temp, fill=BLACK, anchor="lm")

            st = ellipsize(draw, f"ST {_deg(p.apparent_temperature)}", f_small, detail_w)
            rain = ellipsize(draw, f"lluvia {p.precipitation_probability}%", f_small, detail_w)
            draw.text((col_detail, mid - 3), st, font=f_small, fill=BLACK, anchor="ls")
            draw.text((col_detail, mid + 5), rain, font=f_small, fill=BLACK, anchor="lt")


class WeatherForecastTile(Tile):
    """Los días siguientes en columnas: día, ícono, máx / mín."""

    name = "weather_forecast"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        report = ctx["weather"]
        if report is None or not report.days:
            _no_data(draw, box)
            return

        f_day = fonts.load(20, bold=True)
        f_temp = fonts.load(22, bold=True)
        f_min = fonts.load(22)

        days = report.days
        col_w = box.width // len(days)
        icon = min(56, box.height - 70)
        for i, d in enumerate(days):
            cx = box.x + i * col_w + col_w // 2
            day = f"{DIAS_CORTOS[d.date.weekday()]} {d.date.day}"
            draw.text((cx, box.y), day, font=f_day, fill=BLACK, anchor="mt")
            draw_icon(draw, d.icon, cx - icon // 2, box.y + 28, icon)

            # "21° / 12°": la máxima en bold, centrado el conjunto
            hi, sep, lo = _deg(d.temperature_max), " / ", _deg(d.temperature_min)
            total = width(draw, hi, f_temp) + width(draw, sep + lo, f_min)
            x = cx - total // 2
            y = box.y + 28 + icon + 8
            draw.text((x, y), hi, font=f_temp, fill=BLACK)
            draw.text((x + width(draw, hi, f_temp), y), sep + lo, font=f_min, fill=BLACK)
