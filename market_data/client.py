#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_data/client.py — Fetch de klines crudas contra Binance Futures (Fase A).

Wrapper delgado: no parsea ni interpreta el resultado (eso es de
dc_v1.prepare_raw). El único valor agregado acá es el manejo de reintentos
ante errores transitorios de red/rate-limit — ver `_with_retry`.

Límite de responsabilidad: el pacing ENTRE descargas sucesivas
(config.REQUEST_SLEEP_SECONDS) no vive acá, es del loop de downloader.py. Este
módulo solo sabe reintentar UNA llamada.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException

from .config import MAX_RETRIES, RETRY_BACKOFF_BASE_SECONDS, RETRY_BACKOFF_MAX_SECONDS

T = TypeVar("T")

# Códigos de rate-limit/baneo temporal de Binance (peso excedido / IP baneada).
_RATE_LIMIT_STATUS_CODES = (429, 418)


def _retry_after_seconds(exc: BinanceAPIException) -> float | None:
    """Extrae Retry-After (segundos) del header de la respuesta, si Binance lo
    envía. Binance lo emite como número de segundos, no como fecha HTTP; si no
    está presente o no es parseable, se delega al backoff exponencial."""
    response = exc.response
    if response is None:
        return None
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def _is_transient(exc: Exception) -> bool:
    """429/418 (rate-limit), 5xx, y errores de red ameritan reintento.
    Cualquier otro 4xx de BinanceAPIException (símbolo inválido, parámetros
    mal formados, etc.) NO es transitorio: reintentarlo nunca lo arregla."""
    if isinstance(exc, BinanceAPIException):
        return exc.status_code in _RATE_LIMIT_STATUS_CODES or exc.status_code >= 500
    return isinstance(exc, (RequestException, BinanceRequestException))


def _with_retry(fn: Callable[[], T], *, max_retries: int = MAX_RETRIES,
                backoff_base: float = RETRY_BACKOFF_BASE_SECONDS,
                backoff_max: float = RETRY_BACKOFF_MAX_SECONDS,
                sleep_fn: Callable[[float], None] = time.sleep) -> T:
    """Ejecuta `fn()` reintentando ante errores transitorios (ver
    `_is_transient`). `max_retries` es el número TOTAL de intentos (no de
    reintentos adicionales). Un error no transitorio, o agotar los intentos,
    propaga la excepción de inmediato — fallar ruidoso, nunca en silencio.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if not _is_transient(exc) or attempt >= max_retries - 1:
                raise
            delay = None
            if isinstance(exc, BinanceAPIException) and exc.status_code in _RATE_LIMIT_STATUS_CODES:
                delay = _retry_after_seconds(exc)
            if delay is None:
                delay = min(backoff_base * (2 ** attempt), backoff_max)
            sleep_fn(delay)
            attempt += 1


def fetch_klines(client: Client, symbol: str, interval: str, start: str, end: str, *,
                 max_retries: int = MAX_RETRIES,
                 backoff_base: float = RETRY_BACKOFF_BASE_SECONDS,
                 backoff_max: float = RETRY_BACKOFF_MAX_SECONDS,
                 sleep_fn: Callable[[float], None] = time.sleep) -> list[list]:
    """Descarga klines crudas de Binance Futures para el rango [start, end).

    `client` se inyecta (no se construye acá) — mismo patrón que
    bot.py:fetch_ohlcv, para que el módulo sea testeable con un cliente falso.
    No parsea ni convierte el resultado: retorna las filas tal cual las
    entrega client.futures_historical_klines (12 columnas nativas, ver
    config.KLINE_COLUMNS), con reintento acotado ante error transitorio.
    """
    return _with_retry(
        lambda: client.futures_historical_klines(symbol, interval, start, end),
        max_retries=max_retries,
        backoff_base=backoff_base,
        backoff_max=backoff_max,
        sleep_fn=sleep_fn,
    )
