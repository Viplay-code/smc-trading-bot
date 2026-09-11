#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/donchian_breakout_management_hypothesis.py — Fase 4 (H-M,
2026-09-11), implementación del Protocol v2 FINAL pre-registrado.

PREGUNTA CIENTÍFICA: ¿una salida estructural basada en un canal Donchian
de lookback corto preserva mejor los movimientos favorables del breakout
Donchian N=10 que los Management V3 existentes, bajo controles
completamente congelados?

H-M (hipótesis, enunciada sobre CAPTURA, sin referencia a gates):
`DCH-EXIT` preserva una fracción mayor del movimiento favorable
disponible en cada operación que `V3-A`/`V3-B` sobre el mismo universo.
  - Predicción mecanística:  ↑ avg_win, ↑ MFE_capture_ratio, ↑ mean duration_h
  - Consecuencia económica:  ↑ exp_r, ↑ PF, POTENCIALMENTE supervivencia C5
C5 y la promoción 2/3 son criterios de decisión INDEPENDIENTES: no forman
parte de la definición del mecanismo (corrección anti-circularidad del
Protocol v2).

TRES CAPAS SEPARADAS (exigidas por el protocolo, no una elección libre):

  1. UNIDAD EXPERIMENTAL: asset x management x year = 18 observaciones.
     - 12 CONTROLES: reutilizados del baseline CONGELADO
       (`donchian_breakout_baseline_results.csv`, commit e20d3e24),
       rehidratados con C8 `read_experiment_results_csv`. NUNCA se
       re-ejecutan como campaña, NUNCA se les fabrica un contract_hash.
     - 6 TRATAMIENTO: DCH-EXIT, únicas ejecuciones nuevas de esta fase.

  2. UNIDAD DE DECISIÓN (C5, SIN MODIFICAR): asset x management, exige
     gate_pass=True en train Y validate. `management` SÍ es campo real de
     `ExperimentResult`, así que C5 se invoca UNA SOLA VEZ sobre las 18
     observaciones con `candidate_fields=("management",)`.

  3. UNIDAD DE PROMOCIÓN (capa externa a C5, NO parte de decision.py):
     management, agregado sobre los 3 activos; promovido si >= 2/3
     sobreviven. Regla PRE-REGISTRADA, no modificable tras ver resultados.
     Se aplica IDÉNTICAMENTE a V3-A, V3-B y DCH-EXIT.

DIAGNOSTIC RE-DERIVATION (Protocol v2 seccion 4.b): los 12 controles se
re-ejecutan SOLO para recuperar observables que C6 nunca persistió
(TradeRecord -> avg_win/avg_loss/duration_h, y MFE/MAE). NO es una
campaña: no escribe ningún artifact histórico, no genera contract_hash
nuevos, no altera C5 ni ninguna decisión previa. Exige VERIFICACIÓN DE
IDENTIDAD obligatoria contra el artifact congelado (contract_hash + las 9
métricas core); cualquier discrepancia ABORTA Fase 4.

SIN SELECCIÓN SECUENCIAL: `run_treatment()` construye los 6 contratos,
los valida TODOS y los ejecuta TODOS en una sola llamada a `run_many`.
No existe ninguna rama condicional que decida ejecutar un contrato en
función del resultado de otro, ni que mire 2022 para decidir 2023.

MFE/MAE/MFE_capture_ratio son DIAGNÓSTICOS DE MECANISMO: nunca gates,
nunca modifican C5 ni la promoción, nunca rescatan un management que
falle C5, nunca permiten selección post-hoc. Se calculan de forma
IDÉNTICA para tratamiento y controles.

VARIABLES CONGELADAS (idénticas al baseline N=10):
  assets=BTCUSDT/ETHUSDT/SOLUSDT, range_lookback=10 (default del Trigger,
  trigger.params={}), Bias=A_ema200_neutral, Entry=C_market_close,
  session=sin_filtro_24h, atr_period=14, atr_mult=1.5, risk=0.005,
  cost_per_trade=0.0009, max_hold=20, train=2022/validate=2023, gates
  canónicos SIN modificar.
La ÚNICA variable experimental es `management`.

Artifacts (Protocol v2 seccion 19):
  1. donchian_breakout_management_results.csv     — SOLO las 6 filas nuevas
  2. donchian_breakout_management_comparison.csv  — las 18, con provenance
  3. donchian_breakout_management_decision.csv    — 9 filas (C5)
  4. donchian_breakout_management_diagnostics.csv — N1+N2, rotulado no-gate
