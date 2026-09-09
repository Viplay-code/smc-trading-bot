"""
research/tests/test_gestion_campaign_session.py — Validación ESTRUCTURAL (con
datos sintéticos, para los sanity-checks de acoplamiento sessions<->Trigger)
Y de EQUIVALENCIA (con datos reales, para el universo canónico) de
scripts/gestion_campaign_session.py, MIGRADO a C1-C8 (2026-09-09).

Verifica explícitamente las dos propiedades formales del diseño original
(2026-07-29), preservadas sin cambio de significado por la migración:
(1) eventos crudos de T1 idénticos entre ventanas de sesión, (2) n_entries
monótono no decreciente entre ventanas anidadas — Y que ambos sanity-checks
detectan una violación real cuando se les da una, no solo que pasan en el
caso feliz. También verifica que note_concurrency_effects señala (sin
excepción) un caso de n_trades NO monótono.

Además de lo estructural, verifica el universo canónico (C4 expand_universe,
36 contratos, exactamente V3-A/V3-B, Raw excluido — guardia de regresión) y,
sobre datos reales (`data/raw/`), la equivalencia 36/36 contra los artifacts
históricos (`gestion_campaign_session_results.csv`/`_decision.csv`) — la
prueba principal de la migración.

Ejecutar:
    python -m research.tests.test_gestion_campaign_session  (o con pytest)
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

sys.path.insert(0, ".")
import research
from research import runner
from research.comparison import compare_results
from research.persistence import read_experiment_results_csv
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as camp

Path("smc_bot.log").unlink(missing_ok=True)


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def make_synthetic_raw_1h(start="2021-10-01", n=8000, seed=7) -> pd.DataFrame:
    """Misma forma que en los tests de las campañas anteriores, duplicada
    acá por la misma convención (cada archivo de test es standalone)."""
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


def _build_2022_sliced():
    raw = make_synthetic_raw_1h()
    df_full = build_dc_v1(raw, asset="TESTUSDT", dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    # BIAS_CANDIDATE_LEGACY ("A"), NO BIAS_CANDIDATE ("A_ema200_neutral") --
    # bias_camp.apply_bias espera la etiqueta legacy de scripts/bias_campaign.py,
    # distinta del nombre de registro canónico usado en el contrato C2 (ver
    # docstring de scripts/gestion_campaign_session.py).
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, camp.BIAS_CANDIDATE_LEGACY)
    sliced = period_slice(df_full, 2022)
    return sliced, errs


def _raw_and_entry_counts(sliced: pd.DataFrame) -> tuple[dict, dict]:
    raw_counts, entry_counts = {}, {}
    for label in camp.NESTED_ORDER:
        cfg = camp._cfg_for(label)
        frame = bias_camp.to_backtest_frame(sliced, sliced["bias_A"], cfg)
        raw_counts[label] = len(trigger_camp._raw_events(frame, camp.TRIGGER_CANDIDATE, cfg))
        entry_counts[label] = len(trigger_camp.find_entries_for_trigger(frame, cfg, camp.TRIGGER_CANDIDATE))
    return raw_counts, entry_counts


# --------------------------------------------------------------------------- #
# Sanity-checks científicos (datos sintéticos) — PRESERVADOS sin cambio de   #
# significado por la migración.                                              #
# --------------------------------------------------------------------------- #
def test_raw_events_identical_across_session_windows_on_synthetic_data():
    """Prueba 1 del diseño: eventos crudos de T1 idénticos (no solo
    monótonos) entre control_8h/dcv1_activo_15h/sin_filtro_24h, porque
    `sessions` no está en la firma de trigger_T1_ema_cross."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("eventos crudos idénticos entre ventanas de sesión (slice 2022 vacío)", False)
    raw_counts, _ = _raw_and_entry_counts(sliced)
    ok = (not errs) and len(set(raw_counts.values())) == 1
    return _p(f"eventos crudos de T1 idénticos entre las 3 ventanas en datos sintéticos ({raw_counts})", ok)


