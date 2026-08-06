#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/integration_campaign_be.py — Fase de Integración (I1), bloque
`be`: tercera y última prueba conjunta de sesión × un parámetro de Gestión
de la familia H2, bajo Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/
atr_mult=1.5/activation=2.0R/distance=1.0R fijos (anclas V3-A de H2.3 —
NO los hallazgos de H2.1/H2.2, misma regla de no-promoción).

Contexto: sigue a I1-distance (cerrada 2026-08-05, commit `8688020`,
falsificada) e I1-activation (cerrada 2026-08-06, commit `d3930ff`,
falsificada) — en ambas, bajo `dcv1_activo_15h` la frecuencia pasó siempre
pero PF nunca alcanzó 1.50 en una sola fila. Este bloque prueba la misma
pregunta con `be` en vez de `distance`/`activation`, completando el primer
ciclo de la Fase de Integración.

Hipótesis (I1-be) a falsificar: existe al menos una combinación (`be` ∈
conjunto no-dominado del Paso 0, sesión ∈ {control_8h, dcv1_activo_15h})
que, con `activation`=2.0R/`distance`=1.0R fijos en su ancla V3-A, supera
los 4 gates de FRAMEWORK.md en 2022 Y 2023 para al menos un activo.
Falsificada si, evaluado el conjunto candidato completo, ninguna
combinación sobrevive ambos años en ningún activo.

Origen y congelamiento del espacio experimental (Paso 0, 2026-08-04): este
script NO recalcula dominación Pareto — consume exclusivamente
BE_CANDIDATES = {0.25, 0.5, 1.0, 1.5, 2.0}, los 5 valores probados en
H2.3, SIN PODA (ninguno quedó dominado en todos los contextos — misma
situación que `activation`, distinta de `distance`). Cualquier cambio
futuro exige repetir formalmente el Paso 0 y aprobar un nuevo contrato.

Rol dual del ancla (`be`=1.0): mismo diseño metodológico ya validado en
I1-activation — como `be`=1.0 SÍ integra el conjunto no-dominado (a
diferencia de `distance`=1.0 en I1-distance), se computa DOS VECES dentro
de la misma corrida: una vez como control (Fase A) y una vez como
candidato normal dentro del barrido de la Fase B (participa en
CANDIDATES/summarize_decision()/--blind igual que cualquier otro valor).
Excluirlo de la Fase B habría introducido un criterio de exclusión ajeno a
la dominación Pareto del Paso 0. `verify_anchor_dual_role` (idéntica a la
de I1-activation, sin modificar su lógica) exige que la fila role='control'
de be=1.0 y su fila role='candidate' equivalente (misma sesión) coincidan
EXACTO en TODAS las métricas que la campaña publica (pf, wr, exp_r,
avg_win, avg_loss, total_r, max_dd, freq, be, reason_stop, reason_timeout,
n_entries, n_trades) — no solo en el resultado final — porque ambas filas
son, por construcción, la misma computación alcanzada por dos caminos de
código distintos.

Orden de ejecución OBLIGATORIO dentro de la corrida 2022+2023 (Fase 1+2,
no confundir con la Fase 3/blind de 2024, que no corre ninguna
verificación):
  - Fase A (verificación de integridad, 12 verificaciones independientes
    en total): para las 6 combinaciones (activo, año), corre las 2 filas
    de control (`be`=1.0 bajo control_8h y bajo dcv1_activo_15h) y las
    compara EXACTO (sin tolerancia, mismo redondeo determinístico de
    backtest.metrics()) contra:
      * control_8h + be=1.0 -> gestion_campaign_be_results.csv (fila
        candidate=1.0, exit_config="H2.3 anchor (activation=2.0R/
        distance=1.0R, be variable)", ya publicada, H2.3) — 6
        verificaciones, una por (activo, año).
      * dcv1_activo_15h + be=1.0 -> gestion_campaign_session_results.csv
        (fila candidate="dcv1_activo_15h", exit_config="V3-A (1R/2R/1R)",
        ya publicada — MISMA referencia que usaron I1-distance e
        I1-activation, porque el paquete V3-A completo be=1.0/
        activation=2.0/distance=1.0 es el mismo ancla en los tres
        bloques) — 6 verificaciones más, una por (activo, año).
    Si CUALQUIERA de las 12 comparaciones falla, `AssertionError`
    inmediato — la corrida completa aborta antes de calcular una sola
    fila experimental.
  - Fase B (barrido experimental): arranca SOLO si la Fase A completa sin
    excepción para las 6 combinaciones (activo, año). Evalúa las 10
    combinaciones candidatas (`be` x sesión) por activo/año (incluye
    be=1.0 x 2 sesiones, por su rol dual). Tras calcularse,
    `verify_anchor_dual_role` compara esas filas contra las de control ya
    verificadas en la Fase A; cualquier mismatch también aborta antes de
    exportar resultados.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross, Entry=