Los artifacts del baseline y de Fase 3 NO se tocan.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/donchian_breakout_management_hypothesis.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import csv

import pandas as pd

import backtest
import research
from research import runner
from research.decision import summarize_decision
from research.expand import expand_universe
from research.persistence import (
    read_experiment_results_csv, write_experiment_results_csv, write_decision_csv,
)
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Alcance experimental CONGELADO (ver docstring del módulo)                  #
# --------------------------------------------------------------------------- #
IN_SAMPLE_YEAR = 2022
VALIDATION_YEAR = 2023

BIAS_CANDIDATE = "A_ema200_neutral"
TRIGGER_CANDIDATE = "D_range_breakout"
ENTRY_CANDIDATE = "C_market_close"
SESSION = "sin_filtro_24h"

TREATMENT = "DCH-EXIT"
CONTROLS = ("V3-A", "V3-B")
ALL_MANAGEMENTS = CONTROLS + (TREATMENT,)

ATR_MULT = 1.5
ATR_PERIOD = 14
RISK = 0.005
COST_PER_TRADE = 0.0009
MAX_HOLD = 20

PROMOTION_MIN_ASSETS = 2   # de 3 — PRE-REGISTRADO, no modificable post-hoc

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}

BASELINE_RESULTS_PATH = "donchian_breakout_baseline_results.csv"   # CONGELADO, solo lectura

RESULTS_PATH = "donchian_breakout_management_results.csv"
COMPARISON_PATH = "donchian_breakout_management_comparison.csv"
DECISION_PATH = "donchian_breakout_management_decision.csv"
DIAGNOSTICS_PATH = "donchian_breakout_management_diagnostics.csv"

CORE_METRICS = ("n_entries", "n_trades", "pf", "wr", "exp_r",
                "total_r", "max_dd", "freq", "gate_pass")


# --------------------------------------------------------------------------- #
# Capa 1a — TRATAMIENTO: universo canónico (C4) + ejecución (C3)            #
# --------------------------------------------------------------------------- #
def build_treatment_universe(
    assets: tuple[str, ...] = ASSETS, years: dict[str, int] | None = None,
) -> list[dict]:
    """6 contratos DCH-EXIT (3 assets x 2 years), vía un único template
    expandido por `research.expand_universe` (C4).

    `trigger.params={}` — idéntico al baseline congelado, preservando la
    declaración exacta del Trigger y su default `range_lookback=10`
    (Protocol v2 seccion 8). `management.params={"exit_lookback": 5}`
    debe coincidir EXACTO con `runner._MANAGEMENT_PARAMS["DCH-EXIT"]` o
    `validate_contract` lo rechaza con ContractError."""
    if years is None:
        years = {"train": IN_SAMPLE_YEAR, "validate": VALIDATION_YEAR}
    template = {
        "name": "donchian_breakout_management_hypothesis",
        "contract_version": "1",
        "assets": list(assets),
        "years": dict(years),
        "bias": {"name": BIAS_CANDIDATE, "params": {}},
        "trigger": {"name": TRIGGER_CANDIDATE, "params": {}},
        "entry": {"name": ENTRY_CANDIDATE, "params": {}},
        "session": SESSION,
        "management": {"name": TREATMENT,
                        "params": {"exit_lookback": runner.DCH_EXIT_LOOKBACK}},
        "risk": RISK,
        "cost_per_trade": COST_PER_TRADE,
        "max_hold": MAX_HOLD,
        "atr_mult": ATR_MULT,
        "gates": dict(_CANONICAL_GATES),
        "independent_variable": "management",
        "blind_authorized": False,
    }
    return expand_universe(template)


def run_treatment(assets: tuple[str, ...] = ASSETS):
    """Ejecuta las 6 celdas DCH-EXIT, COMPLETAS y de una sola vez.

    SIN SELECCIÓN SECUENCIAL por construcción: los 6 contratos se
    construyen, se validan TODOS y se ejecutan TODOS en una única llamada
    a `run_many`. No hay ninguna rama que consulte un resultado para
    decidir si ejecutar otro contrato, ni que mire train para decidir
    validate. `include_trades=True` para habilitar los diagnósticos N1/N2
    (nunca gates)."""
    contracts = build_treatment_universe(assets)
    for c in contracts:
        runner.validate_contract(c)   # ContractError se propagaría sin capturar
    pairs = runner.run_many(contracts, include_trades=True)
    results = [r for r, _ in pairs]
    trades_by_contract = [t for _, t in pairs]
    return contracts, results, trades_by_contract


