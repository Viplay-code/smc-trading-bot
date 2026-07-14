"""
DC-v1 — Pipeline de construcción del Research Engine Input.

Etapas (cada una verificable por separado):
  1. prepare_raw       carga/validación de entrada + dedup + sanity OHLC
  2. add_1h_derivatives ema50, atr14 (sobre serie CONTINUA — P-3)
  3. add_htf           resample 4H (label/closed left) + EMA200 + shift(1) + merge_asof
  4. trim_warmup       recorte por columna de mayor warmup (htf_ema200_prev — P-5)
  5. add_session       sesión UTC fija, DST-free, CategoricalDtype explícito (P-8)
  6. add_htf_bias      derive_htf_bias sobre frame recortado (P-6)
  7. stamp_attrs       (asset + 3 versiones), re-estampado tras cada merge (P-4)

build_dc_v1() orquesta todo. El validador vive en validator.py.

Convención temporal (P-1): timestamp = APERTURA de la barra (Binance open-time).
En la fila t solo es lícita información completada hasta el inicio de t.

Gaps (DC-v1): se DOCUMENTAN en attrs['gaps'], NO se rellenan. El índice conserva
las barras observadas; nada de asfreq/reindex a grilla completa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import CONTRACT_VERSION, ema, atr, derive_htf_bias

OHLCV = ["open", "high", "low", "close", "volume"]
RESAMPLE_RULES = {"open": "first", "high": "max", "low": "min",
                  "close": "last", "volume": "sum"}

# --- Sesión: horas UTC FIJAS y declaradas (P-8). DST-free por construcción. ---
# NOTA: DC-v1 fija el SET de categorías y el principio "UTC fijo, sin DST", pero
# no pinó las horas exactas. Estas son las ventanas usadas; es el único parámetro
# libre que quedó. Editar aquí si el desk de research usa otra convención.
#   london  : 07:00–13:00 UTC   (Londres, antes del solape)
#   overlap : 13:00–16:00 UTC   (Londres + Nueva York abiertos)
#   ny      : 16:00–22:00 UTC   (Nueva York, tras cierre de Londres)
#   off     : resto (22:00–07:00 UTC)
SESSION_DTYPE = pd.CategoricalDtype(["london", "ny", "overlap", "off"])

REQUIRED_ATTRS = ("contract_version", "dataset_version", "pipeline_version", "asset")


# --------------------------------------------------------------------------- #
# Etapa 1 — Carga / validación de entrada + dedup                              #
# --------------------------------------------------------------------------- #
def prepare_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza y valida el crudo 1H. Dedup ANTES de todo (klines de Binance
    duplicadas en fronteras de paginación). No rellena gaps."""
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    missing = set(OHLCV) - set(df.columns)
    if missing:
        raise ValueError(f"prepare_raw: faltan columnas crudas {missing}")
    df = df[OHLCV]

    # Índice tz-aware UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df.index.name = "timestamp"

    # dtypes float64
    for col in OHLCV:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float64)

    # Ordenar + deduplicar (keep last)
    df = df.sort_index()
    dupes = df.index.duplicated(keep="last")
    n_dupes = int(dupes.sum())
    if dupes.any():
        df = df[~dupes]

    _assert_input_integrity(df)
    df.attrs["n_duplicates_removed"] = n_dupes
    return df


def _assert_input_integrity(df: pd.DataFrame) -> None:
    """Validaciones de entrada que el contrato asume (higiene)."""
    assert isinstance(df.index, pd.DatetimeIndex), "índice no es DatetimeIndex"
    assert df.index.tz is not None, "índice debe ser tz-aware UTC"
    assert df.index.is_monotonic_increasing, "índice no es monótono creciente"
    assert df.index.is_unique, "índice contiene duplicados tras dedup"
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bad = (h < l) | (h < o) | (h < c) | (l > o) | (l > c)
    bad |= (df[["open", "high", "low", "close"]] < 0).any(axis=1)
    bad |= (df["volume"] < 0)
    n_bad = int(bad.sum())
    assert n_bad == 0, f"velas imposibles / valores negativos: {n_bad} filas"


def detect_gaps(df: pd.DataFrame, freq: str = "1h") -> list[dict]:
    """Documenta gaps (no rellena). Devuelve lista de {start, end, missing_bars}.
    Un gap es un salto mayor a `freq` entre barras consecutivas observadas."""
    step = pd.Timedelta(freq)
    deltas = df.index.to_series().diff()
    gaps = []
    for ts, d in deltas.items():
        if pd.notna(d) and d > step:
            missing = int(d / step) - 1
            gaps.append({
                "start": (ts - d).isoformat(),
                "end": ts.isoformat(),
                "missing_bars": missing,
            })
    return gaps


# --------------------------------------------------------------------------- #
# Etapa 2 — Derivadas 1H sobre serie CONTINUA (P-3)                             #
# --------------------------------------------------------------------------- #
def add_1h_derivatives(df: pd.DataFrame) -> pd.DataFrame:
    """ema50 y atr14 sobre la serie continua (aún con NaN de warmup)."""
    df = df.copy()
    df["ema50"] = ema(df["close"], 50).astype(np.float64)
    df["atr14"] = atr(df["high"], df["low"], df["close"], 14).astype(np.float64)
    return df


