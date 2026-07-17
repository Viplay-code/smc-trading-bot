#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""periods.py — Punto ÚNICO de verdad del recorte al periodo de investigación.

Deriva el intervalo de investigación [Y-01-01, (Y+1)-01-01) a partir de un
DataFrame con buffer (la salida de dc_v1.build_dc_v1). Todo consumidor
—inspect_single_dataset, gate-runner, EXP-07 y futuros procesos— debe usar este
helper; nadie reimplementa el corte. Esto resuelve I-1: sin este recorte, el
buffer de 2 meses solapa dic del año anterior entre periodos (in-sample y
validación compartirían diciembre).

YAGNI: módulo plano mientras haya pocos consumidores. Si aparecen varias
utilidades de research (walk-forward, particiones, ventanas), evolucionar
entonces —y no antes— hacia un paquete research/.
"""
from __future__ import annotations
import pandas as pd


def period_bounds(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Límites UTC del periodo: intervalo semiabierto [inicio, fin) sobre open-time."""
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
    return start, end


def period_slice(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Recorta df al periodo `year`: [Y-01-01 00:00, (Y+1)-01-01 00:00) UTC.

    Requisito (garantizado por la salida de dc_v1): índice DatetimeIndex
    tz-aware UTC. Falla fuerte si no se cumple — no localiza en silencio,
    coherente con la política de "no corregir calladamente" y con lo que el
    propio validate_dc_v1 exige.

    Semiabierto sobre open-time: una barra abierta a 2022-12-31 23:00 pertenece
    a 2022; una abierta a 2023-01-01 00:00 pertenece a 2023 → sin solape.

    Puro: solo recorta. No valida completitud ni examina contenido (eso queda
    en el inspector/gate-runner). Agnóstico al timeframe.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            "period_slice requiere DatetimeIndex (la salida de dc_v1 lo es)."
        )
    if df.index.tz is None or str(df.index.tz) != "UTC":
        raise ValueError(
            f"period_slice requiere índice tz-aware UTC; es {df.index.tz}. "
            f"dc_v1 garantiza UTC — revisa el origen del df."
        )
    start, end = period_bounds(year)
    return df.loc[(df.index >= start) & (df.index < end)]