# --------------------------------------------------------------------------- #
# Capa 1b — CONTROLES: rehidratación del baseline CONGELADO (C8)            #
# --------------------------------------------------------------------------- #
def load_frozen_controls(path: str = BASELINE_RESULTS_PATH) -> list:
    """Rehidrata los 12 controles como `ExperimentResult` de primera
    clase desde el artifact CONGELADO, vía C8 — sin re-ejecutar nada y
    conservando su `contract_hash` original.

    NO modifica el artifact (solo lectura). Valida que el contenido sea
    exactamente el universo de control esperado (12 filas, managements
    V3-A/V3-B, 3 activos, 2 años); cualquier desviación es un error
    ruidoso, nunca un filtrado silencioso."""
    results = read_experiment_results_csv(path)
    mgmts = {r.management for r in results}
    assets = {r.asset for r in results}
    periods = {r.period for r in results}
    if len(results) != 12 or mgmts != set(CONTROLS) or len(assets) != 3 or len(periods) != 2:
        raise ValueError(
            f"El artifact congelado {path!r} no contiene el universo de control esperado "
            f"(12 filas, management={set(CONTROLS)}, 3 activos, 2 años) — encontrado: "
            f"{len(results)} filas, management={mgmts}, activos={assets}, años={periods}."
        )
    return results


def rederive_control_diagnostics(assets: tuple[str, ...] = ASSETS):
    """DIAGNOSTIC RE-DERIVATION (Protocol v2 seccion 4.b) — reconstruye los
    12 contratos de control con el script del baseline (determinista) y
    los re-ejecuta con `include_trades=True` SOLO para recuperar
    observables que C6 nunca persistió (TradeRecord, y de ahí avg_win/
    avg_loss/duration_h, además de habilitar MFE/MAE).

    NO es una campaña: no escribe ningún artifact, no genera contract_hash
    nuevos, no altera C5 ni ninguna decisión previa.

    VERIFICACIÓN DE IDENTIDAD OBLIGATORIA: cada resultado re-derivado debe
    coincidir EXACTAMENTE con su fila congelada en `contract_hash` y en
    las 9 métricas core. Ante cualquier discrepancia LANZA RuntimeError —
    Fase 4 ABORTA, nunca continúa con una re-derivación no verificada."""
    import scripts.donchian_breakout_baseline as baseline_camp

    frozen = load_frozen_controls()
    frozen_by_key = {(r.asset, r.period, r.management): r for r in frozen}

    contracts = baseline_camp.build_universe(assets)
    pairs = runner.run_many(contracts, include_trades=True)

    mismatches = []
    for c, (r, _trades) in zip(contracts, pairs):
        key = (r.asset, r.period, r.management)
        ref = frozen_by_key.get(key)
        if ref is None:
            mismatches.append((key, "SIN_FILA_CONGELADA", None, None))
            continue
        if r.contract_hash != ref.contract_hash:
            mismatches.append((key, "contract_hash", ref.contract_hash, r.contract_hash))
        for f in CORE_METRICS:
            ref_v, new_v = getattr(ref, f), getattr(r, f)
            if f == "gate_pass":
                eq = bool(ref_v) == bool(new_v)
            elif f in ("n_entries", "n_trades"):
                eq = int(ref_v) == int(new_v)
            else:
                rv = float(ref_v) if ref_v is not None else float("nan")
                nv = float(new_v) if new_v is not None else float("nan")
                eq = (rv == nv) or (rv != rv and nv != nv)
            if not eq:
                mismatches.append((key, f, ref_v, new_v))

    if mismatches:
        raise RuntimeError(
            f"ABORT FASE 4 — la diagnostic re-derivation NO reproduce el baseline congelado "
            f"({len(mismatches)} discrepancias). Primeras: {mismatches[:5]}. "
            f"Protocol v2 seccion 4.b exige identidad exacta en contract_hash + 9 métricas core."
        )

    return contracts, [r for r, _ in pairs], [t for _, t in pairs]


