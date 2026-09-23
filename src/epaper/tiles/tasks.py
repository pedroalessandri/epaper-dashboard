"""Lista de tareas con checkbox, con recorte de desbordes."""

from __future__ import annotations

from typing import Any

from PIL import ImageDraw

from epaper import fonts
from epaper.display import BLACK
from epaper.tiles.base import Box, Tile
from epaper.tiles.text import ellipsize

LINE_H = 34
CHECK = 18


class TasksTile(Tile):
    name = "tasks"

    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        cfg = ctx["cfg"]["tasks"]
        f_title = fonts.load(20, bold=True)
        f_item = fonts.load(20)
        draw.text((box.x, box.y), "TAREAS", font=f_title, fill=BLACK)

        tasks = ctx.get("tasks") or []
        if not cfg["show_completed"]:
            tasks = [t for t in tasks if not t.done]

        top = box.y + 36
        if not tasks:
            draw.text((box.x, top), "sin tareas pendientes", font=f_item, fill=BLACK)
            return

        # Cuántas filas entran, acotado por la config. Si sobran tareas, la
        # última fila se usa para "+N más".
        fit = max(1, (box.bottom - top) // LINE_H)
        limit = min(fit, cfg["max_visible"])
        visible = tasks if len(tasks) <= limit else tasks[: limit - 1]
        text_x = box.x + CHECK + 12

        for i, task in enumerate(visible):
            mid = top + i * LINE_H + LINE_H // 2
            y0 = mid - CHECK // 2
            draw.rectangle((box.x, y0, box.x + CHECK, y0 + CHECK), outline=BLACK, width=2)
            if task.done:
                draw.line((box.x + 4, mid, box.x + 8, y0 + CHECK - 4), fill=BLACK, width=2)
                draw.line((box.x + 8, y0 + CHECK - 4, box.x + CHECK - 3, y0 + 3), fill=BLACK, width=2)
            title = ellipsize(draw, task.title, f_item, box.right - text_x)
            draw.text((text_x, mid), title, font=f_item, fill=BLACK, anchor="lm")

        hidden = len(tasks) - len(visible)
        if hidden:
            mid = top + len(visible) * LINE_H + LINE_H // 2
            draw.text((text_x, mid), f"+{hidden} más", font=fonts.load(20, bold=True), fill=BLACK, anchor="lm")