# --------------------------------------------------------------------------- #
# Etapa 3 — HTF 4H -> 1H, sin lookahead ni doble lag (P-2)                      #
# --------------------------------------------------------------------------- #
def add_htf(df: pd.DataFrame) -> pd.DataFrame:
    """Resample 4H (label='left', closed='left') sobre la serie continua,
    EMA200 sobre cierres 4H, shift(1) para portar la 4H ANTERIOR completada,
    y merge_asof(direction='backward') keyeado por el inicio de barra.

    En τ ∈ [t_k, t_k+4h) se usa la 4H que cerró en t_k (nunca la que se forma).
    """
    h4 = (
        df[OHLCV]
        .resample("4h", label="left", closed="left")
        .agg(RESAMPLE_RULES)
        .dropna(subset=["close"])
    )
    htf = pd.DataFrame(index=h4.index)
    htf["htf_close_prev"] = h4["close"].astype(np.float64)
    htf["htf_ema200_prev"] = ema(h4["close"], 200).astype(np.float64)

    # shift(1) ANTES del join: cada slot 4H pasa a portar la 4H anterior completada.
    htf = htf.shift(1)

    out = pd.merge_asof(
        df.sort_index(),
        htf.sort_index(),
        left_index=True,
        right_index=True,
        direction="backward",
    )
    # merge_asof descarta attrs -> se re-estampan en build_dc_v1 (P-4).
    return out


# --------------------------------------------------------------------------- #
# Etapa 4 — Trim de warmup por columna dominante (P-5)                          #
# --------------------------------------------------------------------------- #
OBLIGATORY_FOR_TRIM = ["open", "high", "low", "close", "volume",
                       "ema50", "atr14", "htf_close_prev", "htf_ema200_prev"]


def trim_warmup(df: pd.DataFrame) -> pd.DataFrame:
    """Recorta hasta la primera fila donde TODAS las obligatorias (excepto las
    que se derivan después, como htf_bias) son válidas. La columna dominante es
    htf_ema200_prev (200×4H ≈ 800×1H)."""
    valid = df[OBLIGATORY_FOR_TRIM].notna().all(axis=1)
    if not valid.any():
        raise ValueError("trim_warmup: ninguna fila tiene todas las obligatorias válidas")
    first_valid = valid.idxmax()  # primer True
    return df.loc[first_valid:].copy()


# --------------------------------------------------------------------------- #
# Etapa 5 — Sesión (P-8)                                                        #
# --------------------------------------------------------------------------- #
def _classify_session(hours: np.ndarray) -> np.ndarray:
    s = np.full(hours.shape, "off", dtype=object)
    s[(hours >= 7) & (hours < 13)] = "london"
    s[(hours >= 13) & (hours < 16)] = "overlap"
    s[(hours >= 16) & (hours < 22)] = "ny"
    return s


def add_session(df: pd.DataFrame) -> pd.DataFrame:
    """Sesión por hora UTC fija (DST-free). CategoricalDtype explícito para que
    los 9 datasets compartan categorías idénticas."""
    df = df.copy()
    hours = df.index.hour.to_numpy()
    df["session"] = pd.Categorical(_classify_session(hours), dtype=SESSION_DTYPE)
    return df


# --------------------------------------------------------------------------- #
# Etapa 6 — htf_bias (P-6)                                                      #
# --------------------------------------------------------------------------- #
def add_htf_bias(df: pd.DataFrame) -> pd.DataFrame:
    """Deriva htf_bias con la función compartida, sobre el frame ya recortado."""
    df = df.copy()
    df["htf_bias"] = derive_htf_bias(df["htf_close_prev"], df["htf_ema200_prev"])
    return df


# --------------------------------------------------------------------------- #
# Etapa 7 — attrs (P-4)                                                         #
# --------------------------------------------------------------------------- #
def stamp_attrs(df: pd.DataFrame, asset: str, dataset_version: str,
                pipeline_version: str, gaps: list | None = None) -> pd.DataFrame:
    """(Re)estampa los attrs obligatorios. Llamar tras cada etapa que pueda
    descartarlos (en especial el merge de add_htf)."""
    df.attrs["contract_version"] = CONTRACT_VERSION
    df.attrs["dataset_version"] = dataset_version
    df.attrs["pipeline_version"] = pipeline_version
    df.attrs["asset"] = asset
    if gaps is not None:
        df.attrs["gaps"] = gaps
    return df


# --------------------------------------------------------------------------- #
# Orquestador                                                                  #
# --------------------------------------------------------------------------- #
def build_dc_v1(raw_df: pd.DataFrame, asset: str, dataset_version: str,
                pipeline_version: str) -> pd.DataFrame:
    """Construye un DataFrame conforme a DC-v1 a partir del crudo 1H de un activo.

    raw_df: OHLCV 1H con DatetimeIndex (open-time). Un DataFrame por activo.
    """
    raw = prepare_raw(raw_df)
    gaps = detect_gaps(raw, "1h")

    df = add_1h_derivatives(raw)          # 2
    df = add_htf(df)                      # 3 (pierde attrs)
    df = trim_warmup(df)                  # 4
    df = add_session(df)                  # 5
    df = add_htf_bias(df)                 # 6

    # Orden final de columnas del contrato
    contract_cols = ["open", "high", "low", "close", "volume",
                     "ema50", "atr14", "session",
                     "htf_close_prev", "htf_ema200_prev", "htf_bias"]
    df = df[contract_cols]

    df = stamp_attrs(df, asset, dataset_version, pipeline_version, gaps)  # 7
    return df