def test_n_entries_monotonic_across_nested_session_windows_on_synthetic_data():
    """Prueba 2 del diseño: n_entries monótono no decreciente entre las 3
    ventanas anidadas."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("n_entries monótono entre ventanas anidadas (slice 2022 vacío)", False)
    _, entry_counts = _raw_and_entry_counts(sliced)
    counts = [entry_counts[label] for label in camp.NESTED_ORDER]
    ok = (not errs) and counts[0] <= counts[1] <= counts[2]
    try:
        camp.assert_n_entries_monotonic(entry_counts, "TESTUSDT", 2022)
    except AssertionError:
        ok = False
    return _p(f"n_entries monótono no decreciente en datos sintéticos ({dict(zip(camp.NESTED_ORDER, counts))})", ok)


def test_sanity_checks_detect_real_violations():
    """Que ninguno de los dos sanity-checks sea un chequeo vacío: si se les
    da una divergencia/no-monotonicidad real, deben revenir con
    AssertionError. Prueba la lógica de detección en sí."""
    ok = True
    try:
        camp.assert_raw_events_session_invariant(
            {"control_8h": 10, "dcv1_activo_15h": 12, "sin_filtro_24h": 10}, "TESTUSDT", 2022)
        ok = False
    except AssertionError:
        pass
    try:
        camp.assert_n_entries_monotonic(
            {"control_8h": 10, "dcv1_activo_15h": 8, "sin_filtro_24h": 12}, "TESTUSDT", 2022)
        ok = False
    except AssertionError:
        pass
    # casos felices: no deben revenir
    try:
        camp.assert_raw_events_session_invariant(
            {"control_8h": 10, "dcv1_activo_15h": 10, "sin_filtro_24h": 10}, "TESTUSDT", 2022)
        camp.assert_n_entries_monotonic(
            {"control_8h": 10, "dcv1_activo_15h": 12, "sin_filtro_24h": 15}, "TESTUSDT", 2022)
    except AssertionError:
        ok = False
    return _p("ambos sanity-checks revientan con violaciones reales y pasan en el caso feliz", ok)


def test_run_sanity_checks_end_to_end_sobre_datos_sinteticos():
    """Pipeline de verificación completo (`run_sanity_checks` ->
    `_build_windows_and_verify` -> ambos sanity-checks, las 3 ventanas) para
    un (activo, año) sintético, sin excepciones — reemplaza al viejo
    `test_run_asset_year_end_to_end_all_session_windows` (la función
    `run_asset_year` ya no existe: la ejecución real de resultados migró a
    `research.runner.run_many`, que NO acepta datos sintéticos inyectados
    por monkeypatch de `trigger_camp.load_asset_year` — ese monkeypatch solo
    afecta a la ruta de sanity-checks, que sigue usando esas primitivas
    legacy a propósito, ver docstring del módulo)."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("run_sanity_checks end-to-end (las 3 ventanas)", False)

    orig = trigger_camp.load_asset_year
    trigger_camp.load_asset_year = lambda asset, year: sliced
    ok = True
    try:
        camp.run_sanity_checks(("TESTUSDT",), (2022,))
    except AssertionError:
        ok = False
    finally:
        trigger_camp.load_asset_year = orig

    ok = ok and not errs
    return _p("run_sanity_checks corre sin excepciones para las 3 ventanas sobre datos sintéticos", ok)


def test_note_concurrency_effects_flags_non_monotonic_n_trades_without_raising():
    """El contraejemplo del diseño (2026-07-29): n_entries sube (3->4) pero
    n_trades baja (3->2) por una entrada larga que bloquea dos entradas más
    cortas — note_concurrency_effects debe señalarlo en el output SIN
    lanzar ninguna excepción (es información, no un error). Adaptado a las
    columnas canónicas (asset/period/session/management/n_trades) en vez de
    las legacy (asset/year/candidate/exit_config)."""
    rows = [
        {"asset": "BTCUSDT", "period": 2022, "session": "control_8h", "management": "V3-A", "n_trades": 3},
        {"asset": "BTCUSDT", "period": 2022, "session": "dcv1_activo_15h", "management": "V3-A", "n_trades": 2},
        {"asset": "BTCUSDT", "period": 2022, "session": "sin_filtro_24h", "management": "V3-A", "n_trades": 2},
    ]
    df = pd.DataFrame(rows)

    buf = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(buf):
            camp.note_concurrency_effects(df)
    except Exception:
        ok = False
    output = buf.getvalue()
    ok = ok and ("BTCUSDT" in output) and ("no es un error" in output or "Nota" in output)
    return _p("note_concurrency_effects señala n_trades no monótono sin lanzar excepción "
              "(columnas canónicas)", ok)


