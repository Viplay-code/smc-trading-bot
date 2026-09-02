"""research/data.py — Fase 3 (endurecimiento del runner, 2026-09-02):
elimina la dependencia `research -> scripts` identificada en Fase 2
(`research/runner.py` importaba `scripts.bias_campaign`/
`scripts.trigger_campaign`, contrario a la regla de dependencias
`market_data → dc_v1 → research → bot` de `TARGET_ARCHITECTURE.md` §2).

Dos categorías de función acá, tratadas con distinto nivel de riesgo:

  1. MOVIDAS (no duplicadas) desde `scripts/bias_campaign.py`, sin cambiar
     una línea de su lógica: `resample_4h`, `to_backtest_frame`. Son
     adaptadores mecánicos, sin ninguna advertencia de "no tocar" en su
     código de origen — `scripts/bias_campaign.py` ahora las re-exporta
     (mismo objeto de función, no una copia), mismo patrón de wrapper de
     compatibilidad ya usado en Fase 1 para `gate_check`.

  2. NUEVAS, deliberadamente NO movidas desde `scripts/bias_campaign.py`:
     `apply_bias_A`, `load_asset_year`. `scripts/bias_campaign.py::
     apply_bias` trae una advertencia explícita en su propio docstring —
     "Rama deliberadamente separada de la de 'A' (no unificada en un
     bucle sobre BIAS_LAYERS) para no tocar ni una línea de la rama de
     'A', ya congelada y con resultados reales publicados" — tocar esa
     función, aunque fuera para extraer un wrapper, viola esa advertencia
     ya vigente antes de esta fase. En su lugar, `apply_bias_A`/
     `load_asset_year` son implementaciones NUEVAS y AISLADAS acá, con
     equivalencia de comportamiento verificada por test
     (`research/tests/test_data_equivalence.py`) contra
     `scripts.trigger_campaign.load_asset_year` — no se asume la
     equivalencia, se demuestra.

`_load_raw_csv` se duplica localmente (privada, sin exportar) — misma
convención ya establecida y documentada en `scripts/bias_campaign.py`,
`scripts/trigger_campaign.py`, `scripts/build_dc_v1_datasets.py` y
`scripts/inspect_single_dataset.py`: parsing de formato de CSV crudo, no
lógica de pipeline sustantiva, se duplica por diseño en vez de crear un
acoplamiento nuevo para 10 líneas mecánicas.

No modifica `dc_v1` (solo lo invoca, `build_dc_v1`/`validate_dc_v1` sin
tocar) ni `simulate_v3`/`backtest.py` (no los importa siquiera).
"""
from __future__ import annotations

import pandas as pd

import research
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Formato del CSV crudo — duplicado a propósito, ver docstring del módulo.   #
# --------------------------------------------------------------------------- #
_TIME_COL = "open_time"
_OPEN_COL, _HIGH_COL, _LOW_COL, _CLOSE_COL, _VOLUME_COL = "open", "high", "low", "close", "volume"
_TIME_UNIT = "ms"


def _load_raw_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, header=0)
    ts = pd.to_datetime(df[_TIME_COL], unit=_TIME_UNIT, utc=True)
    raw = pd.DataFrame(
        {
            "open":   pd.to_numeric(df[_OPEN_COL],   errors="coerce").to_numpy(),
            "high":   pd.to_numeric(df[_HIGH_COL],   errors="coerce").to_numpy(),
            "low":    pd.to_numeric(df[_LOW_COL],    errors="coerce").to_numpy(),
            "close":  pd.to_numeric(df[_CLOSE_COL],  errors="coerce").to_numpy(),
            "volume": pd.to_numeric(df[_VOLUME_COL], errors="coerce").to_numpy(),
        },
        index=pd.DatetimeIndex(ts, name="open_time"),
    )
    return raw


# --------------------------------------------------------------------------- #
# MOVIDAS desde scripts/bias_campaign.py — comportamiento sin cambios,       #
# solo ubicación. scripts/bias_campaign.py re-exporta ambas (mismo objeto). #
# --------------------------------------------------------------------------- #
_OHLCV = ["open", "high", "low", "close", "volume"]
_RESAMPLE_RULES = {"open": "first", "high": "max", "low": "min",
                    "close": "last", "volume": "sum"}


