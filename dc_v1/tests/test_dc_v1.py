"""
DC-v1 — Tests por etapa. Ejecutar:  python -m dc_v1.tests.test_dc_v1
(o con pytest). Cada test valida una precisión concreta.
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

from dc_v1 import (
    prepare_raw, detect_gaps, add_1h_derivatives, add_htf, trim_warmup,
    add_session, add_htf_bias, build_dc_v1, validate_dc_v1,
    derive_htf_bias, ema, atr, SESSION_DTYPE, assert_equivalence_pandas_ta,
)
from dc_v1.pipeline import OHLCV, RESAMPLE_RULES
import talib


# --------------------------------------------------------------------------- #
# Generador de datos sintéticos: random walk OHLCV 1H continuo y válido.        #
# --------------------------------------------------------------------------- #
def make_synthetic_1h(n_days: int = 50, start: str = "2022-01-01",
                      seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_days * 24
    idx = pd.date_range(start=start, periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.004, n)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0, 0.002, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.uniform(10, 100, n)
    df = pd.DataFrame({"open": open_, "high": high, "low": low,
                       "close": close, "volume": vol}, index=idx)
    df.index.name = "timestamp"
    return df


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
def test_htf_bias_canonical():
    cp = pd.Series([101.0, 99.0, 100.0, 100.5], index=range(4), dtype=np.float64)
    ep = pd.Series([100.0, 100.0, 100.0, 100.0], index=range(4), dtype=np.float64)
    bias = derive_htf_bias(cp, ep)
    ok = (
        bias.tolist() == [1, -1, 0, 1]        # incluye el caso 0 = igualdad exacta
        and bias.dtype == np.int8
        and bias.name == "htf_bias"
    )
    return _p("htf_bias canónico: signos, dtype int8 y caso 0 exacto", ok)


def test_htf_bias_nan_guard():
    cp = pd.Series([101.0, np.nan], dtype=np.float64)
    ep = pd.Series([100.0, 100.0], dtype=np.float64)
    try:
        derive_htf_bias(cp, ep)
        return _p("htf_bias lanza ante NaN (no lo mapea a 0)", False)
    except ValueError:
        return _p("htf_bias lanza ante NaN (no lo mapea a 0)", True)


def test_ema_atr_wrappers():
    df = make_synthetic_1h(10)
    e = ema(df["close"], 50)
    a = atr(df["high"], df["low"], df["close"], 14)
    ref_e = talib.EMA(df["close"].to_numpy(np.float64), 50)
    ref_a = talib.ATR(df["high"].to_numpy(np.float64), df["low"].to_numpy(np.float64),
                      df["close"].to_numpy(np.float64), 14)
    ok = (
        np.allclose(e.to_numpy(), ref_e, equal_nan=True)
        and np.allclose(a.to_numpy(), ref_a, equal_nan=True)
        and e.index.equals(df.index) and a.index.equals(df.index)
    )
    return _p("ema/atr == TA-Lib directo y preservan índice", ok)


def test_htf_join_no_lookahead():
    """Verificación independiente: htf_close_prev(ts) debe ser el cierre de la
    barra 4H que empieza en floor_4h(ts) - 4h (la última 4H completada en ts)."""
    raw = prepare_raw(make_synthetic_1h(50))
    out = add_htf(add_1h_derivatives(raw))

    h4close = (
        raw[OHLCV].resample("4h", label="left", closed="left")
        .agg(RESAMPLE_RULES).dropna(subset=["close"])["close"]
    )
    four = pd.Timedelta("4h")
    checked = 0
    mismatches = 0
    for ts in out.index:
        got = out.loc[ts, "htf_close_prev"]
        if pd.isna(got):
            continue
        prev_start = ts.floor("4h") - four
        if prev_start not in h4close.index:
            continue
        checked += 1
        if got != h4close.loc[prev_start]:
            mismatches += 1
    ok = checked > 500 and mismatches == 0
    return _p(f"HTF join sin lookahead (verif. indep., {checked} barras, {mismatches} fallos)", ok)


def test_dedup_and_sort():
    df = make_synthetic_1h(3)
    scrambled = pd.concat([df.iloc[10:20], df.iloc[5:15]])  # desorden + solape/dups
    cleaned = prepare_raw(scrambled)
    ok = (
        cleaned.index.is_monotonic_increasing
        and cleaned.index.is_unique
        and cleaned.attrs.get("n_duplicates_removed", 0) > 0
    )
    return _p("dedup + orden (keep last) sobre índice desordenado con duplicados", ok)


def test_ohlc_sanity_raises():
    df = make_synthetic_1h(3)
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 1  # high < low
    try:
        prepare_raw(df)
        return _p("prepare_raw lanza ante vela imposible (high < low)", False)
    except AssertionError:
        return _p("prepare_raw lanza ante vela imposible (high < low)", True)


def test_session_dst_free_and_categories():
    winter = make_synthetic_1h(2, start="2022-01-10")
    summer = make_synthetic_1h(2, start="2022-07-10")
    sw = add_session(prepare_raw(winter))
    ss = add_session(prepare_raw(summer))
    # misma hora UTC -> misma sesión en enero y julio (sin DST)
    same = all(
        sw["session"].iloc[h] == ss["session"].iloc[h] for h in range(24)
    )
    cats_ok = list(sw["session"].dtype.categories) == list(SESSION_DTYPE.categories)
    # spot-check de una hora conocida: 14 UTC -> overlap
    hour14 = sw[sw.index.hour == 14]["session"].iloc[0]
    return _p("sesión DST-free + categorías fijas + 14UTC=overlap",
              same and cats_ok and hour14 == "overlap")


def test_trim_binding_column():
    raw = prepare_raw(make_synthetic_1h(50))
    df = add_htf(add_1h_derivatives(raw))
    trimmed = trim_warmup(df)
    cols = ["ema50", "atr14", "htf_close_prev", "htf_ema200_prev"]
    no_nan = not trimmed[cols].isna().any().any()
    # la primera fila válida está gobernada por htf_ema200_prev (la de mayor warmup)
    first_valid_ema200 = df["htf_ema200_prev"].first_valid_index()
    bound_ok = trimmed.index[0] >= first_valid_ema200
    return _p("trim por columna dominante (htf_ema200_prev), sin NaN posterior",
              no_nan and bound_ok)


def test_attrs_persist_end_to_end():
    out = build_dc_v1(make_synthetic_1h(50), asset="BTCUSDT",
                      dataset_version="binance_2022_raw", pipeline_version="pipe-0.1.0")
    ok = all(k in out.attrs for k in
             ("contract_version", "dataset_version", "pipeline_version", "asset"))
    ok = ok and out.attrs["asset"] == "BTCUSDT" and out.attrs["contract_version"] == "DC-v1"
    return _p("attrs sobreviven el merge (re-estampado tras add_htf)", ok)


def test_full_pipeline_passes_validator():
    out = build_dc_v1(make_synthetic_1h(60), asset="ETHUSDT",
                      dataset_version="binance_2022_raw", pipeline_version="pipe-0.1.0")
    errors = validate_dc_v1(out, strict=False)
    if errors:
        print("    errores:", errors)
    return _p("pipeline completo -> validador sin errores", len(errors) == 0)


def test_gaps_documented_not_filled():
    df = make_synthetic_1h(10)
    df = df.drop(df.index[100:105])  # abrir un gap de 5 barras
    raw = prepare_raw(df)
    gaps = detect_gaps(raw, "1h")
    # el gap se documenta y el índice NO se rellena (sigue faltando)
    ok = len(gaps) == 1 and gaps[0]["missing_bars"] == 5 and len(raw) == len(df)
    return _p("gaps documentados en attrs, NO rellenados", ok)


def test_pandas_ta_equivalence_optional():
    df = make_synthetic_1h(30)
    res = assert_equivalence_pandas_ta(df["close"], df["high"], df["low"])
    if res.get("status") == "skipped":
        print("  [SKIP] equivalencia pandas-ta (no instalado en este entorno)")
        return True
    return _p(f"equivalencia numérica pandas-ta ({res})", res.get("status") == "passed")


ALL_TESTS = [
    test_htf_bias_canonical,
    test_htf_bias_nan_guard,
    test_ema_atr_wrappers,
    test_htf_join_no_lookahead,
    test_dedup_and_sort,
    test_ohlc_sanity_raises,
    test_session_dst_free_and_categories,
    test_trim_binding_column,
    test_attrs_persist_end_to_end,
    test_full_pipeline_passes_validator,
    test_gaps_documented_not_filled,
    test_pandas_ta_equivalence_optional,
]


def main():
    print("DC-v1 — suite de verificación por etapa\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