# --------------------------------------------------------------------------- #
# Diagnósticos N1 (TradeRecord) y N2 (MFE/MAE) — NUNCA gates               #
# --------------------------------------------------------------------------- #
def _rebuild_frame_and_entries(contract: dict):
    """Re-deriva el `frame` y las `entries` EXACTAMENTE como lo hace
    `research.runner.run()` internamente (que no los expone). Necesario
    solo para los diagnósticos N2 (MFE/MAE), que exigen recorrer las
    velas sin aplicar ninguna regla de salida.

    Es determinista y reproduce la misma ruta de datos; quien lo use DEBE
    verificar `len(entries) == ExperimentResult.n_entries` (ver
    `compute_mfe_diagnostics`) — esa igualdad es la prueba de que se está
    midiendo sobre el MISMO universo que ejecutó el runner, no una
    aproximación."""
    asset = contract["assets"][0]
    (_role, year), = contract["years"].items()
    df_full = research.load_asset_year(asset, year)
    cfg = backtest.Config(
        atr_mult=contract["atr_mult"],
        atr_period=contract.get("atr_period", 14),
        max_hold=contract["max_hold"],
        risk=contract["risk"],
        sessions=runner.SESSION_WINDOWS[contract["session"]],
    )
    frame = research.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = research.find_entries(
        frame, cfg, contract["trigger"]["name"], contract["entry"]["name"],
        trigger_params=contract["trigger"].get("params") or {},
    )
    return frame, entries, cfg


def _mfe_mae_r_for_entry(frame: pd.DataFrame, entry: dict, cfg) -> tuple[float, float]:
    """MFE_R / MAE_R de UNA entrada, sobre la MISMA ventana `max_hold` y
    con la MISMA fórmula de excursión favorable que `simulate_v3`, pero
    SIN aplicar ninguna regla de salida (sin stop, sin BE, sin trailing,
    sin canal, sin timeout anticipado) — de ahí que no se reutilice
    ninguna función de simulación: por diseño esas SÍ cortan la ventana.
    Medición de SOLO LECTURA, posterior, que no altera ningún trade."""
    i0 = entry["entry_idx"]
    direction = entry["direction"]
    e = entry["entry"]
    risk_pts = entry["risk_pts"]

    n = len(frame)
    end = min(i0 + cfg.max_hold + 1, n)
    max_fav = 0.0
    max_adv = 0.0
    for k in range(i0 + 1, end):
        c = frame.iloc[k]
        if direction == "long":
            fav = c["high"] - e
            adv = e - c["low"]
        else:
            fav = e - c["low"]
            adv = c["high"] - e
        if fav > max_fav:
            max_fav = fav
        if adv > max_adv:
            max_adv = adv
    return max_fav / risk_pts, max_adv / risk_pts


def compute_diagnostics(contract: dict, result, trades: list, origin: str) -> dict:
    """Diagnósticos N1 + N2 de UNA observación (asset x management x year).

    N1 (sin ningún cambio a C1-C8, desde `TradeRecord`): avg_win,
    avg_loss, mean_duration_h, fill_rate, desglose de `reason`.
    N2 (instrumentación nueva, read-only): mean MFE_R, mean MAE_R y
    MFE_capture_ratio = mean(pnl_r / MFE_R) SOLO sobre ganadores.

    `MFE_capture_ratio` compara un `pnl_r` NETO de costos contra un MFE_R
    BRUTO — asimetría declarada y ACEPTADA: se calcula de forma idéntica
    para tratamiento y controles, así que la comparación entre mecanismos
    (que es su único uso) permanece homogénea.

    NINGUNA de estas magnitudes es gate, ni entra en C5, ni en la
    promoción."""
    pnl = [t.pnl_r for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    durations = [t.duration_h for t in trades]
    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1

    frame, entries, cfg = _rebuild_frame_and_entries(contract)
    if len(entries) != result.n_entries:
        raise RuntimeError(
            f"ABORT — la re-derivación del frame para diagnósticos N2 produce "
            f"{len(entries)} entradas pero ExperimentResult.n_entries={result.n_entries} "
            f"({result.asset}/{result.period}/{result.management}): no se está midiendo "
            f"sobre el mismo universo. Protocol v2 seccion 11 exige esta verificación."
        )

    entry_by_time = {frame.index[e["entry_idx"]]: e for e in entries}
    mfes, maes, capture = [], [], []
    for t in trades:
        ent = entry_by_time.get(t.entry_time)
        if ent is None:
            continue
        mfe_r, mae_r = _mfe_mae_r_for_entry(frame, ent, cfg)
        mfes.append(mfe_r)
        maes.append(mae_r)
        if t.pnl_r > 0 and mfe_r > 0:
            capture.append(t.pnl_r / mfe_r)

    def _mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "origin": origin,
        "asset": result.asset,
        "period": result.period,
        "period_role": result.period_role,
        "management": result.management,
        "contract_hash": result.contract_hash,
        "n_entries": result.n_entries,
        "n_trades": result.n_trades,
        "fill_rate": round(result.n_trades / result.n_entries, 4) if result.n_entries else None,
        "avg_win": _mean(wins),
        "avg_loss": _mean(losses),
        "mean_duration_h": _mean(durations),
        "mean_mfe_r": _mean(mfes),
        "mean_mae_r": _mean(maes),
        "mfe_capture_ratio": _mean(capture),
        "reason_breakdown": ";".join(f"{k}={v}" for k, v in sorted(reasons.items())),
    }