def resample_4h(df1h: pd.DataFrame) -> pd.DataFrame:
    """1H OHLCV -> 4H OHLCV, misma regla que dc_v1::add_htf (label='left',
    closed='left'). MOVIDA desde scripts/bias_campaign.py (Fase 3) sin
    cambiar una línea de su cuerpo."""
    return (
        df1h[_OHLCV]
        .resample("4h", label="left", closed="left")
        .agg(_RESAMPLE_RULES)
        .dropna(subset=["close"])
    )


def to_backtest_frame(df: pd.DataFrame, bias_numeric: pd.Series, cfg) -> pd.DataFrame:
    """Adapta las columnas del contrato dc_v1 (open/high/low/close/volume/
    atr14/...) al formato que esperan backtest.py::find_entries/simulate_v3.
    MOVIDA desde scripts/bias_campaign.py (Fase 3) sin cambiar una línea de
    su cuerpo. No modifica backtest.py."""
    out = df[["open", "high", "low", "close"]].copy()
    out["atr"] = df["atr14"]
    h_idx = out.index.hour
    out["in_session"] = [any(s <= hh < e for s, e in cfg.sessions) for hh in h_idx]
    bias_map = {1: "long", -1: "short", 0: "neutral"}
    out["bias"] = bias_numeric.map(bias_map)
    return out


# --------------------------------------------------------------------------- #
# NUEVAS — NO tocan scripts/bias_campaign.py::apply_bias (advertencia de     #
# "no tocar" ya vigente, ver docstring del módulo). Equivalencia de          #
# comportamiento con scripts.trigger_campaign.load_asset_year DEMOSTRADA    #
# por test, no asumida.                                                      #
# --------------------------------------------------------------------------- #
def apply_bias_A(df1h: pd.DataFrame, df4h: pd.DataFrame) -> pd.Series:
    """Bias 'A' (research.BIAS_LAYERS["A_ema200_neutral"]) a granularidad
    1H: clasificación 4H desplazada (shift(1), evita mirar una vela 4H
    todavía en formación) y sostenida (ffill) sobre las filas 1H
    siguientes — misma lógica que la rama "A" de
    scripts.bias_campaign.apply_bias, reescrita acá para no importar
    scripts/ desde research/ (ver docstring del módulo)."""
    bias_fn = research.BIAS_LAYERS["A_ema200_neutral"]
    bias_4h = bias_fn(df4h)
    held = bias_4h.shift(1).rename("bias")
    merged = df1h[[]].join(held, how="left").ffill()
    return merged["bias"].fillna(0).astype("int8")


def load_asset_year(asset: str, year: int) -> pd.DataFrame:
    """Carga (activo, año) desde data/raw/, corre build_dc_v1()+
    validate_dc_v1() (dc_v1 sin modificar), calcula bias_A sobre el frame
    COMPLETO (disciplina P-3: continuo, luego slice) y recién entonces
    corta con periods.period_slice(). Devuelve el DataFrame 1H recortado
    con la columna bias_A (int8) agregada al contrato de dc_v1.

    Bias 'A' ÚNICAMENTE — a diferencia de
    scripts.bias_campaign.load_asset_year (que calcula bias_A Y bias_A2),
    esta función no calcula A2 porque ningún consumidor de research/ lo
    necesita todavía (el runner MVP de Fase 2 solo soporta Bias 'A').
    Ampliar a A2/B, si hace falta, es trabajo de una fase posterior."""
    path = raw_path(asset, INTERVAL_1H, year, RAW_DIR)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} no existe — corré scripts/download_market_data.py primero."
        )
    raw = _load_raw_csv(path)
    df_full = build_dc_v1(raw, asset=asset, dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    if errs:
        raise ValueError(f"validate_dc_v1 falló para {asset}/{year}: {errs}")

    df4h_full = resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = apply_bias_A(df_full, df4h_full)

    return period_slice(df_full, year)
