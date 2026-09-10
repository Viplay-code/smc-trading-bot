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
    contra datos reales).

    FIX DE INFRAESTRUCTURA DE TESTS (2026-09-10, Fase 2 de propagación de
    trigger.params): usa el literal "A" en vez de `trig_camp.BIAS_CANDIDATE`
    — bug PREEXISTENTE a esta fase, reproducido contra `e20d3e24` (el HEAD
    antes de tocar nada de Fase 2), no introducido por este cambio. Causa
    raíz: la migración de `scripts/trigger_campaign.py` (commit `721d172`)
    redefinió `BIAS_CANDIDATE` de la etiqueta legacy `"A"` al nombre
    canónico del contrato `"A_ema200_neutral"` — `bias_camp.apply_bias`
    exige la etiqueta legacy (`"A"`/`"A2"`/`"B"`), nunca el nombre de
    registro canónico, y este archivo (fuera del alcance de esa migración,
    nunca actualizado) quedó referenciando el valor nuevo, incompatible.
    Mismo patrón de corrección ya aplicado en
    `research/tests/test_gestion_campaign_session.py` (`BIAS_CANDIDATE_LEGACY
    = "A"`). Fix exclusivo de infraestructura de test — no cambia ningún
    comportamiento de producción, no toca `scripts/trigger_campaign.py` ni
    ningún componente de C1-C8 más allá de lo ya autorizado para esta fase."""
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, "A")
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


# --------------------------------------------------------------------------- #
# Propagación genérica de trigger.params (Automatización Experimental,       #
# 2026-09-10) — comportamiento de find_entries/_raw_events en sí, sobre      #
# datos sintéticos (la validación de C2 se prueba en                        #
# research/tests/test_runner_invariants.py).                                #
# --------------------------------------------------------------------------- #
def test_trigger_params_omitido_es_idéntico_a_vacio():
    """find_entries(...) sin trigger_params (default None->{}) debe
    producir EXACTAMENTE lo mismo que pasar trigger_params={} explícito —
    confirma que el default no cambia nada respecto del comportamiento
    anterior a esta extensión."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("trigger_params omitido == trigger_params={} (slice 2022 vacío)", False)

    sin_params = research.find_entries(frame, cfg, "D_range_breakout", "C_market_close")
    con_params_vacio = research.find_entries(
        frame, cfg, "D_range_breakout", "C_market_close", trigger_params={},
    )
    ok = (not errs) and sin_params == con_params_vacio
    return _p("find_entries(..., trigger_params omitido) == find_entries(..., trigger_params={}) "
              "para D_range_breakout", ok)


def test_trigger_params_vacio_es_idéntico_al_comportamiento_previo_a_la_extension():
    """Para los 3 Triggers no-T1, trigger_params={} debe producir
    EXACTAMENTE lo mismo que la llamada directa TRIGGER_LAYERS[name](frame)
    (el comportamiento de _raw_events ANTES de esta extensión) — no solo
    que no lanza excepción (eso ya lo cubre
    test_find_entries_otros_triggers_no_lanzan_excepcion), sino que el
    resultado es idéntico."""
    frame, cfg, errs = _build_2022_frame()
    ok = not errs
    for trigger_name in ("A_sweep_bos", "D_range_breakout", "C_bos_only"):
        directo = research.TRIGGER_LAYERS[trigger_name](frame)
        via_find_entries_raw = research.entries._raw_events(frame, trigger_name, cfg, {})
        if directo != via_find_entries_raw:
            ok = False
            print(f"    {trigger_name}: divergen con trigger_params={{}}")
    return _p("_raw_events(..., trigger_params={}) reproduce exacto TRIGGER_LAYERS[name](frame) "
              "para A_sweep_bos/D_range_breakout/C_bos_only", ok)


def test_trigger_params_range_lookback_cambia_los_eventos_donchian():
    """LA PRUEBA POSITIVA: range_lookback=5 vs range_lookback=20 deben
    producir conjuntos de eventos DISTINTOS para D_range_breakout sobre el
    mismo frame — confirma que trigger_params realmente llega al Trigger,
    no solo que no rompe nada."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("range_lookback distinto produce eventos distintos (slice 2022 vacío)", False)

    eventos_5 = research.find_entries(
        frame, cfg, "D_range_breakout", "C_market_close", trigger_params={"range_lookback": 5},
    )
    eventos_20 = research.find_entries(
        frame, cfg, "D_range_breakout", "C_market_close", trigger_params={"range_lookback": 20},
    )
    ok = (not errs) and eventos_5 != eventos_20 and len(eventos_5) != len(eventos_20)
    return _p(f"range_lookback=5 ({len(eventos_5)} eventos) vs range_lookback=20 "
              f"({len(eventos_20)} eventos) -> conjuntos de eventos distintos, trigger_params "
              f"llega realmente al Trigger", ok)


def test_t1_ignora_trigger_params_incluso_si_se_le_pasan():
    """Defensa en profundidad: aunque research.runner.validate_contract ya
    rechaza trigger.params no vacío para T1_ema_cross (ver
    test_runner_invariants.py), find_entries en sí también debe ignorar
    cualquier trigger_params para T1 — sigue derivando atr_period/atr_mult
    EXCLUSIVAMENTE de cfg, nunca de trigger_params, sin importar qué
    contenga."""
    frame, cfg, errs = _build_2022_frame()
    if frame.empty:
        return _p("T1 ignora trigger_params (slice 2022 vacío)", False)

    sin_params = research.find_entries(frame, cfg, "T1_ema_cross", "C_market_close")
    con_params_irrelevantes = research.find_entries(
        frame, cfg, "T1_ema_cross", "C_market_close",
        trigger_params={"atr_mult": 999.0, "ema_fast": 2},
    )
    ok = (not errs) and sin_params == con_params_irrelevantes
    return _p("find_entries(T1_ema_cross, ..., trigger_params={...}) == find_entries(T1_ema_cross, "
              "...) sin trigger_params — T1 los ignora por completo, ruta especial intacta", ok)


ALL_TESTS = [
    test_find_entries_matches_backtest_find_entries_exacto,
    test_find_entries_matches_legacy_find_entries_for_trigger_exacto,
    test_entries_no_esta_vacio_para_el_dataset_sintetico,
    test_find_entries_rechaza_trigger_desconocido,
    test_find_entries_otros_triggers_no_lanzan_excepcion,
    test_trigger_params_omitido_es_idéntico_a_vacio,
    test_trigger_params_vacio_es_idéntico_al_comportamiento_previo_a_la_extension,
    test_trigger_params_range_lookback_cambia_los_eventos_donchian,
    test_t1_ignora_trigger_params_incluso_si_se_le_pasan,
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
