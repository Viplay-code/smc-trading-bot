#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""download_market_data.py — CLI de Fase A: descarga y persiste OHLCV crudo de
Binance Futures para los activos/años configurados en market_data.config.

No requiere API key: futures_historical_klines es dato público (mismo
precedente que backtest.py: Client() sin credenciales).

Es el ÚNICO mecanismo para (re)generar data/raw/ — excluido de git (ver
.gitignore); si el directorio no existe o se borra, correr este script lo
reconstruye desde cero.

Uso (desde la raíz del repo):  python scripts/download_market_data.py
"""
import sys

sys.path.insert(0, ".")   # ejecutar desde la raíz del repo

from binance.client import Client

from market_data import (
    ASSETS,
    END_DATE,
    START_DATE,
    WARMUP_BUFFER_DAYS,
    download_all,
    manifest_path,
    read_manifest,
)


def hr(title: str) -> None:
    print("\n" + "═" * 68 + "\n  " + title + "\n" + "═" * 68)


def main() -> None:
    hr(f"market_data — descarga Fase A ({START_DATE} → {END_DATE}, buffer {WARMUP_BUFFER_DAYS}d)")
    print(f"  Activos: {', '.join(ASSETS)}")

    try:
        client = Client()  # datos públicos de klines históricos, sin API key
        paths = download_all(client)
    except Exception as e:
        print(f"\n  FAIL → descarga interrumpida: {type(e).__name__}: {e}")
        sys.exit(1)

    hr("Resumen")
    for path in paths:
        symbol, interval, year = path.stem.split("_")
        manifest = read_manifest(manifest_path(symbol, interval, int(year), raw_dir=path.parent))
        print(f"  OK  {path}  ({manifest['row_count']:,} filas, "
             f"{manifest['start']} → {manifest['end']})")

    print(f"\n  {len(paths)} archivo(s) escritos en data/raw/.")


if __name__ == "__main__":
    main()
