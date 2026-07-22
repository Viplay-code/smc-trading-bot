"""
research/tests/test_layers.py — Suite de paridad Tarea 5 (plan de unificación
del motor de señales). Ejecutar:  python -m research.tests.test_layers
(o con pytest). Sigue el patrón de dc_v1/tests/test_dc_v1.py.

Verifica que los 3 candidatos baseline ya portados (bias_A_ema200_neutral,
trigger_A_sweep_bos, entry_A_pullback_50) reproducen exactamente el
comportamiento del motor legacy (bot.py/backtest.py), y que el contrato de
la Tarea 1 (tipos de retorno, inmutabilidad, registros) se cumple. No
modifica bot.py/backtest.py ni los conecta con research — solo valida.

Import de bot.py: dispara `logging.basicConfig(FileHandler("smc_bot.log"))`
como efecto secundario del módulo. Se limpia una vez, a nivel de módulo,
justo después del import — ninguna de las funciones que se usan acá
(detect_liquidity_sweep, detect_bos, htf_bias) escribe al log por sí misma.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pandas as pd

import bot
import backtest
from research.layers import (
    BIAS_LAYERS,
    TRIGGER_LAYERS,
    ENTRY_LAYERS,
    TriggerEvent,
    EntrySignal,
    bias_A_ema200_neutral,
    bias_A2_ema200_neutral_1h_held,
    trigger_A_sweep_bos,
    entry_A_pullback_50,
    trigger_T1_ema_cross,
    entry_C_market_close,
)

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# Datos sintéticos (semilla fija, mismos parámetros ya usados y verificados   #
# manualmente en las Tareas 2-4).                                             #
# --------------------------------------------------------------------------- #
def make_synthetic_4h(n=260, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    ret = rng.normal(0, 0.01, n)
    close = 20000 * np.exp(np.cumsum(ret))
    return pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999, "close": close,
        "volume": rng.uniform(10, 100, n),
    }, index=idx)


def make_synthetic_1h(n=3000, seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.006, n)
    close = 20000 * np.exp(np.cumsum(ret))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.uniform(10, 100, n),
    }, index=idx)


# --------------------------------------------------------------------------- #
# Registro y contrato (ajustes pedidos: registros poblados + tipos)           #
# --------------------------------------------------------------------------- #
def test_registries_populated():
    ok = (
        BIAS_LAYERS.get("A_ema200_neutral") is bias_A_ema200_neutral
        and TRIGGER_LAYERS.get("A_sweep_bos") is trigger_A_sweep_bos
        and ENTRY_LAYERS.get("A_pullback_50") is entry_A_pullback_50
        and TRIGGER_LAYERS.get("T1_ema_cross") is trigger_T1_ema_cross
        and ENTRY_LAYERS.get("C_market_close") is entry_C_market_close
    )
    return _p("los candidatos baseline + T1 están registrados en BIAS/TRIGGER/ENTRY_LAYERS", ok)


def test_contract_return_types():
    df4h = make_synthetic_4h()
    df1h = make_synthetic_1h(n=500)

    bias = bias_A_ema200_neutral(df4h)
    events = trigger_A_sweep_bos(df1h)
    ok_bias = isinstance(bias, pd.Series)
    ok_trigger = isinstance(events, list) and all(isinstance(e, TriggerEvent) for e in events)

    ok_entry = True
    if events:
        signal = entry_A_pullback_50(df1h, events[0])
        ok_entry = isinstance(signal, EntrySignal) and isinstance(signal.price, float)

    ok = ok_bias and ok_trigger and ok_entry
    return _p("BiasFn->Series, TriggerFn->list[TriggerEvent], EntryFn->EntrySignal", ok)


def test_trigger_event_immutable():
    ev = TriggerEvent(entry_idx=0, direction="long", meta={})
    try:
        ev.entry_idx = 1
        ok = False
    except FrozenInstanceError:
        ok = True
    return _p("TriggerEvent es frozen (rechaza mutación)", ok)


def test_entry_signal_immutable():
    sig = EntrySignal(price=1.0)
    try:
        sig.price = 2.0
        ok = False
    except FrozenInstanceError:
        ok = True
    return _p("EntrySignal es frozen (rechaza mutación)", ok)


# --------------------------------------------------------------------------- #
# Capa 1 — bias_A_ema200_neutral vs bot.py real (paridad) y vs backtest.py    #
# (verificación de impacto de la Iniciativa B, NO paridad funcional).         #
#                                                                              #
# Contra bot.py::htf_bias: sigue siendo una comparación de PARIDAD exacta —   #
# desde la Iniciativa B, bias_A_ema200_neutral y bot.py::compute_ema usan     #
# ambas dc_v1.ema() (mismo candidato migrado, misma fuente), así que el       #
# último valor debe coincidir exactamente, igual que antes de la migración.  #
#                                                                              #
# Contra backtest.py::build_features: YA NO es una comparación de paridad     #
# funcional entre bot.py y backtest.py — nunca lo fue del todo desde la       #
# Tarea 7 (dos fórmulas de reclasificación distintas), y desde la Iniciativa  #
# B tampoco lo es a nivel de fuente (bias_A_ema200_neutral -> dc_v1.ema(),    #
# backtest.py's EMA200 de Bias -> pandas.ewm, sin migrar a propósito, ver     #
# Iniciativa G). Lo que este test verifica ahora es solo el IMPACTO medido    #
# de migrar la fuente del indicador: cuántas filas cambian de clasificación   #
# fuera de la ventana de warmup real de TA-Lib (199 velas para EMA200, que    #
# pandas.ewm nunca tuvo — con un fixture chico casi todo el fixture cae en    #
# ese warmup y la comparación no dice nada útil, por eso acá se usa un        #
# fixture más grande que en el resto de la suite). Medido empíricamente:      #
# ~2% de las filas post-warmup difieren (14/700 con n=900) — se documenta un  #
# techo generoso (10%) para detectar una regresión real, no para exigir       #
# equivalencia. La reconciliación funcional completa de Bias entre bot.py y   #
# backtest.py sigue siendo responsabilidad exclusiva de la Iniciativa G.      #
# --------------------------------------------------------------------------- #
def test_bias_matches_legacy():
    df4h = make_synthetic_4h(n=900)
    new_bias = bias_A_ema200_neutral(df4h)

    cfg_bt = backtest.Config()
    feats = backtest.build_features(df4h.copy(), df4h, cfg_bt)
    legacy_bias = feats["bias"].reindex(df4h.index).map(
        {"long": 1, "short": -1, "neutral": 0}
    ).astype("int8")

    ema_period = 200
    post_warmup = new_bias.index[ema_period:]
    disagree = int((new_bias.loc[post_warmup] != legacy_bias.loc[post_warmup]).sum())
    disagree_pct = 100 * disagree / len(post_warmup)
    impact_ok = disagree_pct <= 10.0
    print(f"    (info) impacto de fuente sobre bias post-warmup: "
          f"{disagree}/{len(post_warmup)} filas ({disagree_pct:.1f}%) — no se exige paridad")

    cfg_bot = bot.Config()
    last_str = bot.htf_bias(df4h, cfg_bot)
    last_map = {"long": 1, "short": -1, "neutral": 0}
    last_matches = last_map[last_str] == int(new_bias.iloc[-1])

    ok = impact_ok and last_matches
    return _p(
        "bias_A_ema200_neutral == bot.py (paridad exacta, misma fuente dc_v1) "
        "y vs backtest.py impacto de fuente <=10% post-warmup (NO paridad funcional)",
        ok,
    )


# --------------------------------------------------------------------------- #
# Paridad Capa 1 — candidato A2 (Iniciativa G, backlog post-Fase-B): a         #
# diferencia de test_bias_matches_legacy, acá sí se exige paridad EXACTA,     #
# porque bias_A2_ema200_neutral_1h_held es un port literal de la lógica       #
# actual de backtest.py::build_features (misma fuente pandas.ewm, misma       #
# mecánica shift+ffill) — no una variante con fuente distinta como A.         #
# --------------------------------------------------------------------------- #
def test_bias_a2_matches_backtest_exact():
    df1h = make_synthetic_1h()
    df4h = make_synthetic_4h()
    cfg = backtest.Config()

    feats = backtest.build_features(df1h, df4h, cfg)
    legacy_bias = feats["bias"].map({"long": 1, "short": -1, "neutral": 0}).astype("int8")

    new_bias = bias_A2_ema200_neutral_1h_held(df1h, df4h)

    ok = legacy_bias.equals(new_bias)
    return _p(
        "bias_A2_ema200_neutral_1h_held == backtest.py::build_features bias "
        "(paridad EXACTA, port literal, misma fuente pandas.ewm)",
        ok,
    )


# --------------------------------------------------------------------------- #
# Paridad Capa 2 — trigger_A_sweep_bos vs bot.py real, sin máquina de estados #
# --------------------------------------------------------------------------- #
def test_trigger_matches_legacy():
    df1h = make_synthetic_1h()
    cfg = bot.Config()

    legacy = []
    for i in range(cfg.swing_lookback, len(df1h)):
        sweep = bot.detect_liquidity_sweep(df1h.iloc[:i + 1], cfg)
        if sweep is None:
            continue
        bos = bot.detect_bos(df1h, i, sweep["type"], cfg)
        if bos is None:
            continue
        legacy.append((bos["bos_idx"], sweep["type"], sweep["sweep_level"], bos["bos_level"]))

    new_events = trigger_A_sweep_bos(df1h)
    new = [(e.entry_idx, e.direction, e.meta["sweep_level"], e.meta["bos_level"]) for e in new_events]

    ok = legacy == new and len(legacy) > 0  # exigir >0 para que la prueba no sea trivialmente vacía
    return _p(f"trigger_A_sweep_bos == detección real de bot.py, evento a evento ({len(legacy)} eventos)", ok)


# --------------------------------------------------------------------------- #
# Paridad Capa 3 — entry_A_pullback_50.                                       #
#                                                                              #
# RESUELTO (Tarea 6, commit 6b783e9): bot.py ya no tiene una fórmula de       #
# entrada inline propia — delega directamente en research.ENTRY_LAYERS       #
# ["A_pullback_50"]. entry_A_pullback_50 es ahora la ÚNICA implementación;    #
# ya no existe una segunda copia (ni en bot.py ni en este test) contra la    #
# cual comparar, así que la antigua _reference_entry_formula (transcripción  #
# manual de bot.py, mantenida a mano) se elimina — mantenerla habría sido    #
# duplicar la única fuente de verdad que ya quedó consolidada.               #
#                                                                              #
# Verificación sin duplicar la fórmula: al 50% exacto de pullback, el precio #
# de entrada es SIEMPRE el punto medio aritmético entre sweep_level y        #
# bos_level, sin importar la dirección (se puede derivar por álgebra de la   #
# fórmula con pullback_pct=0.5: bos - (bos-sweep)*0.5 == sweep + (bos-       #
# sweep)*0.5 == (sweep+bos)/2, y simétricamente para short). Es una          #
# propiedad matemática independiente, no una reimplementación de la rama     #
# long/short de entry_A_pullback_50.                                        #
# --------------------------------------------------------------------------- #
def test_entry_matches_shared_implementation():
    df1h = make_synthetic_1h()
    events = trigger_A_sweep_bos(df1h)
    assert events, "se necesitan eventos reales para esta prueba"

    price_ok = True
    direction_key_ok = True
    for ev in events:
        sweep_lvl = ev.meta["swing_low"] if ev.direction == "long" else ev.meta["swing_high"]
        expected_midpoint = (sweep_lvl + ev.meta["bos_level"]) / 2
        got = entry_A_pullback_50(df1h, ev).price
        if got != expected_midpoint:
            price_ok = False

        if ev.direction == "long" and "swing_low" not in ev.meta:
            direction_key_ok = False
        if ev.direction == "short" and "swing_high" not in ev.meta:
            direction_key_ok = False

    ok = price_ok and direction_key_ok
    return _p(f"entry_A_pullback_50 == punto medio sweep/bos + dirección->clave correcta ({len(events)} eventos)", ok)


# --------------------------------------------------------------------------- #
# Paridad T1 — trigger_T1_ema_cross + entry_C_market_close vs                 #
# backtest.py::find_entries real, reaplicando el mismo filtro de bias/sesión  #
# que find_entries hace inline (trigger_T1_ema_cross deliberadamente no lo    #
# aplica — ver nota de composición en research/layers.py). Sin reaplicar ese  #
# filtro, comparar directamente no tendría sentido: find_entries ya viene     #
# filtrado, trigger_T1_ema_cross no.                                         #
# --------------------------------------------------------------------------- #
def test_t1_matches_legacy():
    df1h = make_synthetic_1h()
    df4h = make_synthetic_4h()
    cfg = backtest.Config()

    feats = backtest.build_features(df1h, df4h, cfg)
    legacy = [
        (e["entry_idx"], e["direction"], e["entry"])
        for e in backtest.find_entries(feats, cfg)
    ]

    raw_events = trigger_T1_ema_cross(df1h)
    new = []
    for ev in raw_events:
        in_session = bool(feats["in_session"].iloc[ev.entry_idx])
        bias = feats["bias"].iloc[ev.entry_idx]
        if in_session and bias == ev.direction:
            price = entry_C_market_close(df1h, ev).price
            new.append((ev.entry_idx, ev.direction, price))

    ok = legacy == new and len(legacy) > 0
    return _p(
        f"trigger_T1_ema_cross + entry_C_market_close (tras filtrar bias/sesión) "
        f"== find_entries real, evento a evento ({len(legacy)} eventos)",
        ok,
    )


ALL_TESTS = [
    test_registries_populated,
    test_contract_return_types,
    test_trigger_event_immutable,
    test_entry_signal_immutable,
    test_bias_matches_legacy,
    test_bias_a2_matches_backtest_exact,
    test_trigger_matches_legacy,
    test_entry_matches_shared_implementation,
    test_t1_matches_legacy,
]


def main():
    print("research/layers — suite de paridad (Tarea 5)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