# --------------------------------------------------------------------------- #
# Universo canónico (C4) — estructural, sin datos reales                    #
# --------------------------------------------------------------------------- #
def test_build_universe_produce_36_contratos_v3a_v3b_sin_raw():
    contracts = camp.build_universe(("BTCUSDT", "ETHUSDT", "SOLUSDT"), {"train": 2022, "validate": 2023})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    mgmts = {c["management"]["name"] for c in contracts}
    sessions = {c["session"] for c in contracts}
    hashes = {research.compute_contract_hash(c) for c in contracts}
    ok = (
        len(contracts) == 36
        and mgmts == {"V3-A", "V3-B"}
        and sessions == set(camp.NESTED_ORDER)
        and len(hashes) == 36
    )
    return _p(f"build_universe produce 36 contratos válidos (3 assets x 2 years x 3 sessions x "
              f"2 managements), management={{'V3-A','V3-B'}} exacto (visto: {mgmts})", ok)


def test_raw_explicitamente_excluido_del_universo_incluso_si_el_registro_crece():
    """Guardia de regresión (sección 11 de la migración, 2026-09-09):
    MANAGEMENTS es una tupla EXPLÍCITA -- si en el futuro se agrega OTRO
    management a research.runner.MANAGEMENT_LAYERS/research.EXIT_CONFIGS,
    esta campaña NO debe cambiar de alcance silenciosamente. Confirma
    ADEMÁS que el guard es real (no trivialmente verdadero): Raw SÍ está
    presente en el registro global HOY, y aun así queda fuera del universo
    de esta campaña."""
    ok = (
        camp.MANAGEMENTS == ("V3-A", "V3-B")
        and "Raw" not in camp.MANAGEMENTS
        and "Raw" in runner.MANAGEMENT_LAYERS
        and "Raw" in research.EXIT_CONFIGS
    )
    contracts = camp.build_universe(("BTCUSDT",), {"train": 2022})
    # 3 sessions x 2 managements x 1 asset x 1 year = 6 contratos
    ok = ok and len(contracts) == 6 and all(c["management"]["name"] != "Raw" for c in contracts)
    return _p("MANAGEMENTS = ('V3-A','V3-B') explícito -- Raw excluido del universo incluso estando "
              "presente en research.runner.MANAGEMENT_LAYERS/research.EXIT_CONFIGS (guard de regresión)", ok)


def test_run_blind_test_requires_frozen_candidate():
    ok = True
    try:
        camp.run_blind_test(candidate=None)
        ok = False
    except ValueError:
        pass
    try:
        camp.run_blind_test(candidate="ventana_inventada")
        ok = False
    except ValueError:
        pass
    return _p("run_blind_test exige --candidate en CANDIDATES antes de tocar data/raw/", ok)


def test_run_blind_test_also_runs_sanity_checks_y_restringe_a_una_ventana():
    """Corrección 2026-07-29, preservada por la migración: run_blind_test
    debe pasar por los sanity-checks (espía sobre assert_n_entries_monotonic)
    Y el universo construido debe restringirse a la ÚNICA ventana congelada
    (con AMBOS managements). `runner.run_many` se cortocircuita (no debe
    tocar dc_v1/datos reales para "TESTUSDT", que no existe) — la ejecución
    real ya está cubierta por test_migracion_36_celdas_equivale_a_legacy más
    abajo, con datos reales."""
    sliced, errs = _build_2022_sliced()
    if sliced.empty:
        return _p("run_blind_test invoca los sanity-checks", False)

    calls = []
    orig_assert = camp.assert_n_entries_monotonic

    def spy(counts, asset, year):
        calls.append((asset, year))
        return orig_assert(counts, asset, year)

    orig_load = trigger_camp.load_asset_year
    orig_run_many = runner.run_many
    trigger_camp.load_asset_year = lambda asset, year: sliced
    camp.assert_n_entries_monotonic = spy
    runner.run_many = lambda contracts: []  # cortocircuito -- no toca dc_v1/datos reales
    try:
        contracts, results = camp.run_blind_test(assets=("TESTUSDT",), candidate="dcv1_activo_15h")
    finally:
        trigger_camp.load_asset_year = orig_load
        camp.assert_n_entries_monotonic = orig_assert
        runner.run_many = orig_run_many

    ok = (
        not errs
        and calls == [("TESTUSDT", camp.BLIND_YEAR)]
        and len(contracts) == len(camp.MANAGEMENTS)  # 1 ventana x 1 asset x 1 año x 2 managements
        and all(c["session"] == "dcv1_activo_15h" for c in contracts)
        and {c["management"]["name"] for c in contracts} == {"V3-A", "V3-B"}
    )
    return _p("run_blind_test invoca assert_n_entries_monotonic Y construye contratos solo para la "
              "ventana congelada x MANAGEMENTS explícitos", ok)


