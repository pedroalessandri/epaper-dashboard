"""Carga y validación de ``config.yaml``.

La config nunca aborta el proceso: si el archivo falta, no se puede parsear o
tiene valores inválidos, se loguea el problema y se usan los defaults (clave
por clave, así un error puntual no tira abajo el resto).

Ruta: ``$EPAPER_CONFIG`` o ``config.yaml`` en la raíz del repo.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = _REPO_ROOT / "config.yaml"

# Espejo de config.example.yaml. Si se agrega una clave allá, va acá también.
DEFAULTS: dict[str, Any] = {
    "location": {
        "name": "Buenos Aires",
        "latitude": -34.6037,
        "longitude": -58.3816,
        "timezone": "America/Argentina/Buenos_Aires",
    },
    "display": {
        "clock_format": "%H:%M",
        "date_format": "%A %d de %B",
        "units": "metric",
    },
    "refresh": {
        "interval_minutes": 5,
        "quiet_hours": {"enabled": False, "start": "23:00", "end": "07:00"},
        "full_refresh_at": "04:00",
    },
    "weather": {
        "enabled": True,
        "periods": {
            "morning": [6, 12],
            "afternoon": [12, 18],
            "evening": [18, 24],
        },
        "forecast_days": 3,
    },
    "tasks": {
        "enabled": True,
        "source": "local",
        "max_visible": 6,
        "show_completed": False,
    },
    "web": {"enabled": True, "host": "0.0.0.0", "port": 8080},
}


def load(path: Path | str | None = None) -> dict[str, Any]:
    """Devuelve la config ya validada y con defaults aplicados."""
    path = Path(path or os.environ.get("EPAPER_CONFIG") or DEFAULT_PATH)
    raw: Any = {}
    try:
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        log.warning("No existe %s; se usan los defaults", path)
    except (OSError, yaml.YAMLError) as exc:
        log.error("No se pudo leer %s (%s); se usan los defaults", path, exc)

    if not isinstance(raw, dict):
        log.error("%s no es un mapeo YAML; se usan los defaults", path)
        raw = {}

    return _validate(_merge(DEFAULTS, raw, prefix=""))


def _merge(defaults: dict, given: dict, prefix: str) -> dict:
    """Merge profundo: cada clave toma el valor dado si el tipo coincide."""
    out = copy.deepcopy(defaults)
    for key, value in given.items():
        name = f"{prefix}{key}"
        if key not in defaults:
            log.warning("Clave desconocida en la config: %s (se ignora)", name)
            continue
        default = defaults[key]
        if isinstance(default, dict):
            if isinstance(value, dict):
                # weather.periods admite franjas nuevas, no solo las del default.
                if name == "weather.periods":
                    out[key] = value
                else:
                    out[key] = _merge(default, value, prefix=f"{name}.")
            else:
                log.error("%s debería ser un mapeo; se usa el default", name)
        elif _same_type(default, value):
            out[key] = float(value) if isinstance(default, float) else value
        else:
            log.error("%s=%r tiene tipo inválido; se usa el default", name, value)
    return out


def _same_type(default: Any, value: Any) -> bool:
    # bool es subclase de int: tratarlos por separado.
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float))
    return isinstance(value, type(default))


def _validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Chequeos de rango que el tipo solo no alcanza a cubrir."""
    loc = cfg["location"]
    if not -90 <= loc["latitude"] <= 90 or not -180 <= loc["longitude"] <= 180:
        log.error("Coordenadas fuera de rango; se usa la ubicación default")
        cfg["location"] = copy.deepcopy(DEFAULTS["location"])

    if cfg["refresh"]["interval_minutes"] < 3:
        # Waveshare recomienda >= 180 s entre refrescos.
        log.error("refresh.interval_minutes < 3; se usa el default")
        cfg["refresh"]["interval_minutes"] = DEFAULTS["refresh"]["interval_minutes"]

    weather = cfg["weather"]
    periods = {}
    for name, span in weather["periods"].items():
        if (
            isinstance(span, (list, tuple))
            and len(span) == 2
            and all(isinstance(h, int) and not isinstance(h, bool) for h in span)
            and 0 <= span[0] < span[1] <= 24
        ):
            periods[str(name)] = [span[0], span[1]]
        else:
            log.error("weather.periods.%s=%r inválido (se ignora)", name, span)
    if not periods:
        log.error("weather.periods quedó vacío; se usan las franjas default")
        periods = copy.deepcopy(DEFAULTS["weather"]["periods"])
    weather["periods"] = periods

    if not 0 <= weather["forecast_days"] <= 15:
        log.error("weather.forecast_days fuera de rango; se usa el default")
        weather["forecast_days"] = DEFAULTS["weather"]["forecast_days"]

    return cfg
