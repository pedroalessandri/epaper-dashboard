"""Íconos de clima dibujados con primitivas de Pillow.

En 1 bit no hay antialiasing: todo se dibuja con trazos de ancho entero, sin
fuentes de íconos. Cada ícono ocupa un cuadrado de lado ``size`` con esquina
superior izquierda en ``(x, y)``.

Los identificadores son los que devuelve ``sources.openmeteo.describe``.
"""

from __future__ import annotations

import math

from PIL import ImageDraw

from epaper.display import BLACK, WHITE


def draw_icon(draw: ImageDraw.ImageDraw, icon: str, x: int, y: int, size: int) -> None:
    fn = _ICONS.get(icon, _unknown)
    fn(draw, x, y, size)


def _stroke(size: int) -> int:
    return max(2, round(size / 22))


# --------------------------------------------------------------------------
# Piezas
# --------------------------------------------------------------------------


def _sun(draw, cx: float, cy: float, r: float, w: int, rays: bool = True) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK, width=w)
    if not rays:
        return
    for i in range(8):
        a = i * math.pi / 4
        r1, r2 = r * 1.45, r * 1.95
        draw.line(
            (cx + r1 * math.cos(a), cy + r1 * math.sin(a),
             cx + r2 * math.cos(a), cy + r2 * math.sin(a)),
            fill=BLACK, width=w,
        )


def _cloud(draw, x: float, y: float, w: float, h: float, stroke: int) -> None:
    """Nube con contorno y relleno blanco (tapa lo que haya detrás).

    Se dibuja la silueta en negro y encima la misma silueta achicada en
    blanco: así la unión de círculos queda con un solo contorno limpio.
    """

    def shapes(inset: float):
        base_top = y + h * 0.45
        return [
            ("ellipse", (x + w * 0.05, y + h * 0.35, x + w * 0.45, y + h * 0.95)),
            ("ellipse", (x + w * 0.25, y + h * 0.05, x + w * 0.70, y + h * 0.80)),
            ("ellipse", (x + w * 0.52, y + h * 0.28, x + w * 0.95, y + h * 0.95)),
            ("rect", (x + w * 0.25, base_top, x + w * 0.75, y + h * 0.95)),
        ], inset

    for color, inset in ((BLACK, 0), (WHITE, stroke)):
        items, d = shapes(inset)
        for kind, (x0, y0, x1, y1) in items:
            box = (x0 + d, y0 + d, x1 - d, y1 - d)
            if kind == "ellipse":
                draw.ellipse(box, fill=color)
            else:
                # el rectángulo no se achica por abajo lo mismo que por los lados:
                # la base de la nube es recta
                draw.rectangle(box, fill=color)


def _drops(draw, x, y, s, w, count: int, length: float, dotted: bool = False) -> None:
    """Gotas inclinadas debajo de la nube."""
    top = y + s * 0.74
    for i in range(count):
        cx = x + s * (0.28 + 0.44 * i / max(1, count - 1))
        if dotted:
            for j in range(2):
                py = top + s * 0.02 + j * s * 0.15
                draw.ellipse((cx - w, py - w, cx + w, py + w), fill=BLACK)
        else:
            draw.line((cx, top, cx - s * 0.06, top + s * length), fill=BLACK, width=w)


def _flakes(draw, x, y, s, w) -> None:
    top = y + s * 0.80
    r = s * 0.07
    for cx in (x + s * 0.30, x + s * 0.50, x + s * 0.70):
        cy = top + (s * 0.05 if cx == x + s * 0.50 else 0)
        for a in (0, math.pi / 3, 2 * math.pi / 3):
            dx, dy = r * math.cos(a), r * math.sin(a)
            draw.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=BLACK, width=max(1, w - 1))


# --------------------------------------------------------------------------
# Íconos
# --------------------------------------------------------------------------


def _clear(draw, x, y, s):
    _sun(draw, x + s / 2, y + s / 2, s * 0.22, _stroke(s))


