"""Franja inferior: hora de actualización y estado de los datos."""

from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from epaper import fonts
from epaper.display import BLACK
from epaper.tiles.base import Box, Tile


class FooterTile(Tile):
    name = "footer"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        font = fonts.load(16)
        mid = box.y + box.height // 2
        now = ctx["now"]
        draw.text((box.x, mid), f"actualizado {now:%H:%M}", font=font, fill=BLACK, anchor="lm")

        report = ctx["weather"]
        if report is None:
            status = "sin datos de clima"
        elif report.stale:
            fetched = report.fetched_at.astimezone(now.tzinfo)
            status = f"clima sin actualizar desde {fetched:%d/%m %H:%M}"
        else:
            status = ""
        if status:
            draw.text((box.right, mid), status, font=fonts.load(16, bold=True), fill=BLACK, anchor="rm")
