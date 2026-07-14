"""
DC-v1 — Indicadores canónicos y derivación oficial de htf_bias.

Gobernanza P-7 (congelado):
- TA-Lib es la librería canónica.
- EMA recursiva con semilla SMA (equivalente adjust=False / TradingView) -> talib.EMA.
- ATR14 con suavizado de Wilder (RMA) -> talib.ATR.
- Cualquier alternativa (pandas-ta) solo es admisible si demuestra equivalencia
  numérica con esta implementación (ver assert_equivalence_pandas_ta).

Este módulo es la ÚNICA fuente de verdad para EMA, ATR y htf_bias.
Pipeline y validador importan de aquí; no se transcribe ninguna fórmula dos veces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import talib

CONTRACT_VERSION = "DC-v1"


# --------------------------------------------------------------------------- #
# Indicadores canónicos (TA-Lib). Preservan el índice de la Serie de entrada.  #
# TA-Lib exige float64 y devuelve NaN en el periodo de lookback inicial.       #
# --------------------------------------------------------------------------- #
def ema(close: pd.Series, timeperiod: int) -> pd.Series:
    """EMA canónica (TA-Lib): recursiva, semilla SMA de las primeras `timeperiod`
    observaciones, k = 2/(timeperiod+1). Equivalente a adjust=False / TradingView."""
    values = talib.EMA(close.to_numpy(dtype=np.float64), timeperiod=timeperiod)
    return pd.Series(values, index=close.index, name=f"ema{timeperiod}")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, timeperiod: int = 14) -> pd.Series:
    """ATR canónica (TA-Lib): True Range suavizado por Wilder (RMA)."""
    values = talib.ATR(
        high.to_numpy(dtype=np.float64),
        low.to_numpy(dtype=np.float64),
        close.to_numpy(dtype=np.float64),
        timeperiod=timeperiod,
    )
    return pd.Series(values, index=close.index, name=f"atr{timeperiod}")


# --------------------------------------------------------------------------- #
# htf_bias — derivación OFICIAL (P-6). Única fuente de verdad.                  #
# Dominio {+1, -1, 0} (int8). 0 = igualdad exacta de floats: reservado por     #
# estabilidad semántica, prácticamente inalcanzable.                           #
# --------------------------------------------------------------------------- #
def derive_htf_bias(htf_close_prev: pd.Series, htf_ema200_prev: pd.Series) -> pd.Series:
    """Deriva htf_bias = sign(htf_close_prev - htf_ema200_prev) como int8.

    Se usa np.sign (no np.where): np.where(c>e,1,np.where(c<e,-1,0)) mapea NaN->0
    en silencio (las comparaciones con NaN son False) y corrompería el bias.
    np.sign propaga NaN; el guard de abajo lo caza en voz alta.

    Requiere inputs sin NaN -> llamar SOLO sobre el frame ya recortado por warmup.
    Orden de resta fijado (close_prev - ema200_prev); invertirlo voltea los signos.
    """
    if htf_close_prev.isna().any() or htf_ema200_prev.isna().any():
        raise ValueError(
            "derive_htf_bias: NaN en columnas _prev. "
            "Debe derivarse DESPUÉS del trim de warmup (P-5/P-6)."
        )
    if not htf_close_prev.index.equals(htf_ema200_prev.index):
        raise ValueError("derive_htf_bias: los índices de las columnas _prev no coinciden.")

    diff = htf_close_prev.to_numpy(dtype=np.float64) - htf_ema200_prev.to_numpy(dtype=np.float64)
    bias = np.sign(diff).astype(np.int8)  # {-1., 0., 1.} -> {-1, 0, 1}
    return pd.Series(bias, index=htf_close_prev.index, name="htf_bias")


# --------------------------------------------------------------------------- #
# Verificación de equivalencia numérica para implementaciones alternativas      #
# (P-7). Solo se ejecuta si pandas-ta está instalado.                          #
# --------------------------------------------------------------------------- #
def assert_equivalence_pandas_ta(close: pd.Series, high: pd.Series, low: pd.Series,
                                 atol: float = 1e-8) -> dict:
    """Compara EMA/ATR canónicas (TA-Lib) contra pandas-ta. Lanza si difieren.

    Devuelve un dict con las diferencias máximas. Skippea (retorna status) si
    pandas-ta no está instalado. La equivalencia se evalúa solo donde ambas
    implementaciones tienen valores válidos (no-NaN).
    """
    try:
        import pandas_ta as ta  # noqa: F401
    except ImportError:
        return {"status": "skipped", "reason": "pandas-ta no instalado"}

    import pandas_ta as ta
    ta.Imports["talib"] = False  # forzar la implementación propia de pandas-ta

    results = {}
    for period in (50, 200):
        canon = ema(close, period)
        alt = ta.ema(close, length=period, talib=False)
        mask = canon.notna() & alt.notna()
        max_diff = float((canon[mask] - alt[mask]).abs().max())
        results[f"ema{period}_max_diff"] = max_diff
        assert max_diff <= atol, f"EMA{period}: divergencia {max_diff} > {atol}"

    canon_atr = atr(high, low, close, 14)
    alt_atr = ta.atr(high=high, low=low, close=close, length=14, talib=False)
    mask = canon_atr.notna() & alt_atr.notna()
    max_diff = float((canon_atr[mask] - alt_atr[mask]).abs().max())
    results["atr14_max_diff"] = max_diff
    assert max_diff <= atol, f"ATR14: divergencia {max_diff} > {atol}"

    results["status"] = "passed"
    return results
