"""Tareas: el modelo, la interfaz de las fuentes y la fuente local.

La fuente local guarda todo en ``tasks.json`` (raíz del repo, o
``$EPAPER_TASKS``). La escribe el panel web y la lee el dashboard; cada
escritura es atómica y se fuerza a disco, porque la Pi se desenchufa sin
apagar y un archivo a medio escribir se pierde entero.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, replace
from pathlib import Path

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = _REPO_ROOT / "tasks.json"


@dataclass(frozen=True)
class Task:
    title: str
    done: bool = False
    id: str = ""


class TaskSource(ABC):
    @abstractmethod
    def get_tasks(self) -> list[Task]:
        """Devuelve las tareas. Nunca lanza: ante un fallo, lista vacía."""


class LocalTaskSource(TaskSource):
    """Tareas en un JSON local, editables desde el panel web."""

    MAX_TITLE = 200

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or os.environ.get("EPAPER_TASKS") or DEFAULT_PATH)
        # El panel web atiende requests en varios threads.
        self._lock = threading.Lock()

    # -- lectura -----------------------------------------------------------

    def get_tasks(self) -> list[Task]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [
                Task(title=str(t["title"]), done=bool(t.get("done")), id=str(t["id"]))
                for t in data["tasks"]
            ]
        except FileNotFoundError:
            return []
        except Exception as exc:  # JSON roto, formato inesperado
            log.error("No se pudo leer %s (%s: %s)", self.path, type(exc).__name__, exc)
            return []

    # -- escritura ---------------------------------------------------------

    def add(self, title: str) -> Task | None:
        title = " ".join(title.split())[: self.MAX_TITLE]
        if not title:
            return None
        task = Task(title=title, id=uuid.uuid4().hex[:8])
        with self._lock:
            self._save(self.get_tasks() + [task])
        return task

    def toggle(self, task_id: str) -> None:
        with self._lock:
            tasks = [replace(t, done=not t.done) if t.id == task_id else t for t in self.get_tasks()]
            self._save(tasks)

    def delete(self, task_id: str) -> None:
        with self._lock:
            self._save([t for t in self.get_tasks() if t.id != task_id])

    def clear_done(self) -> None:
        with self._lock:
            self._save([t for t in self.get_tasks() if not t.done])

    def move(self, task_id: str, offset: int) -> None:
        """Mueve una tarea ``offset`` posiciones (-1 sube, +1 baja)."""
        with self._lock:
            tasks = self.get_tasks()
            idx = next((i for i, t in enumerate(tasks) if t.id == task_id), None)
            if idx is None:
                return
            new = max(0, min(len(tasks) - 1, idx + offset))
            tasks.insert(new, tasks.pop(idx))
            self._save(tasks)

    def _save(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        payload = json.dumps(
            {"tasks": [asdict(t) for t in tasks]}, ensure_ascii=False, indent=1
        )
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(self.path)
        # fsync del directorio para que el rename también quede en disco.
        dir_fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
