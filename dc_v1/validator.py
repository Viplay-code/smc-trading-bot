"""
DC-v1 — Validador del contrato (punto de consumo).

Recoge TODAS las violaciones y las reporta juntas (más útil para research que
fallar en la primera). validate_dc_v1(df, strict=True) lanza AssertionError si
hay alguna; con strict=False devuelve el reporte sin lanzar.

Chequeos (consolidado de las precisiones):
  1. attrs: contract_version=='DC-v1' + dataset_version + pipeline_version + asset
  2. índice: DatetimeIndex, tz UTC, monótono creciente, único
  3. columnas obligatorias presentes con dtypes EXACTOS
  4. sin NaN en obligatorias
  5. sanity OHLC
  6. htf_bias == derive_htf_bias(htf_close_prev, htf_ema200_prev)  (misma función)
  7. session: categorías == set fijo
  8. htf_bias ∈ {-1, 0, 1}
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import CONTRACT_VERSION, derive_htf_bias
from .pipeline import SESSION_DTYPE, REQUIRED_ATTRS

FLOAT_COLS = ["open", "high", "low", "close", "volume",
              "ema50", "atr14", "htf_close_prev", "htf_ema200_prev"]
OBLIGATORY = FLOAT_COLS + ["session", "htf_bias"]


def validate_dc_v1(df: pd.DataFrame, strict: bool = True) -> list[str]:
    """Devuelve la lista de violaciones. strict=True -> lanza si hay alguna."""
    errors: list[str] = []

    # 1. attrs
    for key in REQUIRED_ATTRS:
        if key not in df.attrs:
            errors.append(f"attrs: falta '{key}'")
    if df.attrs.get("contract_version") not in (None, CONTRACT_VERSION):
        errors.append(f"attrs: contract_version='{df.attrs.get('contract_version')}' != {CONTRACT_VERSION}")

    # 2. índice
    if not isinstance(df.index, pd.DatetimeIndex):
        errors.append("índice: no es DatetimeIndex")
    else:
        if df.index.tz is None or str(df.index.tz) != "UTC":
            errors.append(f"índice: tz debe ser UTC (es {df.index.tz})")
        if not df.index.is_monotonic_increasing:
            errors.append("índice: no monótono creciente")
        if not df.index.is_unique:
            errors.append("índice: contiene duplicados")

    # 3. columnas + dtypes
    for col in OBLIGATORY:
        if col not in df.columns:
            errors.append(f"columna obligatoria ausente: {col}")
    if not errors or all("ausente" not in e for e in errors):
        for col in FLOAT_COLS:
            if col in df.columns and df[col].dtype != np.float64:
                errors.append(f"dtype: {col} debe ser float64 (es {df[col].dtype})")
        if "htf_bias" in df.columns and df["htf_bias"].dtype != np.int8:
            errors.append(f"dtype: htf_bias debe ser int8 (es {df['htf_bias'].dtype})")
        if "session" in df.columns:
            if not isinstance(df["session"].dtype, pd.CategoricalDtype):
                errors.append("dtype: session debe ser CategoricalDtype")
            elif list(df["session"].dtype.categories) != list(SESSION_DTYPE.categories):
                errors.append(
                    f"session: categorías {list(df['session'].dtype.categories)} "
                    f"!= {list(SESSION_DTYPE.categories)}"
                )

    # 4. sin NaN en obligatorias
    for col in OBLIGATORY:
        if col in df.columns:
            n_nan = int(df[col].isna().sum())
            if n_nan:
                errors.append(f"NaN en obligatoria '{col}': {n_nan} filas")

    # 5. sanity OHLC
    if all(c in df.columns for c in ["open", "high", "low", "close"]):
        o, h, l, c = df["open"], df["high"], df["low"], df["close"]
        bad = int(((h < l) | (h < o) | (h < c) | (l > o) | (l > c)).sum())
        if bad:
            errors.append(f"sanity OHLC: {bad} velas imposibles")

    # 6. htf_bias re-derivado (misma función -> igualdad exacta, incluido el 0)
    if all(c in df.columns for c in ["htf_bias", "htf_close_prev", "htf_ema200_prev"]):
        if not df[["htf_close_prev", "htf_ema200_prev"]].isna().any().any():
            expected = derive_htf_bias(df["htf_close_prev"], df["htf_ema200_prev"])
            mismatch = int((df["htf_bias"] != expected).sum())
            if mismatch:
                errors.append(f"htf_bias: {mismatch} filas inconsistentes con columnas _prev")

    # 8. dominio htf_bias
    if "htf_bias" in df.columns:
        outside = int((~df["htf_bias"].isin([-1, 0, 1])).sum())
        if outside:
            errors.append(f"htf_bias: {outside} valores fuera de {{-1,0,1}}")

    if strict and errors:
        raise AssertionError(
            "DC-v1 validación FALLÓ:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    return errors