C_market_close, `atr_mult`=1.5 (ancla H1), `activation`=2.0R/`distance`=
1.0R (anclas V3-A de H2.3 — NO los hallazgos de H2.1/H2.2), `atr_period`=
14, `max_hold`=20, `risk`=0.005, una posición a la vez, datasets dc_v1
canónicos, disciplina P-3, modelo de costos, gates literales de
FRAMEWORK.md, 2024 ciego.

Estructura de datos y criterio de decisión — igual que I1-distance/
I1-activation: `candidate` = f"{be} | {session_label}" para que
`summarize_decision()` (reutilizada SIN modificar) no mezcle sesiones
distintas bajo el mismo `be`. `summarize_decision()` opera EXCLUSIVAMENTE
sobre filas `role="candidate"` — `role="control"` existe únicamente para
la verificación de integridad de la Fase A (y la verificación de rol
dual) y nunca se pasa a esa función, nunca aparece en `CANDIDATES`, nunca
es elegible para `--blind`.

Nota de prudencia metodológica (2026-08-06): si, al cerrar esta campaña,
ninguna combinación supera los 4 gates — como ya ocurrió en I1-distance e
I1-activation — eso sería evidencia acumulada consistente con que ajustar
un único parámetro de Gestión junto con la sesión no basta para cerrar la
brecha de PF. Es una hipótesis respaldada por la evidencia, no una
conclusión de este contrato ni de este script: cualquier decisión sobre
hacia dónde redirigir el espacio de búsqueda del proyecto (Capa 1/2,
combinaciones de más de un parámetro, u otra dirección) corresponde al
cierre integrado de la Fase I1 completa (los tres bloques juntos), no a
este bloque en solitario.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
De scripts/gestion_campaign_session.py — `SESSION_WINDOWS`.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_integration_campaign_be.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/integration_campaign_be.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/integration_campaign_be.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
ACTIVATION_ANCHOR = 2.0  # V3-A / ancla de H2.3, congelado — NO el hallazgo de H2.2
DISTANCE_ANCHOR = 1.0    # V3-A / ancla de H2.3, congelado — NO el hallazgo de H2.1
ATR_MULT_ANCHOR = 1.5    # ancla de H1, congelado
BE_ANCHOR = 1.0           # V3-A — control de integridad Y candidato (rol dual)

# Congelado por el Paso 0 (2026-08-04) — dominación Pareto sobre
# gestion_campaign_be_results.csv. SIN poda: los 5 valores probados en
# H2.3 sobreviven. Este script NO recalcula dominación.
BE_CANDIDATES = (0.25, 0.5, 1.0, 1.5, 2.0)

SESSION_LABELS = ("control_8h", "dcv1_activo_15h")
SESSION_WINDOWS = {label: session_camp.SESSION_WINDOWS[label] for label in SESSION_LABELS}

CANDIDATES = tuple(
    f"{b} | {s}" for b in BE_CANDIDATES for s in SESSION_LABELS
)
EXIT_CONFIG_LABEL = "I1-be (activation=2.0R/distance=1.0R, be & session variable)"

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

_H23_REF_PATH = "gestion_campaign_be_results.csv"
_H23_EXIT_CONFIG = "H2.3 anchor (activation=2.0R/distance=1.0R, be variable)"
_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "avg_win", "avg_loss", "max_dd", "freq")
# Campos completos para la verificación de rol dual (más estricta que la
# verificación contra histórico: toda métrica publicada, no un subconjunto).
_FULL_FIELDS = ("pf", "wr", "exp_r", "avg_win", "avg_loss", "total_r", "max_dd",
                 "freq", "be", "reason_stop", "reason_timeout", "n_entries", "n_trades")


def _label(be: float, session_label: str) -> str:
    return f"{be} | {session_label}"


def _exit_cfg(be: float) -> dict:
    return {"be": be, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}


# --------------------------------------------------------------------------- #
# Orquestación por sesión                                                     #
# --------------------------------------------------------------------------- #
def _entries_for_session(asset: str, year: int, session_label: str):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, sessions=SESSION_WINDOWS[session_label])
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    return frame, cfg, entries