def _mostly_clear(draw, x, y, s):
    w = _stroke(s)
    _sun(draw, x + s * 0.45, y + s * 0.42, s * 0.19, w)
    _cloud(draw, x + s * 0.45, y + s * 0.58, s * 0.52, s * 0.36, w)


def _partly_cloudy(draw, x, y, s):
    w = _stroke(s)
    _sun(draw, x + s * 0.36, y + s * 0.36, s * 0.17, w)
    _cloud(draw, x + s * 0.18, y + s * 0.36, s * 0.80, s * 0.52, w)


def _cloudy(draw, x, y, s):
    _cloud(draw, x + s * 0.05, y + s * 0.20, s * 0.90, s * 0.60, _stroke(s))


def _rain_cloud(draw, x, y, s):
    _cloud(draw, x + s * 0.05, y + s * 0.10, s * 0.90, s * 0.58, _stroke(s))


def _drizzle(draw, x, y, s):
    _rain_cloud(draw, x, y, s)
    _drops(draw, x, y, s, _stroke(s), 3, 0, dotted=True)


def _rain(draw, x, y, s):
    _rain_cloud(draw, x, y, s)
    _drops(draw, x, y, s, _stroke(s), 3, 0.18)


def _heavy_rain(draw, x, y, s):
    _rain_cloud(draw, x, y, s)
    _drops(draw, x, y, s, _stroke(s), 4, 0.22)


def _showers(draw, x, y, s):
    w = _stroke(s)
    _sun(draw, x + s * 0.30, y + s * 0.26, s * 0.14, w)
    _cloud(draw, x + s * 0.15, y + s * 0.18, s * 0.82, s * 0.52, w)
    _drops(draw, x + s * 0.05, y, s, w, 3, 0.18)


def _freezing_rain(draw, x, y, s):
    w = _stroke(s)
    _rain_cloud(draw, x, y, s)
    _drops(draw, x, y, s, w, 2, 0.18)
    cx, cy = x + s * 0.50, y + s * 0.85
    r = s * 0.06
    draw.line((cx - r, cy, cx + r, cy), fill=BLACK, width=w)
    draw.line((cx, cy - r, cx, cy + r), fill=BLACK, width=w)


def _snow(draw, x, y, s):
    _rain_cloud(draw, x, y, s)
    _flakes(draw, x, y, s, _stroke(s))


def _thunderstorm(draw, x, y, s):
    _rain_cloud(draw, x, y, s)
    pts = [
        (x + s * 0.55, y + s * 0.58),
        (x + s * 0.40, y + s * 0.80),
        (x + s * 0.52, y + s * 0.80),
        (x + s * 0.44, y + s * 0.98),
        (x + s * 0.66, y + s * 0.72),
        (x + s * 0.54, y + s * 0.72),
        (x + s * 0.62, y + s * 0.58),
    ]
    draw.polygon(pts, fill=BLACK)


def _fog(draw, x, y, s):
    w = _stroke(s)
    for i, (a, b) in enumerate(((0.12, 0.88), (0.20, 0.80), (0.12, 0.88), (0.22, 0.72))):
        yy = y + s * (0.30 + i * 0.14)
        draw.line((x + s * a, yy, x + s * b, yy), fill=BLACK, width=w)


def _unknown(draw, x, y, s):
    w = _stroke(s)
    draw.rectangle((x + s * 0.2, y + s * 0.2, x + s * 0.8, y + s * 0.8), outline=BLACK, width=w)
    draw.line((x + s * 0.2, y + s * 0.2, x + s * 0.8, y + s * 0.8), fill=BLACK, width=w)


_ICONS = {
    "clear": _clear,
    "mostly_clear": _mostly_clear,
    "partly_cloudy": _partly_cloudy,
    "cloudy": _cloudy,
    "fog": _fog,
    "drizzle": _drizzle,
    "rain": _rain,
    "heavy_rain": _heavy_rain,
    "freezing_rain": _freezing_rain,
    "showers": _showers,
    "snow": _snow,
    "thunderstorm": _thunderstorm,
    "unknown": _unknown,
}

ICON_IDS = tuple(_ICONS)