def test_results_to_frame_deriva_de_experiment_result_sin_columnas_diagnosticas():
    """results_to_frame ya no reconstruye PF/WR/expectancy a mano ni
    fabrica columnas diagnósticas legacy (avg_win/avg_loss/entries_per_month/
    fill_rate/be/reason_stop/reason_timeout) -- deriva DIRECTAMENTE de
    ExperimentResult vía research.to_experiment_rows (C6), ver mapping
    legacy->canónico documentado en el docstring del módulo."""
    from research.schema import ExperimentResult
    r = ExperimentResult(
        experiment_name="x", asset="BTCUSDT", period=2022, period_role="train",
        bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
        session="dcv1_activo_15h", management="V3-A", n_entries=90, n_trades=85,
        pf=1.2, wr=30.0, exp_r=0.05, total_r=1.0, max_dd=-3.0, freq=7.5, gate_pass=False,
        contract_hash="abc", dataset_version="market-data-v1", pipeline_version="dc-v1",
        engine_version="research-engine-1",
    )
    df = camp.results_to_frame([r])
    row = df.iloc[0]
    ok = (
        row["asset"] == "BTCUSDT" and row["period"] == 2022 and row["session"] == "dcv1_activo_15h"
        and row["management"] == "V3-A" and row["pf"] == 1.2
        and "avg_win" not in df.columns and "avg_loss" not in df.columns
        and "entries_per_month" not in df.columns and "fill_rate" not in df.columns
    )
    return _p("results_to_frame deriva directamente de ExperimentResult (vía "
              "research.to_experiment_rows), sin columnas diagnósticas legacy", ok)


# --------------------------------------------------------------------------- #
# EQUIVALENCIA sobre datos reales — la prueba principal de la migración.    #
# Requiere `data/raw/` poblado (BTCUSDT/ETHUSDT/SOLUSDT, 2022/2023) Y los   #
# artifacts históricos ya committeados. Si no están disponibles, reporta    #
# FAIL explícito en vez de saltarse silenciosamente la prueba principal.    #
# --------------------------------------------------------------------------- #
_LEGACY_RESULTS_PATH = "gestion_campaign_session_results.csv"
_LEGACY_DECISION_PATH = "gestion_campaign_session_decision.csv"
_EXIT_LABEL = {"V3-A": "V3-A (1R/2R/1R)", "V3-B": "V3-B (0.75R/1.5R/0.75R)"}
_METRIC_FIELDS = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass")


def test_migracion_36_celdas_equivale_a_legacy_sobre_datos_reales():
    """LA PRUEBA PRINCIPAL: ejecuta el script MIGRADO (run_campaign, sobre
    datos reales de data/raw/) y compara sus 36 ExperimentResult, celda por
    celda, contra el artifact histórico gestion_campaign_session_results.csv
    (NUNCA modificado por este test). 36/36 deben coincidir exacto en las 9
    columnas de métricas/gates -- sin tolerancia."""
    if not os.path.exists("data/raw") or not os.path.exists(_LEGACY_RESULTS_PATH):
        return _p("equivalencia 36/36 contra el artifact histórico (data/raw/ o el artifact "
                  "histórico no disponibles en este entorno)", False)

    contracts, results = camp.run_campaign()
    legacy = pd.read_csv(_LEGACY_RESULTS_PATH)

    legacy_idx = {}
    for _, row in legacy.iterrows():
        key = (row["asset"], int(row["year"]), row["candidate"], row["exit_config"])
        legacy_idx[key] = row

    matched = 0
    mismatches = []
    for r in results:
        key = (r.asset, r.period, r.session, _EXIT_LABEL[r.management])
        lrow = legacy_idx.get(key)
        if lrow is None:
            mismatches.append((key, "NO_LEGACY_ROW"))
            continue
        row_ok = True
        for f in _METRIC_FIELDS:
            lv = lrow[f]
            cv = getattr(r, f)
            if f == "gate_pass":
                eq = bool(lv) == bool(cv)
            elif f in ("n_entries", "n_trades"):
                eq = int(lv) == int(cv)
            else:
                lvf, cvf = float(lv), float(cv)
                eq = (lvf == cvf) or (lvf != lvf and cvf != cvf)
            if not eq:
                row_ok = False
                mismatches.append((key, f, lv, cv))
        if row_ok:
            matched += 1

    ok = len(contracts) == 36 and len(results) == 36 and matched == 36 and not mismatches
    if mismatches:
        for m in mismatches[:10]:
            print(f"    mismatch: {m}")
    return _p(f"36/36 contratos, 36/36 resultados, {matched}/36 celdas equivalentes exactas "
              f"contra {_LEGACY_RESULTS_PATH} ({len(mismatches)} mismatches)", ok)


