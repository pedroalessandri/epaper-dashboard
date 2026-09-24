"""Panel de administración del dashboard.

Corre en la misma Pi (``epaper-web.service``), sin autenticación: es para la
red de la casa. Secciones: Tareas y Mensaje (alterna la pantalla entre el
dashboard y un texto con marco). Una sección nueva es otra entrada en
``SECTIONS`` más su template.

Cada cambio pide un refresco del panel. El agendador respeta el mínimo de
180 s entre refrescos: si hace falta esperar, deja uno solo programado para
cuando se cumpla el plazo, así cargar cinco tareas seguidas es un refresco.

Uso local (notebook):
    EPAPER_BACKEND=mock uvicorn epaper.web.app:app --port 8080
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from epaper import refresh
from epaper.display import MockDisplay
from epaper.sources.message import MAX_TEXT, MessageStore
from epaper.sources.tasks import LocalTaskSource

log = logging.getLogger(__name__)

SECTIONS = [("/", "Tareas"), ("/mensaje", "Mensaje")]

app = FastAPI(title="epaper", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
tasks = LocalTaskSource()
messages = MessageStore()


class RefreshScheduler:
    """Dispara el refresco del panel sin pasarse de la cadencia mínima."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._due: float | None = None  # epoch del refresco agendado
        self._last_trigger = 0.0

    def _wait(self) -> float:
        since_trigger = time.time() - self._last_trigger
        return max(refresh.seconds_until_allowed(), refresh.MIN_INTERVAL_S - since_trigger)

    def request(self) -> None:
        with self._lock:
            if self._timer is not None:
                return  # ya hay uno agendado; este cambio entra en ese
            wait = self._wait()
            if wait <= 0:
                self._trigger_locked()
            else:
                self._due = time.time() + wait + 2
                self._timer = threading.Timer(wait + 2, self._fire)
                self._timer.daemon = True
                self._timer.start()
                log.info("Refresco agendado en %.0f s", wait + 2)

    def pending_in(self) -> float | None:
        """Segundos hasta el refresco agendado, o None si no hay."""
        with self._lock:
            return None if self._due is None else max(0.0, self._due - time.time())

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
            self._due = None
            self._trigger_locked()

    def _trigger_locked(self) -> None:
        self._last_trigger = time.time()
        if os.environ.get("EPAPER_BACKEND", "mock").lower() == "waveshare":
            # systemd serializa: si el timer justo está corriendo, no hay
            # dos procesos peleando por el SPI.
            cmd = ["sudo", "-n", "systemctl", "start", "--no-block", "epaper.service"]
        else:
            cmd = [sys.executable, "-m", "epaper.main"]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("Refresco disparado: %s", " ".join(cmd))
        except OSError as exc:
            log.error("No se pudo disparar el refresco: %s", exc)


scheduler = RefreshScheduler()


def _back(to: str = "/") -> RedirectResponse:
    # 303: después de un POST el navegador vuelve con GET (patrón PRG).
    return RedirectResponse(to, status_code=303)


def _page(request: Request, template: str, current: str, **extra):
    return templates.TemplateResponse(
        request,
        template,
        {
            "sections": SECTIONS,
            "current": current,
            "screen": messages.get(),
            "status": _status(),
            "stamp": int(time.time()),
            **extra,
        },
    )


def _status() -> str:
    pending = scheduler.pending_in()
    if pending is not None:
        return f"la pantalla se actualiza en {int(pending)} s"
    since = refresh.seconds_since_last()
    if since is None:
        return "la pantalla todavía no se actualizó"
    if since < 90:
        return "pantalla actualizada recién"
    return f"pantalla actualizada hace {int(since // 60)} min"


@app.get("/")
def tasks_page(request: Request):
    return _page(request, "tareas.html", "/", tasks=tasks.get_tasks())


@app.post("/tareas")
def add_task(title: str = Form("")):
    if tasks.add(title):
        scheduler.request()
    return _back()


@app.post("/tareas/limpiar")
def clear_done():
    tasks.clear_done()
    scheduler.request()
    return _back()


@app.post("/tareas/{task_id}/{action}")
def task_action(task_id: str, action: str):
    actions = {
        "toggle": lambda: tasks.toggle(task_id),
        "borrar": lambda: tasks.delete(task_id),
        "subir": lambda: tasks.move(task_id, -1),
        "bajar": lambda: tasks.move(task_id, +1),
    }
    if action in actions:
        actions[action]()
        scheduler.request()
    return _back()


@app.get("/mensaje")
def message_page(request: Request):
    return _page(request, "mensaje.html", "/mensaje", max_text=MAX_TEXT)


@app.post("/mensaje")
def save_message(text: str = Form(""), action: str = Form("mostrar")):
    if action == "mostrar" and text.strip():
        messages.show_message(text)
        scheduler.request()
    else:
        before = messages.get()
        after = messages.save_text(text)
        if before.shows_message != after.shows_message or (
            after.shows_message and before.text != after.text
        ):
            scheduler.request()
    return _back("/mensaje")


@app.post("/modo/dashboard")
def show_dashboard(volver: str = Form("/")):
    messages.show_dashboard()
    scheduler.request()
    return _back(volver if volver in dict(SECTIONS) else "/")


@app.post("/refrescar")
def refresh_now(volver: str = Form("/")):
    scheduler.request()
    return _back(volver if volver in dict(SECTIONS) else "/")


@app.get("/preview.png")
def preview():
    path = MockDisplay().out_path
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
