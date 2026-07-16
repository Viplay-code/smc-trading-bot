"""market_data — Fase A: descarga y almacenamiento versionado de OHLCV crudo
(Binance Futures), destino data/raw/.

Deliberadamente tonto: sin dedup, sin validación de sanity — eso es
responsabilidad exclusiva de dc_v1 (ver CLAUDE.md / TARGET_ARCHITECTURE.md).

Único punto de entrada público (regla de dependencias §2 de
TARGET_ARCHITECTURE.md): otros componentes importan solo desde acá, nunca
desde market_data.config/.client/.storage/.downloader directamente.
"""
from .config import (
    ASSETS,
    END_DATE,
    FETCHER_VERSION,
    INTERVAL_1H,
    INTERVAL_4H,
    KLINE_COLUMNS,
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
from .client import fetch_klines
from .downloader import download_all, download_asset
from .storage import manifest_path, raw_path, read_manifest, write_manifest, write_raw_csv

__all__ = [
    "ASSETS",
    "END_DATE",
    "FETCHER_VERSION",
    "INTERVAL_1H",
    "INTERVAL_4H",
    "KLINE_COLUMNS",
    "MAX_RETRIES",
    "RAW_DIR",
    "REQUEST_SLEEP_SECONDS",
    "RETRY_BACKOFF_BASE_SECONDS",
    "RETRY_BACKOFF_MAX_SECONDS",
    "START_DATE",
    "WARMUP_BUFFER_DAYS",
    "year_window",
    "years_in_range",
    "fetch_klines",
    "download_all",
    "download_asset",
    "manifest_path",
    "raw_path",
    "read_manifest",
    "write_manifest",
    "write_raw_csv",
]