def test_decision_migrada_equivale_a_legacy_sobre_datos_reales():
    """Decisión canónica (C5, candidate_fields=('session','management')) vs
    gestion_campaign_session_decision.csv (NUNCA modificado): mismo número
    de candidatos (18) y mismo conjunto (vacío) de sobrevivientes."""
    if not os.path.exists("data/raw") or not os.path.exists(_LEGACY_DECISION_PATH):
        return _p("decisión equivalente al artifact histórico (data/raw/ o el artifact "
                  "histórico no disponibles en este entorno)", False)

    from research.decision import summarize_decision
    contracts, results = camp.run_campaign()
    decisions = summarize_decision(
        results, candidate_fields=("session", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    legacy_dec = pd.read_csv(_LEGACY_DECISION_PATH)

    canon_survivors = {(d.asset, d.candidate[0], d.candidate[1]) for d in decisions if d.survives_required_roles}
    legacy_survivors = {
        (row["asset"], row["candidate"], row["exit_config"])
        for _, row in legacy_dec.iterrows() if row["survives_both_years"]
    }
    # Normalizar exit_config legacy ("V3-A (1R/2R/1R)") a management canónico ("V3-A")
    _inv_label = {v: k for k, v in _EXIT_LABEL.items()}
    legacy_survivors_norm = {(a, s, _inv_label[e]) for a, s, e in legacy_survivors}

    ok = (
        len(decisions) == 18 and len(legacy_dec) == 18
        and canon_survivors == legacy_survivors_norm == set()
    )
    return _p(f"decisión canónica (18 candidatos) equivale a la decisión legacy (18 filas) -- "
              f"mismo conjunto de sobrevivientes ({canon_survivors})", ok)


def test_persistence_roundtrip_campania_migrada_sobre_datos_reales():
    """C6 write -> C8 read sobre los 36 resultados reales de la campaña
    migrada, en un artifact TEMPORAL (nunca gestion_campaign_session_*.csv
    históricos ni los canonical_*.csv de main())."""
    if not os.path.exists("data/raw"):
        return _p("persistence round-trip sobre datos reales (data/raw/ no disponible)", False)

    from research.persistence import write_experiment_results_csv
    contracts, results = camp.run_campaign()
    tmp_path = "test_migracion_gestion_campaign_session_TEMP.csv"
    try:
        write_experiment_results_csv(tmp_path, results)
        read_back = read_experiment_results_csv(tmp_path)
        comps = [compare_results(read_back[i], results[i]) for i in range(len(results))]
        ok = len(read_back) == 36 and all(c.matches for c in comps)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return _p("C6 write -> C8 read produce 36/36 ExperimentResult idénticos (artifact temporal, "
              "eliminado al terminar)", ok)


ALL_TESTS = [
    test_raw_events_identical_across_session_windows_on_synthetic_data,
    test_n_entries_monotonic_across_nested_session_windows_on_synthetic_data,
    test_sanity_checks_detect_real_violations,
    test_run_sanity_checks_end_to_end_sobre_datos_sinteticos,
    test_note_concurrency_effects_flags_non_monotonic_n_trades_without_raising,
    test_build_universe_produce_36_contratos_v3a_v3b_sin_raw,
    test_raw_explicitamente_excluido_del_universo_incluso_si_el_registro_crece,
    test_run_blind_test_requires_frozen_candidate,
    test_run_blind_test_also_runs_sanity_checks_y_restringe_a_una_ventana,
    test_results_to_frame_deriva_de_experiment_result_sin_columnas_diagnosticas,
    test_migracion_36_celdas_equivale_a_legacy_sobre_datos_reales,
    test_decision_migrada_equivale_a_legacy_sobre_datos_reales,
    test_persistence_roundtrip_campania_migrada_sobre_datos_reales,
]


def main():
    print("scripts/gestion_campaign_session — validación estructural + equivalencia migración C1-C8\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
