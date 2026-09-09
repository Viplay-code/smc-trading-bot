"""
research/tests/test_trigger_campaign.py — Validación ESTRUCTURAL (con datos
sintéticos, para la paridad de las funciones legacy preservadas) Y de
EQUIVALENCIA (con datos reales, para el universo canónico) de
scripts/trigger_campaign.py, MIGRADO a C1-C8 (2026-09-09).

`load_asset_year`/`_raw_events`/`find_entries_for_trigger` se PRESERVAN en
el script (dependencia cruzada real de `scripts/gestion_campaign_session.py`,
ver docstring de `scripts/trigger_campaign.py`) — sus tests de paridad
contra `backtest.find_entries` se mantienen sin cambios de fondo. La
orquestación de la campaña (`run_campaign`/`run_blind_test`/
`build_universe`) migró a `research.expand_universe`(C4)/
`research.runner.run_many`(C3) — sus tests se adaptan a la nueva API y se
agregan pruebas de universo (24 contratos), guard Trigger/Raw, y
equivalencia 24/24 sobre datos reales contra
`trigger_campaign_results.csv`/`_decision.csv` (nunca modificados).

Ejecutar:
    python -m research.tests.test_trigger_campaign  (o con pytest)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import research
from research import runner
from research.comparison import compare_results
from research.decision import summarize_decision
from research.persistence import read_experiment_results_csv, write_experiment_results_csv
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """~333 días 1H (>> 90 días de buffer + un año completo). Misma forma
    que research/tests/test_bias_campaign.py::make_synthetic_raw_1h,
    duplicada acá por la misma convención (cada archivo de test es
    standalone) ya usada entre test_layers.py y test_bias_campaign.py."""
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
    """Construye el frame adaptado (Bias=A ya resuelto) sobre el slice 2022
    sintético — mismos pasos que trigger_campaign.py::load_asset_year salvo
    la carga de CSV, igual que test_bias_campaign.py lo hace para bias_campaign.py."""
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
    return frame, cfg, errs, sliced


# --------------------------------------------------------------------------- #
# Funciones legacy PRESERVADAS (dependencia cruzada real, ver docstring del  #
# script) — paridad sin cambios de fondo.                                    #
# --------------------------------------------------------------------------- #
def test_find_entries_for_trigger_t1_matches_backtest_find_entries():
    """Paridad: find_entries_for_trigger(frame, cfg, "T1_ema_cross") debe
    producir EXACTAMENTE las mismas entradas que backtest.find_entries sobre
    el mismo frame — son la misma combinación Trigger+Entry, solo con el
    Trigger resuelto por nombre en vez de estar hardcodeado. Si esto
    diverge, el adaptador preservado (usado por gestion_campaign_session.py)
    no es fiel al que ya está validado en producción."""
    frame, cfg, errs, _ = _build_2022_frame()
    if frame.empty:
        return _p("find_entries_for_trigger('T1_ema_cross') == backtest.find_entries (slice 2022 vacío)", False)

    expected = backtest.find_entries(frame, cfg)
    actual = camp.find_entries_for_trigger(frame, cfg, "T1_ema_cross")

    ok = (not errs) and expected == actual
    return _p("find_entries_for_trigger('T1_ema_cross') reproduce backtest.find_entries 1:1", ok)


def test_find_entries_for_trigger_runs_both_candidates_end_to_end():
    """Pipeline legacy preservado (adaptador + run_config + metrics +
    gate_check) para AMBOS candidatos de Trigger, sin excepciones — sigue
    siendo lo que scripts/gestion_campaign_session.py consume para sus
    sanity-checks, aunque la ORQUESTACIÓN de esta campaña ya no lo use."""
    frame, cfg, errs, sliced = _build_2022_frame()
    if sliced.empty:
        return _p("pipeline legacy preservado (Trigger T1/A_sweep_bos + run_config + metrics + gate_check)", False)

    ok = not errs
    for trigger_name in camp.TRIGGERS:
        entries = camp.find_entries_for_trigger(frame, cfg, trigger_name)
        ok = ok and isinstance(entries, list)
        ok = ok and all(
            {"entry_idx", "direction", "entry", "sl0", "risk_pts"}.issubset(e.keys())
            for e in entries
        )
        for exit_cfg in backtest.EXIT_CONFIGS.values():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            gate = research.gate_check(m)
            ok = ok and isinstance(gate, bool)

    return _p("pipeline legacy preservado corre sin excepciones para T1_ema_cross y A_sweep_bos "
              "sobre slice 2022", ok)


def test_raw_events_rejects_unknown_trigger_name():
    frame, cfg, _, _ = _build_2022_frame()
    try:
        camp._raw_events(frame, "no_existe", cfg)
        ok = False
    except ValueError:
        ok = True
    return _p("_raw_events rechaza un nombre de Trigger desconocido con ValueError", ok)


# --------------------------------------------------------------------------- #
# Universo canónico (C4) — estructural, sin datos reales                    #
# --------------------------------------------------------------------------- #
def test_build_universe_produce_24_contratos_triggers_y_managements_exactos():
    contracts = camp.build_universe(("BTCUSDT", "ETHUSDT", "SOLUSDT"), {"train": 2022, "validate": 2023})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    triggers = {c["trigger"]["name"] for c in contracts}
    mgmts = {c["management"]["name"] for c in contracts}
    sessions = {c["session"] for c in contracts}
    hashes = {research.compute_contract_hash(c) for c in contracts}
    ok = (
        len(contracts) == 24
        and triggers == {"T1_ema_cross", "A_sweep_bos"}
        and mgmts == {"V3-A", "V3-B"}
        and sessions == {"control_8h"}
        and len(hashes) == 24
    )
    return _p(f"build_universe produce 24 contratos válidos (3 assets x 2 years x 2 triggers x "
              f"2 managements), session=control_8h fijo, trigger={{'T1_ema_cross','A_sweep_bos'}} "
              f"exacto (visto: {triggers}), management={{'V3-A','V3-B'}} exacto (visto: {mgmts})", ok)


def test_raw_y_triggers_extra_explicitamente_excluidos_del_universo():
    """Guardia de regresión (2026-09-09): TRIGGERS/MANAGEMENTS son tuplas
    EXPLÍCITAS -- si en el futuro se agrega otro Trigger a
    research.TRIGGER_LAYERS (hoy ya tiene D_range_breakout/C_bos_only,
    agregados después) u otro management a
    research.runner.MANAGEMENT_LAYERS (Raw), esta campaña NO debe cambiar
    de alcance silenciosamente."""
    ok = (
        camp.TRIGGERS == ("T1_ema_cross", "A_sweep_bos")
        and camp.MANAGEMENTS == ("V3-A", "V3-B")
        and "Raw" not in camp.MANAGEMENTS
        and "Raw" in runner.MANAGEMENT_LAYERS
        and set(research.TRIGGER_LAYERS) - set(camp.TRIGGERS)  # confirma que el registro es MÁS grande
    )
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    ok = ok and len(contracts) == 4  # 2 triggers x 2 managements x 1 asset x 1 year
    ok = ok and all(c["management"]["name"] != "Raw" for c in contracts)
    ok = ok and all(c["trigger"]["name"] in ("T1_ema_cross", "A_sweep_bos") for c in contracts)
    return _p("TRIGGERS/MANAGEMENTS explícitos -- Raw y D_range_breakout/C_bos_only excluidos del "
              "universo incluso estando presentes en los registros globales (guard de regresión)", ok)


def test_run_blind_test_requires_frozen_candidate():
    """Mismo guardrail que la versión legacy — no se puede correr 2024 sin
    un candidato ya congelado tras 2022+2023. Se puede probar sin data/raw/
    porque el chequeo ocurre antes de cualquier I/O."""
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="bogus_trigger")
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_restringe_universo_a_un_trigger():
    """run_blind_test debe construir contratos solo para el Trigger
    congelado (ambos managements, todos los activos) -- verificado sin
    tocar datos reales (contratos estructurales, runner.run_many
    cortocircuitado)."""
    orig_run_many = runner.run_many
    runner.run_many = lambda contracts: []  # cortocircuito -- no toca dc_v1/datos reales
    try:
        contracts, results = camp.run_blind_test(assets=("BTCUSDT",), candidate="A_sweep_bos")
    finally:
        runner.run_many = orig_run_many

    ok = (
        len(contracts) == len(camp.MANAGEMENTS)  # 1 trigger x 1 asset x 1 año x 2 managements
        and all(c["trigger"]["name"] == "A_sweep_bos" for c in contracts)
        and {c["management"]["name"] for c in contracts} == {"V3-A", "V3-B"}
    )
    return _p("run_blind_test construye contratos solo para el Trigger congelado x MANAGEMENTS "
              "explícitos", ok)


def test_results_to_frame_deriva_de_experiment_result_sin_columnas_diagnosticas():
    """results_to_frame ya no reconstruye PF/WR/expectancy a mano ni
    fabrica entries_per_month/fill_rate/be/reason_stop/reason_timeout --
    deriva DIRECTAMENTE de ExperimentResult vía research.to_experiment_rows
    (C6), ver mapping legacy->canónico documentado en el docstring del
    módulo."""
    from research.schema import ExperimentResult
    r = ExperimentResult(
        experiment_name="x", asset="BTCUSDT", period=2022, period_role="train",
        bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
        session="control_8h", management="V3-A", n_entries=63, n_trades=62,
        pf=1.2, wr=30.0, exp_r=0.05, total_r=1.0, max_dd=-3.0, freq=7.5, gate_pass=False,
        contract_hash="abc", dataset_version="market-data-v1", pipeline_version="dc-v1",
        engine_version="research-engine-1",
    )
    df = camp.results_to_frame([r])
    row = df.iloc[0]
    ok = (
        row["asset"] == "BTCUSDT" and row["period"] == 2022 and row["trigger"] == "T1_ema_cross"
        and row["management"] == "V3-A" and row["pf"] == 1.2
        and "entries_per_month" not in df.columns and "fill_rate" not in df.columns
        and "be" not in df.columns and "reason_stop" not in df.columns
    )
    return _p("results_to_frame deriva directamente de ExperimentResult (vía "
              "research.to_experiment_rows), sin columnas diagnósticas legacy", ok)


# --------------------------------------------------------------------------- #
# EQUIVALENCIA sobre datos reales — la prueba principal de la migración.    #
# Requiere `data/raw/` poblado Y los artifacts históricos ya committeados.  #
# Si no están disponibles, reporta FAIL explícito, no un salto silencioso.  #
# --------------------------------------------------------------------------- #
_LEGACY_RESULTS_PATH = "trigger_campaign_results.csv"
_LEGACY_DECISION_PATH = "trigger_campaign_decision.csv"
_EXIT_LABEL = {"V3-A": "V3-A (1R/2R/1R)", "V3-B": "V3-B (0.75R/1.5R/0.75R)"}
_METRIC_FIELDS = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass")


def test_migracion_24_celdas_equivale_a_legacy_sobre_datos_reales():
    """LA PRUEBA PRINCIPAL: ejecuta el script MIGRADO (run_campaign, sobre
    datos reales de data/raw/) y compara sus 24 ExperimentResult, celda por
    celda (clave semántica, no posición), contra el artifact histórico
    trigger_campaign_results.csv (NUNCA modificado). 24/24 deben coincidir
    exacto en las 9 columnas de métricas/gates, NaN-aware -- incluyendo
    explícitamente las 6 filas de A_sweep_bos/2023 (muestra <5 trades ->
    metrics=None -> todos los campos numéricos NaN/None)."""
    if not os.path.exists("data/raw") or not os.path.exists(_LEGACY_RESULTS_PATH):
        return _p("equivalencia 24/24 contra el artifact histórico (data/raw/ o el artifact "
                  "histórico no disponibles en este entorno)", False)

    contracts, results = camp.run_campaign()
    legacy = pd.read_csv(_LEGACY_RESULTS_PATH)

    legacy_idx = {}
    for _, row in legacy.iterrows():
        key = (row["asset"], int(row["year"]), row["candidate"], row["exit_config"])
        legacy_idx[key] = row

    matched = 0
    mismatches = []
    nan_rows_ok = 0
    for r in results:
        key = (r.asset, r.period, r.trigger, _EXIT_LABEL[r.management])
        lrow = legacy_idx.get(key)
        if lrow is None:
            mismatches.append((key, "NO_LEGACY_ROW"))
            continue
        row_ok = True
        is_nan_case = pd.isna(lrow["pf"])
        for f in _METRIC_FIELDS:
            lv = lrow[f]
            cv = getattr(r, f)
            if f == "gate_pass":
                eq = bool(lv) == bool(cv)
            elif f in ("n_entries", "n_trades"):
                eq = int(lv) == int(cv)
            else:
                lvf = float(lv) if not pd.isna(lv) else float("nan")
                cvf = float(cv) if cv is not None else float("nan")
                eq = (lvf == cvf) or (lvf != lvf and cvf != cvf)
            if not eq:
                row_ok = False
                mismatches.append((key, f, lv, cv))
        if row_ok:
            matched += 1
            if is_nan_case:
                nan_rows_ok += 1

    ok = len(contracts) == 24 and len(results) == 24 and matched == 24 and not mismatches and nan_rows_ok == 6
    if mismatches:
        for m in mismatches[:10]:
            print(f"    mismatch: {m}")
    return _p(f"24/24 contratos, 24/24 resultados, {matched}/24 celdas equivalentes exactas "
              f"contra {_LEGACY_RESULTS_PATH} ({len(mismatches)} mismatches), "
              f"{nan_rows_ok}/6 filas NaN (A_sweep_bos/2023) verificadas NaN-aware", ok)


def test_decision_migrada_equivale_a_legacy_sobre_datos_reales():
    """Decisión canónica (C5, candidate_fields=('trigger','management')) vs
    trigger_campaign_decision.csv (NUNCA modificado): mismo número de
    candidatos (12) y mismo conjunto (vacío) de sobrevivientes."""
    if not os.path.exists("data/raw") or not os.path.exists(_LEGACY_DECISION_PATH):
        return _p("decisión equivalente al artifact histórico (data/raw/ o el artifact "
                  "histórico no disponibles en este entorno)", False)

    contracts, results = camp.run_campaign()
    decisions = summarize_decision(
        results, candidate_fields=("trigger", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    legacy_dec = pd.read_csv(_LEGACY_DECISION_PATH)

    canon_survivors = {(d.asset, d.candidate[0], d.candidate[1]) for d in decisions if d.survives_required_roles}
    _inv_label = {v: k for k, v in _EXIT_LABEL.items()}
    legacy_survivors = {
        (row["asset"], row["candidate"], _inv_label[row["exit_config"]])
        for _, row in legacy_dec.iterrows() if row["survives_both_years"]
    }

    ok = (
        len(decisions) == 12 and len(legacy_dec) == 12
        and canon_survivors == legacy_survivors == set()
    )
    return _p(f"decisión canónica (12 candidatos) equivale a la decisión legacy (12 filas) -- "
              f"mismo conjunto de sobrevivientes ({canon_survivors})", ok)


def test_persistence_roundtrip_campania_migrada_sobre_datos_reales():
    """C6 write -> C8 read -> C7 compare_results sobre los 24 resultados
    reales de la campaña migrada, en un artifact TEMPORAL (nunca
    trigger_campaign_*.csv históricos ni los canonical_*.csv de main())."""
    if not os.path.exists("data/raw"):
        return _p("persistence round-trip sobre datos reales (data/raw/ no disponible)", False)

    contracts, results = camp.run_campaign()
    tmp_path = "test_migracion_trigger_campaign_TEMP.csv"
    try:
        write_experiment_results_csv(tmp_path, results)
        read_back = read_experiment_results_csv(tmp_path)
        comps = [compare_results(read_back[i], results[i]) for i in range(len(results))]
        ok = len(read_back) == 24 and all(c.matches for c in comps)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return _p("C6 write -> C8 read -> C7 compare produce 24/24 ExperimentResult idénticos "
              "(artifact temporal, eliminado al terminar)", ok)


ALL_TESTS = [
    test_find_entries_for_trigger_t1_matches_backtest_find_entries,
    test_find_entries_for_trigger_runs_both_candidates_end_to_end,
    test_raw_events_rejects_unknown_trigger_name,
    test_build_universe_produce_24_contratos_triggers_y_managements_exactos,
    test_raw_y_triggers_extra_explicitamente_excluidos_del_universo,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_restringe_universo_a_un_trigger,
    test_results_to_frame_deriva_de_experiment_result_sin_columnas_diagnosticas,
    test_migracion_24_celdas_equivale_a_legacy_sobre_datos_reales,
    test_decision_migrada_equivale_a_legacy_sobre_datos_reales,
    test_persistence_roundtrip_campania_migrada_sobre_datos_reales,
]


def main():
    print("scripts/trigger_campaign — validación estructural + equivalencia migración C1-C8\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