# --------------------------------------------------------------------------- #
# Capa 2 — DECISIÓN (C5, sin modificar) sobre las 18 observaciones          #
# --------------------------------------------------------------------------- #
def decide(all_18: list):
    """C5 invocada UNA SOLA VEZ sobre las 18 observaciones (12 controles
    rehidratados + 6 de tratamiento). `management` es campo real de
    `ExperimentResult`, así que `candidate_fields=("management",)` agrupa
    directamente, sin ningún reetiquetado. `research/decision.py` NO se
    modifica."""
    if len(all_18) != 18:
        raise ValueError(f"Se esperaban 18 observaciones para C5 — recibidas {len(all_18)}.")
    return summarize_decision(
        all_18, candidate_fields=("management",),
        required_roles=("train", "validate"), rank_by_role="validate",
    )


# --------------------------------------------------------------------------- #
# Capa 3 — PROMOCIÓN (externa a C5)                                         #
# --------------------------------------------------------------------------- #
def promotion_summary(decisions: list) -> pd.DataFrame:
    """Regla PRE-REGISTRADA >= 2/3 activos, aplicada IDÉNTICAMENTE a
    V3-A, V3-B y DCH-EXIT. Solo cuenta decisiones ya tomadas por C5 —
    nunca accede a ningún gate individual ni lo reinterpreta."""
    rows = []
    for mgmt in ALL_MANAGEMENTS:
        surviving = [d.asset for d in decisions
                      if d.candidate[0] == mgmt and d.survives_required_roles]
        rows.append({
            "management": mgmt,
            "assets_surviving": len(surviving),
            "assets_total": 3,
            "surviving_assets": ", ".join(sorted(surviving)) or "(ninguno)",
            "promoted": len(surviving) >= PROMOTION_MIN_ASSETS,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Artifacts (Protocol v2 seccion 19)                                         #
# --------------------------------------------------------------------------- #
_COMPARISON_COLUMNS = (
    "source", "source_artifact", "contract_hash", "asset", "period",
    "period_role", "management",
) + CORE_METRICS


def build_comparison_rows(frozen_controls: list, treatment_results: list) -> list[dict]:
    """Las 18 observaciones con PROVENANCE explícita. Las 9 métricas core
    se COPIAN VERBATIM del objeto de origen — las de control provienen del
    artifact congelado (rehidratado por C8, `contract_hash` intacto) y
    NUNCA se recalculan."""
    rows = []
    for r in frozen_controls:
        rows.append({
            "source": "phase1_baseline_frozen", "source_artifact": BASELINE_RESULTS_PATH,
            "contract_hash": r.contract_hash, "asset": r.asset, "period": r.period,
            "period_role": r.period_role, "management": r.management,
            **{f: getattr(r, f) for f in CORE_METRICS},
        })
    for r in treatment_results:
        rows.append({
            "source": "phase4_new", "source_artifact": RESULTS_PATH,
            "contract_hash": r.contract_hash, "asset": r.asset, "period": r.period,
            "period_role": r.period_role, "management": r.management,
            **{f: getattr(r, f) for f in CORE_METRICS},
        })
    return rows


def _write_csv(path: str, rows: list[dict], columns: tuple[str, ...]) -> None:
    """Escritor mínimo para los artifacts NO canónicos (comparison /
    diagnostics), que por diseño quedan fuera del esquema fijo de C6.
    C6 no se modifica."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columns))
        w.writeheader()
        for row in rows:
            w.writerow(row)


_DIAGNOSTIC_COLUMNS = (
    "origin", "asset", "period", "period_role", "management", "contract_hash",
    "n_entries", "n_trades", "fill_rate", "avg_win", "avg_loss", "mean_duration_h",
    "mean_mfe_r", "mean_mae_r", "mfe_capture_ratio", "reason_breakdown",
)


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def print_comparison(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    print(f"\n{'='*110}\n  FASE 4 — COMPARACIÓN (18 observaciones: 12 controles congelados + "
          f"6 DCH-EXIT)\n{'='*110}")
    print(df[list(_COMPARISON_COLUMNS)].to_string(index=False))


def print_decision(decisions: list) -> None:
    print(f"\n{'='*110}\n  DECISIÓN — C5 summarize_decision(candidate_fields=('management',), "
          f"required_roles=('train','validate'), rank_by_role='validate')\n{'='*110}")
    rows = [{"asset": d.asset, "management": d.candidate[0],
              "survives_required_roles": d.survives_required_roles,
              "rank_within_asset": d.rank_within_asset} for d in decisions]
    print(pd.DataFrame(rows).to_string(index=False))


def print_promotion(promo: pd.DataFrame) -> None:
    print(f"\n{'='*110}\n  PROMOCIÓN — regla PRE-REGISTRADA >= {PROMOTION_MIN_ASSETS}/3 activos, "
          f"aplicada idénticamente a los 3 managements\n{'='*110}")
    print(promo.to_string(index=False))


def print_diagnostics(rows: list[dict]) -> None:
    print(f"\n{'='*110}\n  DIAGNÓSTICOS DE MECANISMO (N1+N2) — NO SON GATES, no entran en C5 "
          f"ni en la promoción\n{'='*110}")
    print(pd.DataFrame(rows)[list(_DIAGNOSTIC_COLUMNS)].to_string(index=False))


def main() -> None:
    # 1. Controles congelados (sin re-ejecución de campaña).
    frozen_controls = load_frozen_controls()

    # 2. Tratamiento: las 6 celdas, completas, de una sola vez.
    treat_contracts, treat_results, treat_trades = run_treatment()

    # 3. Artifact de resultados: SOLO las 6 filas nuevas (un solo
    #    experiment_name, sin mezcla — Protocol v2 seccion 19.1).
    write_experiment_results_csv(RESULTS_PATH, treat_results)
    print(f"\nResultados DCH-EXIT exportados a {RESULTS_PATH} ({len(treat_results)} filas).")

    # 4. Comparación con provenance (18 observaciones).
    comparison_rows = build_comparison_rows(frozen_controls, treat_results)
    print_comparison(comparison_rows)
    _write_csv(COMPARISON_PATH, comparison_rows, _COMPARISON_COLUMNS)
    print(f"\nComparación exportada a {COMPARISON_PATH} ({len(comparison_rows)} filas).")

    # 5. C5 sobre las 18 + promoción 2/3.
    decisions = decide(list(frozen_controls) + list(treat_results))
    print_decision(decisions)
    write_decision_csv(DECISION_PATH, decisions, candidate_fields=("management",))
    print(f"Decisión exportada a {DECISION_PATH} ({len(decisions)} filas). "
          f"Provenance por join (asset, management) contra {COMPARISON_PATH}.")

    promo = promotion_summary(decisions)
    print_promotion(promo)

    # 6. Diagnósticos de mecanismo, IDÉNTICOS para tratamiento y controles.
    ctrl_contracts, ctrl_results, ctrl_trades = rederive_control_diagnostics()
    diag_rows = []
    for c, r, t in zip(ctrl_contracts, ctrl_results, ctrl_trades):
        diag_rows.append(compute_diagnostics(c, r, t, origin="diagnostic_re_derivation"))
    for c, r, t in zip(treat_contracts, treat_results, treat_trades):
        diag_rows.append(compute_diagnostics(c, r, t, origin="phase4_execution"))
    print_diagnostics(diag_rows)
    _write_csv(DIAGNOSTICS_PATH, diag_rows, _DIAGNOSTIC_COLUMNS)
    print(f"\nDiagnósticos exportados a {DIAGNOSTICS_PATH} ({len(diag_rows)} filas) "
          f"-- NO son gates.")


if __name__ == "__main__":
    main()
