"""Tareas: el modelo y la interfaz de las fuentes.

La fuente concreta (``tasks.json`` editable desde el panel web) llega en la
fase siguiente. Por ahora el dashboard muestra la lista vacía.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    title: str
    done: bool = False


class TaskSource(ABC):
    @abstractmethod
    def get_tasks(self) -> list[Task]:
        """Devuelve las tareas. Nunca lanza: ante un fallo, lista vacía."""
