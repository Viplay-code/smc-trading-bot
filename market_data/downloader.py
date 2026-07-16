#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_data/downloader.py — Orquestador de descarga (Fase A).

Une client.fetch_klines + storage.write_raw_csv/write_manifest en una unidad
por (symbol, year), y recorre secuencialmente todos los (symbol, year)
configurados con pacing entre descargas (config.REQUEST_SLEEP_SECONDS).

Dos sleeps distintos, deliberadamente separados:
  - retry_sleep_fn: backoff DENTRO de una sola llamada a fetch_klines
    (ver client.py:_with_retry) ante error transitorio.
  - pace_sleep_fn: pausa ENTRE descargas sucesivas de este loop, para no
    ráfaguear el weight budget de Binance incluso sin errores.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from binance.client import Client

from .client import fetch_klines
from .config import (
    ASSETS,
    END_DATE,
    FETCHER_VERSION,
    INTERVAL_1H,
    MAX_RETRIES,
    RAW_DIR,
    REQUEST_SLEEP_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
    RETRY_BACKOFF_MAX_SECONDS,
    START_DATE,
    WARMUP_BUFFER_DAYS,
    year_window,
    years_in_range,
)
from .storage import manifest_path, raw_path, write_manifest, write_raw_csv


def download_asset(client: Client, symbol: str, year: int, *,
                   interval: str = INTERVAL_1H,
                   raw_dir: str = RAW_DIR,
                   start_date: str = START_DATE,
                   end_date: str = END_DATE,
                   buffer_days: int = WARMUP_BUFFER_DAYS,
                   max_retries: int = MAX_RETRIES,
                   backoff_base: float = RETRY_BACKOFF_BASE_SECONDS,
                   backoff_max: float = RETRY_BACKOFF_MAX_SECONDS,
                   retry_sleep_fn: Callable[[float], None] = time.sleep) -> Path:
    """Descarga y persiste un único (symbol, interval, year): fetch + CSV +
    manifest. `year` debe pertenecer a years_in_range(start_date, end_date) —
    year_window() lo valida fail-fast, no se reimplementa acá.

    Retorna la ruta del CSV escrito.
    """
    start, end = year_window(year, buffer_days, start_date, end_date)
    rows = fetch_klines(
        client, symbol, interval, start, end,
        max_retries=max_retries, backoff_base=backoff_base,
        backoff_max=backoff_max, sleep_fn=retry_sleep_fn,
    )
    path = raw_path(symbol, interval, year, raw_dir)
    row_count = write_raw_csv(rows, path)
    write_manifest(
        manifest_path(symbol, interval, year, raw_dir),
        symbol=symbol, interval=interval, year=year,
        start=start, end=end, row_count=row_count,
        fetcher_version=FETCHER_VERSION,
    )
    return path


def download_all(client: Client, *,
                 assets: tuple[str, ...] = ASSETS,
                 years: list[int] | None = None,
                 interval: str = INTERVAL_1H,
                 raw_dir: str = RAW_DIR,
                 start_date: str = START_DATE,
                 end_date: str = END_DATE,
                 buffer_days: int = WARMUP_BUFFER_DAYS,
                 max_retries: int = MAX_RETRIES,
                 backoff_base: float = RETRY_BACKOFF_BASE_SECONDS,
                 backoff_max: float = RETRY_BACKOFF_MAX_SECONDS,
                 retry_sleep_fn: Callable[[float], None] = time.sleep,
                 request_sleep_seconds: float = REQUEST_SLEEP_SECONDS,
                 pace_sleep_fn: Callable[[float], None] = time.sleep) -> list[Path]:
    """Descarga `assets × years` secuencialmente (nunca en paralelo — simple y
    respetuoso del rate limit). `years=None` los deriva de years_in_range(),
    nunca hardcodeados. Pausa `request_sleep_seconds` entre descargas
    sucesivas (no tras la última).

    Orden año-mayor (2022 de todos los activos, luego 2023, luego 2024): si la
    descarga se interrumpe a mitad de camino, queda un período completo
    disponible para los 3 activos antes que cualquier otro — la investigación
    (organizada por período, ver FRAMEWORK.md) puede arrancar con ese período
    sin esperar el dataset completo. Es una decisión arquitectónica, no de
    rendimiento: no hay dependencia entre archivos que favorezca un orden
    sobre otro.

    Retorna las rutas de los CSV escritos, en el orden en que se generaron.
    """
    resolved_years = years if years is not None else years_in_range(start_date, end_date)
    jobs = [(symbol, year) for year in resolved_years for symbol in assets]

    paths = []
    for i, (symbol, year) in enumerate(jobs):
        paths.append(download_asset(
            client, symbol, year,
            interval=interval, raw_dir=raw_dir,
            start_date=start_date, end_date=end_date, buffer_days=buffer_days,
            max_retries=max_retries, backoff_base=backoff_base,
            backoff_max=backoff_max, retry_sleep_fn=retry_sleep_fn,
        ))
        if i < len(jobs) - 1:
            pace_sleep_fn(request_sleep_seconds)
    return paths
