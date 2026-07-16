#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_data/config.py — Fuente única de constantes de descarga (Fase A).

Nada de rangos de fechas ni de años hardcodeados fuera de aquí: START_DATE,
END_DATE y WARMUP_BUFFER_DAYS son los únicos parámetros libres; todo lo demás
(qué años cubrir, qué ventana descargar por año) se deriva de ellos con
years_in_range()/year_window().

Convención de archivo (mantenida, no se migra a archivo continuo por ahora):
un CSV crudo por (activo, intervalo, año), con buffer de warmup embebido antes
del 1-ene de ese año — ver storage.py (próximo commit).
"""
from __future__ import annotations

import datetime as _dt

# --------------------------------------------------------------------------- #
# Versión del productor de datos crudos (fuente única).                        #
# Importada por versions.py (DATASET_VERSION) desde el punto de entrada        #
# público `market_data`, nunca desde este submódulo directamente.             #
# --------------------------------------------------------------------------- #
FETCHER_VERSION = "market-data-v1"

# --------------------------------------------------------------------------- #
# Activos y timeframes (FRAMEWORK.md)                                          #
# --------------------------------------------------------------------------- #
ASSETS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

INTERVAL_1H = "1h"
INTERVAL_4H = "4h"  # declarado para reuso futuro (bot en vivo); Fase A solo descarga 1H,
                    # dc_v1 deriva el 4H por resample interno (add_htf) y no lo necesita.

# --------------------------------------------------------------------------- #
# Destino (excluido de git — ver .gitignore, commit posterior)                 #
# --------------------------------------------------------------------------- #
RAW_DIR = "data/raw"

# --------------------------------------------------------------------------- #
# Ventana de fechas de investigación (configurable)                            #
# --------------------------------------------------------------------------- #
START_DATE = "2022-01-01"  # inicio del primer período (in-sample, FRAMEWORK.md)
END_DATE = "2025-01-01"    # fin exclusivo del último período (blind test 2024)

# --------------------------------------------------------------------------- #
# Buffer de warmup por año (configurable)                                      #
# --------------------------------------------------------------------------- #
# Mínimo estricto: 800 barras 1H (~33.3 días) para que htf_ema200_prev deje de
# ser NaN (P-5, DC-v1_Precisiones_Implementacion.md). Se deja margen.
WARMUP_BUFFER_DAYS = 90

# --------------------------------------------------------------------------- #
# Rate limiting / retry (configurable)                                         #
# --------------------------------------------------------------------------- #
REQUEST_SLEEP_SECONDS = 0.5       # pausa entre descargas sucesivas (activo, año)
MAX_RETRIES = 5                   # intentos totales ante error transitorio
RETRY_BACKOFF_BASE_SECONDS = 2.0  # backoff exponencial: base * 2**intento
RETRY_BACKOFF_MAX_SECONDS = 60.0  # techo del backoff (salvo Retry-After explícito)

# --------------------------------------------------------------------------- #
# Columnas crudas de una kline de Binance (orden nativo, sin interpretar)      #
# --------------------------------------------------------------------------- #
KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)


def years_in_range(start_date: str = START_DATE, end_date: str = END_DATE) -> list[int]:
    """Años calendario cubiertos por [start_date, end_date), extremo derecho excluido.

    Si end_date cae exactamente en 1-ene, ese año queda excluido (no hay ninguna
    barra suya dentro del rango semiabierto).
    """
    start = _dt.date.fromisoformat(start_date)
    end = _dt.date.fromisoformat(end_date)
    if end <= start:
        raise ValueError(
            f"years_in_range: end_date ({end_date}) debe ser posterior "
            f"a start_date ({start_date})"
        )
    years = list(range(start.year, end.year + 1))
    if end.month == 1 and end.day == 1:
        years = [y for y in years if y < end.year]
    return years


def year_window(year: int, buffer_days: int = WARMUP_BUFFER_DAYS,
                start_date: str = START_DATE,
                end_date: str = END_DATE) -> tuple[str, str]:
    """Ventana de descarga para `year`: inicio con buffer de warmup, fin exclusivo.

    Fin = min((year+1)-01-01, end_date) — el último año no se pasa de END_DATE
    si este recorta antes de un año calendario completo.

    Contrato autocontenido (fail-fast): `year` debe pertenecer a
    years_in_range(start_date, end_date). No basta con documentar esa
    precondición para que el llamador la respete — se valida aquí, para que un
    año fuera del rango configurado falle de inmediato con un error
    descriptivo en vez de producir una ventana aparentemente válida para un
    año que nunca debió descargarse.
    """
    valid_years = years_in_range(start_date, end_date)
    if year not in valid_years:
        raise ValueError(
            f"year_window: year {year} fuera del rango configurado "
            f"[{start_date}, {end_date}) — años válidos: {valid_years}"
        )
    window_start = _dt.date(year, 1, 1) - _dt.timedelta(days=buffer_days)
    next_year_start = _dt.date(year + 1, 1, 1)
    hard_end = _dt.date.fromisoformat(end_date)
    window_end = min(next_year_start, hard_end)
    return window_start.isoformat(), window_end.isoformat()
