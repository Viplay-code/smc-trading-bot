"""
research/tests/test_entries_equivalence.py — Automatización experimental,
Componente 1 (generalización de Trigger/Entry, 2026-09-03): prueba de
equivalencia BEFORE/AFTER exacta.

`research.find_entries(frame, cfg, trigger_name, entry_name)` (research/
entries.py) reemplaza `backtest.find_entries(frame, cfg)` dentro de
`research/runner.py::run()`. Para la única combinación que el runner ya
soportaba antes de este componente (T1_ema_cross + C_market_close), ambas
funciones DEBEN producir exactamente la misma lista de entradas — mismas
entradas, mismo número, mismos índices/timestamps (entry_idx), mismo
trigger, mismo entry, sin redondeo ni tolerancia. También se compara contra
`scripts.trigger_campaign.find_entries_for_trigger` (el precedente ya
probado del que research/entries.py deriva su lógica de Trigger) para
confirmar que la generalización no diverge de ninguna de las dos
implementaciones ya validadas.

Mismos datos sintéticos que research/tests/test_trigger_campaign.py
(duplicados acá por la misma convención de test standalone ya usada en
todo research/tests/).

Ejecutar:
    python -m research.tests.test_entries_equivalence  (o con pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import research
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trig_camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """Idéntica (misma semilla/forma) a research/tests/test_trigger_campaign.py
    ::make_synthetic_raw_1h — necesario para que el frame construido acá sea
    comparable/reproducible, mismo dataset, activo y año que usa el runner
    en su propio test de equivalencia."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.006, n)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.uniform(10, 100, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _build_2022_frame():
    """Mismos pasos que test_trigger_campaign.py::_build_2022_frame — mismo
    dataset, activo y año que el contrato T1/C que usa el Runner (el mismo
    contrato exacto que research/tests/test_runner_equivalence.py ejecuta
    contra datos reales)."""
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, trig_camp.BIAS_CANDIDATE)
    sliced = period_slice(df_full, 2022)
    cfg = backtest.Config()
    frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
    return frame, cfg, errs


def test_find_entries_matches_backtest_find_entries_exacto():
    """research.find_entries(frame, cfg, "T1_ema_cross", "C_market_close")
    == backtest.find_entries(frame, cfg), campo por campo, sin tolerancia —
    la comparación mínima pedida: mismas entradas, mismo número, mismos
    entry_idx (timestamps derivan de ahí), mismo trigger, mismo entry."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("research.find_entries == backtest.find_entries (slice 2022 vacío)", False)

    expected = backtest.find_entries(frame, cfg)
    actual = research.find_entries(frame, cfg, "T1_ema_cross", "C_market_close")

    ok = (not errs) and expected == actual
    if not ok:
        print(f"    n_expected={len(expected)} n_actual={len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual)):
            if e != a:
                print(f"    primera diferencia en índice {i}: expected={e} actual={a}")
                break
    return _p("research.find_entries(T1_ema_cross, C_market_close) reproduce "
              "backtest.find_entries 1:1 (n_entries, entry_idx, direction, entry, sl0, risk_pts)", ok)


def test_find_entries_matches_legacy_find_entries_for_trigger_exacto():
    """Comparación adicional contra el precedente ya probado del que
    research/entries.py deriva su dispatch de Trigger — confirma que la
    generalización (que además parametriza Entry, a diferencia del
    precedente) no diverge de la implementación ya validada en
    scripts/trigger_campaign.py."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("research.find_entries == find_entries_for_trigger (slice 2022 vacío)", False)

    expected = trig_camp.find_entries_for_trigger(frame, cfg, "T1_ema_cross")
    actual = research.find_entries(frame, cfg, "T1_ema_cross", "C_market_close")

    ok = (not errs) and expected == actual
    return _p("research.find_entries(T1_ema_cross, C_market_close) reproduce "
              "scripts.trigger_campaign.find_entries_for_trigger 1:1", ok)


def test_entries_no_esta_vacio_para_el_dataset_sintetico():
    """Chequeo de cordura: si el dataset sintético no produjera ninguna
    entrada, las dos pruebas de igualdad de arriba pasarían trivialmente
    (listas vacías) sin probar nada — confirma que hay señal real que
    comparar."""
    frame, cfg, errs = _build_2022_frame()
    entries = research.find_entries(frame, cfg, "T1_ema_cross", "C_market_close")
    ok = (not errs) and len(entries) > 0
    return _p(f"El dataset sintético 2022 produce entradas T1/C no-triviales para comparar "
              f"(n_entries={len(entries)})", ok)


def test_find_entries_rechaza_trigger_desconocido():
    frame, cfg, _ = _build_2022_frame()
    try:
        research.find_entries(frame, cfg, "no_existe", "C_market_close")
        ok = False
    except ValueError:
        ok = True
    return _p("research.find_entries rechaza un trigger_name desconocido con ValueError", ok)


def test_find_entries_otros_triggers_no_lanzan_excepcion():
    """A_sweep_bos, D_range_breakout, C_bos_only (los 3 candidatos de
    Trigger que backtest.find_entries nunca soportó) deben poder ejecutarse
    de punta a punta vía research.find_entries sin excepción, emparejados
    con Entry compatibles (C_market_close, trigger-agnóstico) — no se
    verifica aquí ningún resultado científico, solo que el adaptador
    generalizado no rompe."""
    frame, cfg, errs = _build_2022_frame()
    ok = not errs
    for trigger_name in ("A_sweep_bos", "D_range_breakout", "C_bos_only"):
        try:
            entries = research.find_entries(frame, cfg, trigger_name, "C_market_close")
            ok = ok and isinstance(entries, list)
            ok = ok and all(
                {"entry_idx", "direction", "entry", "sl0", "risk_pts"}.issubset(e.keys())
                for e in entries
            )
        except Exception as e:
            ok = False
            print(f"    {trigger_name}: excepción inesperada {type(e).__name__}: {e}")
    return _p("research.find_entries corre sin excepción para A_sweep_bos/D_range_breakout/"
              "C_bos_only + C_market_close sobre el slice 2022 sintético", ok)


ALL_TESTS = [
    test_find_entries_matches_backtest_find_entries_exacto,
    test_find_entries_matches_legacy_find_entries_for_trigger_exacto,
    test_entries_no_esta_vacio_para_el_dataset_sintetico,
    test_find_entries_rechaza_trigger_desconocido,
    test_find_entries_otros_triggers_no_lanzan_excepcion,
]


def main():
    print("research/tests/test_entries_equivalence — equivalencia BEFORE/AFTER de la "
          "generalización de Trigger/Entry\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
