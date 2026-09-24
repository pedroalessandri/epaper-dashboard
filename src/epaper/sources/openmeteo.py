"""Clima desde Open-Meteo (sin API key).

Una sola llamada HTTP trae ``hourly`` y ``daily``. Con eso se arma:

- el día corriente partido en franjas (mañana / tarde / noche, configurables),
- los días siguientes en versión resumida (máx, mín, condición).

El resultado se guarda en ``out/cache.json``. Ante cualquier fallo (red, HTTP,
respuesta mal formada) se devuelve la última caché marcada como ``stale``; si
no hay caché, ``None``. Nunca se propaga la excepción.

Uso por consola:
    python3 -m epaper.sources.openmeteo
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from epaper.storage import atomic_write_text

log = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 10

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_PATH = _REPO_ROOT / "out" / "cache.json"

HOURLY_VARS = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "weather_code",
)
DAILY_VARS = ("weather_code", "temperature_2m_max", "temperature_2m_min")

# Código WMO -> (etiqueta corta, identificador de ícono).
# Etiquetas de hasta ~14 caracteres: tienen que entrar en la columna de HOY.
# https://open-meteo.com/en/docs  (sección "WMO Weather interpretation codes")
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("despejado", "clear"),
    1: ("casi despejado", "mostly_clear"),
    2: ("algo nublado", "partly_cloudy"),
    3: ("nublado", "cloudy"),
    45: ("niebla", "fog"),
    48: ("niebla", "fog"),
    51: ("llovizna leve", "drizzle"),
    53: ("llovizna", "drizzle"),
    55: ("llovizna", "drizzle"),
    56: ("llovizna helada", "freezing_rain"),
    57: ("llovizna helada", "freezing_rain"),
    61: ("lluvia leve", "rain"),
    63: ("lluvia", "rain"),
    65: ("lluvia fuerte", "heavy_rain"),
    66: ("lluvia helada", "freezing_rain"),
    67: ("lluvia helada", "freezing_rain"),
    71: ("nevada leve", "snow"),
    73: ("nevada", "snow"),
    75: ("nevada fuerte", "snow"),
    77: ("nieve", "snow"),
    80: ("chaparrones", "showers"),
    81: ("chaparrones", "showers"),
    82: ("chaparrones", "heavy_rain"),
    85: ("nevadas", "snow"),
    86: ("nevadas", "snow"),
    95: ("tormenta", "thunderstorm"),
    96: ("granizo", "thunderstorm"),
    99: ("granizo", "thunderstorm"),
}
UNKNOWN_CONDITION = ("sin dato", "unknown")

_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def describe(code: int | None) -> tuple[str, str]:
    """Código WMO -> (etiqueta, ícono). Códigos desconocidos no fallan."""
    if code is None:
        return UNKNOWN_CONDITION
    return WMO_CODES.get(int(code), UNKNOWN_CONDITION)


@dataclass(frozen=True)
class Period:
    """Una franja horaria del día corriente."""

    name: str  # morning | afternoon | evening | ...
    start_hour: int
    end_hour: int  # exclusivo
    temperature: float  # promedio de la franja
    apparent_temperature: float  # promedio de la franja
    precipitation_probability: int  # máxima de la franja, en %
    weather_code: int  # el más frecuente de la franja
    label: str
    icon: str


@dataclass(frozen=True)
class DayForecast:
    """Resumen de un día siguiente, tomado directo de ``daily``."""

    date: date
    temperature_max: float
    temperature_min: float
    weather_code: int
    label: str
    icon: str


@dataclass(frozen=True)
class WeatherReport:
    location: str
    today: date
    periods: list[Period]
    days: list[DayForecast]
    fetched_at: datetime  # UTC
    stale: bool = False  # True si viene de la caché por un fallo de red


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------


def get_weather(
    cfg: dict[str, Any], cache_path: Path | str | None = None
) -> WeatherReport | None:
    """Pide el pronóstico; si algo falla, cae a la caché. Nunca lanza."""
    cache_path = Path(
        cache_path or os.environ.get("EPAPER_WEATHER_CACHE") or DEFAULT_CACHE_PATH
    )
    try:
        payload = _fetch(cfg)
        report = _aggregate(payload, cfg)
    except Exception as exc:  # red, HTTP, JSON o datos inesperados
        log.warning("Open-Meteo falló (%s: %s); se usa la caché", type(exc).__name__, exc)
        return _read_cache(cache_path, cfg)

    _write_cache(cache_path, report, cfg)
    return report


# --------------------------------------------------------------------------
# HTTP y agregación
# --------------------------------------------------------------------------


def _fetch(cfg: dict[str, Any]) -> dict[str, Any]:
    loc = cfg["location"]
    params = {
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "timezone": loc["timezone"],
        # hoy + los días siguientes (3 por default -> forecast_days=4)
        "forecast_days": 1 + cfg["weather"]["forecast_days"],
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
    }
    resp = requests.get(API_URL, params=params, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def _aggregate(payload: dict[str, Any], cfg: dict[str, Any]) -> WeatherReport:
    hourly = payload["hourly"]
    daily = payload["daily"]

    # "Hoy" es el primer día que devuelve la API, ya en la zona horaria pedida.
    # No se usa el reloj local: la notebook puede estar en otra zona.
    today = date.fromisoformat(daily["time"][0])

    by_hour: dict[int, dict[str, Any]] = {}
    for i, stamp in enumerate(hourly["time"]):
        ts = datetime.fromisoformat(stamp)
        if ts.date() == today:
            by_hour[ts.hour] = {var: hourly[var][i] for var in HOURLY_VARS}

    periods = []
    for name, (start, end) in cfg["weather"]["periods"].items():
        rows = [by_hour[h] for h in range(start, end) if h in by_hour]
        period = _aggregate_period(name, start, end, rows)
        if period is None:
            log.warning("Franja %s (%d-%d) sin datos horarios", name, start, end)
        else:
            periods.append(period)

    days = []
    for i in range(1, len(daily["time"])):
        code = daily["weather_code"][i]
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        if None in (code, tmax, tmin):
            log.warning("Día %s incompleto en daily; se omite", daily["time"][i])
            continue
        label, icon = describe(code)
        days.append(
            DayForecast(
                date=date.fromisoformat(daily["time"][i]),
                temperature_max=round(float(tmax), 1),
                temperature_min=round(float(tmin), 1),
                weather_code=int(code),
                label=label,
                icon=icon,
            )
        )

    return WeatherReport(
        location=cfg["location"]["name"],
        today=today,
        periods=periods,
        days=days,
        fetched_at=datetime.now(timezone.utc).replace(microsecond=0),
    )


def _aggregate_period(
    name: str, start: int, end: int, rows: list[dict[str, Any]]
) -> Period | None:
    temps = [r["temperature_2m"] for r in rows if r["temperature_2m"] is not None]
    feels = [
        r["apparent_temperature"] for r in rows if r["apparent_temperature"] is not None
    ]
    probs = [
        r["precipitation_probability"]
        for r in rows
        if r["precipitation_probability"] is not None
    ]
    codes = [int(r["weather_code"]) for r in rows if r["weather_code"] is not None]
    if not temps or not codes:
        return None

    # Código dominante: el más frecuente; en empate gana el más "severo"
    # (código WMO más alto), porque avisar lluvia importa más que avisar sol.
    counts = Counter(codes)
    code = max(counts, key=lambda c: (counts[c], c))
    label, icon = describe(code)

    return Period(
        name=name,
        start_hour=start,
        end_hour=end,
        temperature=round(sum(temps) / len(temps), 1),
        apparent_temperature=round(sum(feels) / len(feels), 1) if feels else float("nan"),
        precipitation_probability=int(max(probs)) if probs else 0,
        weather_code=code,
        label=label,
        icon=icon,
    )


# --------------------------------------------------------------------------
# Caché en disco
# --------------------------------------------------------------------------


def _write_cache(path: Path, report: WeatherReport, cfg: dict[str, Any]) -> None:
    data = {
        "latitude": cfg["location"]["latitude"],
        "longitude": cfg["location"]["longitude"],
        "report": asdict(report),
    }
    try:
        atomic_write_text(path, json.dumps(data, default=str, ensure_ascii=False, indent=1))
    except OSError as exc:
        log.error("No se pudo escribir la caché %s: %s", path, exc)


def _read_cache(path: Path, cfg: dict[str, Any]) -> WeatherReport | None:
    try:
        data = json.loads(path.read_text())
        if (data["latitude"], data["longitude"]) != (
            cfg["location"]["latitude"],
            cfg["location"]["longitude"],
        ):
            log.warning("La caché es de otra ubicación; se descarta")
            return None
        r = data["report"]
        report = WeatherReport(
            location=r["location"],
            today=date.fromisoformat(r["today"]),
            periods=[Period(**p) for p in r["periods"]],
            days=[
                DayForecast(**{**d, "date": date.fromisoformat(d["date"])})
                for d in r["days"]
            ],
            fetched_at=datetime.fromisoformat(r["fetched_at"]),
            stale=True,
        )
    except FileNotFoundError:
        log.warning("Sin caché de clima en %s", path)
        return None
    except Exception as exc:  # caché corrupta o de un formato viejo
        log.error("Caché de clima ilegible (%s: %s)", type(exc).__name__, exc)
        return None
    log.info("Clima desde caché del %s (stale)", report.fetched_at.isoformat())
    return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_PERIOD_NAMES = {"morning": "mañana", "afternoon": "tarde", "evening": "noche"}


def format_report(report: WeatherReport | None) -> str:
    if report is None:
        return "Sin datos de clima (fallo de red y sin caché)."

    def dia(d: date) -> str:
        return f"{_DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"

    estado = "STALE (caché)" if report.stale else "fresco"
    lines = [
        f"Clima · {report.location} · hoy {dia(report.today)}",
        f"obtenido {report.fetched_at.isoformat()} · {estado}",
        "",
        "HOY",
    ]
    for p in report.periods:
        nombre = _PERIOD_NAMES.get(p.name, p.name)
        lines.append(
            f"  {nombre:<7} {p.start_hour:02d}-{p.end_hour:02d}h"
            f"  {p.temperature:5.1f}°  ST {p.apparent_temperature:5.1f}°"
            f"  lluvia {p.precipitation_probability:3d}%"
            f"  [{p.weather_code:2d}] {p.label} ({p.icon})"
        )
    lines += ["", "PRÓXIMOS DÍAS"]
    for d in report.days:
        lines.append(
            f"  {dia(d.date)}  máx {d.temperature_max:5.1f}°"
            f"  mín {d.temperature_min:5.1f}°"
            f"  [{d.weather_code:2d}] {d.label} ({d.icon})"
        )
    return "\n".join(lines)


def main() -> int:
    from epaper import config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    report = get_weather(config.load())
    print(format_report(report))
    return 0 if report is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
