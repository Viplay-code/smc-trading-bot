#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_data/storage.py — Persistencia de crudo (Fase A).

Escribe exactamente lo que Binance devuelve: sin dedup, sin validación de
sanity, sin coerción de tipos — eso es responsabilidad exclusiva de
dc_v1.prepare_raw (ver CLAUDE.md / TARGET_ARCHITECTURE.md). Un CSV por
(symbol, interval, year), con un manifest JSON sidecar que documenta qué
ventana se pidió y qué se obtuvo.

Convención de ruta (data/raw/, excluido de git — ver .gitignore):
  data/raw/{symbol}_{interval}_{year}.csv
  data/raw/{symbol}_{interval}_{year}.manifest.json
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path

from .config import KLINE_COLUMNS, RAW_DIR


def raw_path(symbol: str, interval: str, year: int, raw_dir: str = RAW_DIR) -> Path:
    """Ruta del CSV crudo para (symbol, interval, year)."""
    return Path(raw_dir) / f"{symbol}_{interval}_{year}.csv"


def manifest_path(symbol: str, interval: str, year: int, raw_dir: str = RAW_DIR) -> Path:
    """Ruta del manifest sidecar de (symbol, interval, year)."""
    return Path(raw_dir) / f"{symbol}_{interval}_{year}.manifest.json"


def write_raw_csv(rows: list[list], path: Path) -> int:
    """Escribe `rows` tal cual (sin dedup, sin sanity, sin coerción de tipos),
    con el header fijo KLINE_COLUMNS (12 columnas nativas de una kline de
    Binance). Crea el directorio destino si no existe.

    Retorna la cantidad de filas escritas.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(KLINE_COLUMNS)
        writer.writerows(rows)
    return len(rows)


def write_manifest(path: Path, *, symbol: str, interval: str, year: int,
                   start: str, end: str, row_count: int, fetcher_version: str,
                   fetched_at: str | None = None) -> None:
    """Escribe el manifest sidecar (JSON) junto al CSV crudo.

    `start`/`end` son la ventana PEDIDA (la que devuelve year_window), no una
    garantía de lo que Binance efectivamente devolvió — eso lo audita
    `row_count`. `fetched_at` es opcional para que los tests puedan fijar un
    valor determinista; si no se pasa, se usa la hora UTC actual.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "symbol": symbol,
        "interval": interval,
        "year": year,
        "start": start,
        "end": end,
        "row_count": row_count,
        "fetcher_version": fetcher_version,
        "fetched_at": fetched_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def read_manifest(path: Path) -> dict:
    """Lee un manifest sidecar ya escrito."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