def _run_be(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
            be: float) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, _exit_cfg(be), cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, be: float, session_label: str,
          entries: list[dict], trades: pd.DataFrame, m: dict | None, role: str) -> dict:
    return {
        "asset": asset, "year": year, "role": role, "session": session_label,
        "candidate": _label(be, session_label), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


def _full_row_fields(row: dict) -> dict:
    m = row["metrics"] or {}
    reasons = m.get("reasons") or {}
    return {
        "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
        "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
        "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": m.get("freq"),
        "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
        "reason_timeout": reasons.get("timeout", 0),
        "n_entries": row["n_entries"], "n_trades": row["n_trades"],
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad contra resultados ya publicados         #
# (12 verificaciones independientes: 6 contra gestion_campaign_be_           #
# results.csv + 6 contra gestion_campaign_session_results.csv)               #
# --------------------------------------------------------------------------- #
def _h23_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_H23_REF_PATH)
    df["candidate_f"] = df["candidate"].astype(float)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate_f"] == BE_ANCHOR)
               & (df["exit_config"] == _H23_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia H2.3 para {asset}/{year}/be="
            f"{BE_ANCHOR} en {_H23_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "dcv1_activo_15h")
               & (df["exit_config"] == "V3-A (1R/2R/1R)")]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia de sesión para {asset}/{year}/"
            f"dcv1_activo_15h/V3-A en {_SESSION_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(m: dict | None, n_trades: int, ref_row: pd.Series, context: str) -> None:
    mismatches = []
    for field in _CHECK_FIELDS:
        actual = m.get(field) if m else None
        expected = ref_row[field]
        if actual != expected:
            mismatches.append(f"{field}: actual={actual!r} vs esperado={expected!r}")
    if n_trades != ref_row["n_trades"]:
        mismatches.append(f"n_trades: actual={n_trades} vs esperado={ref_row['n_trades']}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad) falló en {context}: "
            f"{'; '.join(mismatches)} — el mecanismo de variación de sesión no "
            f"reproduce un resultado histórico ya publicado. Corrida abortada antes "
            f"de calcular cualquier resultado de la Fase B."
        )


def run_control_rows(asset: str, year: int) -> list[dict]:
    """Corre las 2 filas de control (role='control') para un (activo, año),
    una por sesión, con be=BE_ANCHOR."""
    rows = []
    for session_label in SESSION_LABELS:
        frame, cfg, entries = _entries_for_session(asset, year, session_label)
        trades, m = _run_be(frame, cfg, entries, BE_ANCHOR)
        rows.append(_row(asset, year, BE_ANCHOR, session_label, entries, trades, m, role="control"))
    return rows


def run_control_checks(asset: str, year: int) -> list[dict]:
    """Fase A para un (activo, año) — 2 de las 12 verificaciones totales de
    la campaña. Corre y devuelve las 2 filas de control tras verificarlas
    exitosamente contra los CSV históricos ya publicados (H2.3 y campaña de
    sesión). Revienta con AssertionError (sin devolver nada parcial) si
    cualquiera de las 2 verificaciones falla."""
    rows = run_control_rows(asset, year)
    row_c8 = next(r for r in rows if r["session"] == "control_8h")
    row_15 = next(r for r in rows if r["session"] == "dcv1_activo_15h")

    ref_h23 = _h23_reference(asset, year)
    _verify_against(row_c8["metrics"], row_c8["n_trades"], ref_h23,
                     f"{asset}/{year} control_8h vs H2.3 ({_H23_REF_PATH})")

    ref_sess = _session_reference(asset, year)
    _verify_against(row_15["metrics"], row_15["n_trades"], ref_sess,
                     f"{asset}/{year} dcv1_activo_15h vs campaña de sesión ({_SESSION_REF_PATH})")

    return rows


# --------------------------------------------------------------------------- #
# Fase B — barrido experimental (solo tras Fase A completa sin excepción)     #
# --------------------------------------------------------------------------- #
def run_asset_year_experimental(asset: str, year: int) -> list[dict]:
    rows = []
    for session_label in SESSION_LABELS:
        frame, cfg, entries = _entries_for_session(asset, year, session_label)
        for be in BE_CANDIDATES:
            trades, m = _run_be(frame, cfg, entries, be)
            rows.append(_row(asset, year, be, session_label, entries, trades, m, role="candidate"))
    return rows


def verify_anchor_dual_role(control_rows: list[dict], experimental_rows: list[dict]) -> None:
    """Verifica que, para cada (activo, año, sesión), la fila role='control'
    de be=BE_ANCHOR coincida EXACTO en TODOS los campos publicados
    (_FULL_FIELDS, no solo pf/gate_pass) con su fila role='candidate'
    equivalente generada en la Fase B — ambas son, por construcción, la
    misma computación alcanzada por caminos de código distintos. Cualquier
    divergencia revienta con AssertionError."""
    anchor_label_by_session = {s: _label(BE_ANCHOR, s) for s in SESSION_LABELS}
    exp_by_key = {(r["asset"], r["year"], r["candidate"]): r for r in experimental_rows}

    for ctrl in control_rows:
        key = (ctrl["asset"], ctrl["year"], anchor_label_by_session[ctrl["session"]])
        cand = exp_by_key.get(key)
        if cand is None:
            raise AssertionError(
                f"Verificación de rol dual: no se encontró la fila candidata "
                f"equivalente a {key} generada por la Fase B."
            )
        ctrl_fields = _full_row_fields(ctrl)
        cand_fields = _full_row_fields(cand)
        mismatches = [f"{k}: control={ctrl_fields[k]!r} vs candidate={cand_fields[k]!r}"
                      for k in _FULL_FIELDS if ctrl_fields[k] != cand_fields[k]]
        if mismatches:
            raise AssertionError(
                f"Verificación de rol dual falló para {key}: {'; '.join(mismatches)} — "
                f"la fila de control y la fila candidata de be={BE_ANCHOR} deberían "
                f"ser IDÉNTICAS en todos los campos publicados; la divergencia indica "
                f"un bug interno de separación de roles, no un desvío respecto de "
                f"datos históricos."
            )


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Internamente: Fase A completa para las 6
    combinaciones (activo, año) ANTES de que arranque la Fase B; tras la
    Fase B, verify_anchor_dual_role confirma la consistencia interna del
    rol dual del ancla antes de devolver ningún resultado. NO incluye
    2024 — ver run_blind_test."""
    control_rows: list[dict] = []
    for year in years:
        for asset in assets:
            control_rows.extend(run_control_checks(asset, year))  # Fase A — aborta acá si falla

    experimental_rows: list[dict] = []
    for year in years:
        for asset in assets:
            experimental_rows.extend(run_asset_year_experimental(asset, year))  # Fase B

    verify_anchor_dual_role(control_rows, experimental_rows)  # aborta acá si el rol dual diverge

    return control_rows + experimental_rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{be} | {session}") ya congelado tras decidir con 2022+2023. No corre
    Fase A ni verificación de rol dual acá (exclusivas de la fase
    2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    be_str, session_label = (p.strip() for p in candidate.split("|"))
    be = float(be_str)
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_session(asset, BLIND_YEAR, session_label)
        trades, m = _run_be(frame, cfg, entries, be)
        results.append(_row(asset, BLIND_YEAR, be, session_label, entries, trades, m, role="candidate"))
    return results


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        reasons = m.get("reasons") or {}
        freq = m.get("freq")
        n_entries = r["n_entries"]
        n_trades = r["n_trades"]
        months = (n_trades / freq) if freq else None
        entries_per_month = (n_entries / months) if months else None
        fill_rate = (n_trades / n_entries) if n_entries else None
        rows.append({
            "asset": r["asset"], "year": r["year"], "role": r["role"], "session": r["session"],
            "candidate": r["candidate"], "exit_config": r["exit_config"],
            "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  I1 — bloque be: sesión x be bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/activation=2.0R/distance=1.0R fijos\n{'='*100}")
    cols = ["asset", "year", "role", "session", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]

    control = df[df["role"] == "control"]
    print(f"\n{'-'*100}\n  Fase A — filas de control (integridad verificada OK contra H2.3 y campaña de sesión):\n{'-'*100}")
    print(control[cols].to_string(index=False) if not control.empty else "  (sin filas de control)")

    candidate = df[df["role"] == "candidate"]
    print(f"\n{'-'*100}\n  Fase B — barrido experimental (incluye be=1.0 por su rol dual, "
          f"verificado internamente contra la Fase A):\n{'-'*100}")
    print(candidate[cols].to_string(index=False) if not candidate.empty else "  (sin filas experimentales)")

    print(f"\n{'-'*100}\n  Combinaciones candidatas que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = candidate[candidate["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación candidata pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación (be, sesión) en {CANDIDATES} demuestra "
                  f"evidencia suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023 — "
                  f"I1-be queda sin evidencia suficiente para este activo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{be} | {sesión}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "integration_campaign_be_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        candidates_only = df[df["role"] == "candidate"].reset_index(drop=True)
        decision = summarize_decision(candidates_only)
        print_decision(decision)
        decision_path = "integration_campaign_be_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
