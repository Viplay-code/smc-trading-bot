#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/integration_campaign_distance.py — Fase de Integración (I1),
bloque `distance`: primera prueba conjunta de sesión × un parámetro de
Gestión de la familia H2, bajo Bias=A/Trigger=T1_ema_cross/Entry=
C_market_close/atr_mult=1.5/be=1.0R/activation=2.0R fijos.

Contexto: las campañas H1/H2.1/H2.2/H2.3 (todas cerradas, ninguna con
sobrevivientes) fijaron sesión=`control_8h` a propósito para aislar cada
variable — pero `control_8h` por sí solo ya garantiza freq<6 (campaña de
sesión, cerrada), independientemente de cómo se calibre Gestión.
Simétricamente, la campaña de sesión probó `dcv1_activo_15h` (única
ventana que mete la frecuencia en [6,12]) solo bajo la Gestión por
defecto (V3-A/V3-B), nunca bajo los valores de `distance` que H2.1
encontró con asociación real de PF. Esa celda — sesión que resuelve
frecuencia × Gestión con evidencia de PF — es la que ningún experimento
anterior tocó. Diseño acordado 2026-08-04 (Paso 0 + contrato I1-distance).

Hipótesis (I1-distance) a falsificar: existe al menos una combinación
(`distance` ∈ conjunto no-dominado del Paso 0, sesión ∈ {control_8h,
dcv1_activo_15h}) que, con `be`=1.0R/`activation`=2.0R fijos en su ancla
V3-A, supera los 4 gates de FRAMEWORK.md en 2022 Y 2023 para al menos un
activo. Falsificada si, evaluado el conjunto candidato completo, ninguna
combinación sobrevive ambos años en ningún activo.

Origen y congelamiento del espacio experimental (Paso 0, 2026-08-04): este
script NO recalcula dominación Pareto — consume exclusivamente
DISTANCE_CANDIDATES = {0.25, 0.5, 1.5}, el conjunto no-dominado ya
calculado sobre gestion_campaign_trailing_distance_results.csv (dominación
Pareto sobre pf/max_dd/exp_r por (activo,año), sin comparar entre activos).
`distance`=1.0 (ancla V3-A) quedó dominado en TODOS los contextos
probados en H2.1 y por eso NO forma parte del espacio experimental — se
mantiene únicamente como control de integridad (ver abajo). Cualquier
cambio futuro a DISTANCE_CANDIDATES exige repetir formalmente el Paso 0 y
aprobar un nuevo contrato — este script no está autorizado a recortar,
ampliar ni recalcular ese conjunto por su cuenta.

Configuración de control de integridad (rol="control", fuera del espacio
experimental): `distance`=1.0 × {control_8h, dcv1_activo_15h}. Nunca
aparece en CANDIDATES, nunca entra al frame que recibe summarize_decision(),
nunca es elegible para --blind — ver `results_to_frame`/`main`.

Orden de ejecución OBLIGATORIO dentro de la corrida 2022+2023 (Fase 1+2,
no confundir con la Fase 3/blind de 2024, que no corre verificación):
  - Fase A (verificación): corre las 2 filas de control para las 6
    combinaciones (activo, año) y las compara EXACTO (sin tolerancia,
    mismo redondeo determinístico de backtest.metrics()) contra:
      * control_8h + distance=1.0 -> gestion_campaign_trailing_distance_
        results.csv (fila candidate=1.0, ya publicada, H2.1)
      * dcv1_activo_15h + distance=1.0 -> gestion_campaign_session_
        results.csv (fila candidate="dcv1_activo_15h",
        exit_config="V3-A (1R/2R/1R)", ya publicada)
    Si CUALQUIERA de las 12 comparaciones (6 combos x 2 verificaciones)
    falla, `AssertionError` inmediato — la corrida completa aborta antes
    de calcular una sola fila experimental. Un mismatch acá indicaría un
    problema potencialmente sistémico en el mecanismo NUEVO de variación
    de `cfg.sessions` (ninguna campaña H1/H2 lo varió antes), no algo
    aislado a un activo.
  - Fase B (barrido experimental): arranca SOLO si la Fase A completa sin
    excepción para las 6 combinaciones (activo, año). Evalúa las 6
    combinaciones candidatas (`distance` x sesión) por activo/año.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross, Entry=
C_market_close, `atr_mult`=1.5 (ancla H1), `be`=1.0R/`activation`=2.0R
(anclas V3-A — NO los hallazgos de H2.2/H2.3, misma regla de no-promoción
ya aplicada en toda la familia H2), `atr_period`=14, `max_hold`=20,
`risk`=0.005, una posición a la vez, datasets dc_v1 canónicos, disciplina
P-3, modelo de costos, gates literales de FRAMEWORK.md, 2024 ciego.

Invarianza estructural: dentro de UNA sesión fija, las entradas no
dependen de `distance` (mismo argumento que H2.1 — `distance` solo actúa
dentro de `simulate_v3`). Pero SÍ dependen de la sesión (`in_session`
filtra qué eventos producen entrada) — a diferencia de H1/H2.1/H2.2/H2.3,
acá las entradas se recalculan una vez por (activo, año, sesión), no una
vez por (activo, año).

Estructura de datos — encaje con `summarize_decision()` sin modificarla:
agrupa por (asset, candidate, exit_config); con sesión ahora variable, el
campo `candidate` codifica AMBAS dimensiones como
f"{distance} | {session_label}" (ej. "0.5 | dcv1_activo_15h") para que el
agrupamiento no mezcle sesiones distintas bajo el mismo `distance`.
`exit_config` se mantiene constante (EXIT_CONFIG_LABEL), mismo patrón que
H2.1/H2.2/H2.3. Columnas nuevas respecto de la familia H2: `role`
("control"/"candidate") y `session`.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
De scripts/gestion_campaign_session.py — `SESSION_WINDOWS` (las 2 ventanas
usadas acá, reutilizadas directamente, no re-declaradas).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_integration_campaign_distance.py. La verificación de
integridad de la Fase A SÍ puede ejercitarse estructuralmente con datos
sintéticos (contra referencias sintéticas construidas a mano), aunque no
reemplaza la verificación real contra los CSV históricos.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/integration_campaign_distance.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/integration_campaign_distance.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
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
BE_ANCHOR = 1.0          # V3-A, congelado
ACTIVATION_ANCHOR = 2.0  # V3-A, congelado
ATR_MULT_ANCHOR = 1.5    # ancla de H1, congelado
DISTANCE_ANCHOR = 1.0    # V3-A — SOLO control de integridad, fuera del espacio experimental

# Congelado por el Paso 0 (2026-08-04) — dominación Pareto sobre
# gestion_campaign_trailing_distance_results.csv. Este script NO recalcula
# dominación; cualquier cambio exige repetir el Paso 0 formalmente.
DISTANCE_CANDIDATES = (0.25, 0.5, 1.5)

SESSION_LABELS = ("control_8h", "dcv1_activo_15h")  # sin_filtro_24h ya descartada (campaña de sesión)
SESSION_WINDOWS = {label: session_camp.SESSION_WINDOWS[label] for label in SESSION_LABELS}

CANDIDATES = tuple(
    f"{d} | {s}" for d in DISTANCE_CANDIDATES for s in SESSION_LABELS
)
EXIT_CONFIG_LABEL = "I1-distance (be=1.0R/activation=2.0R, distance & session variable)"

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

_H21_REF_PATH = "gestion_campaign_trailing_distance_results.csv"
_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "avg_win", "avg_loss", "max_dd", "freq")


def _label(distance: float, session_label: str) -> str:
    return f"{distance} | {session_label}"


def _exit_cfg(distance: float) -> dict:
    return {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": distance}


# --------------------------------------------------------------------------- #
# Orquestación por sesión — entradas dependen de la sesión (invarianza solo   #
# respecto de `distance` dentro de una sesión fija, ver docstring).           #
# --------------------------------------------------------------------------- #
def _entries_for_session(asset: str, year: int, session_label: str):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, sessions=SESSION_WINDOWS[session_label])
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    return frame, cfg, entries


def _run_distance(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
                   distance: float) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, _exit_cfg(distance), cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, distance: float, session_label: str,
          entries: list[dict], trades: pd.DataFrame, m: dict | None, role: str) -> dict:
    return {
        "asset": asset, "year": year, "role": role, "session": session_label,
        "candidate": _label(distance, session_label), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad contra resultados ya publicados         #
# --------------------------------------------------------------------------- #
def _h21_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_H21_REF_PATH)
    df["candidate_f"] = df["candidate"].astype(float)
    match = df[(df["asset"] == asset) & (df["year"] == year) & (df["candidate_f"] == DISTANCE_ANCHOR)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia H2.1 para {asset}/{year}/distance="
            f"{DISTANCE_ANCHOR} en {_H21_REF_PATH} — no se puede verificar la Fase A."
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
    una por sesión, con distance=DISTANCE_ANCHOR."""
    rows = []
    for session_label in SESSION_LABELS:
        frame, cfg, entries = _entries_for_session(asset, year, session_label)
        trades, m = _run_distance(frame, cfg, entries, DISTANCE_ANCHOR)
        rows.append(_row(asset, year, DISTANCE_ANCHOR, session_label, entries, trades, m, role="control"))
    return rows


def run_control_checks(asset: str, year: int) -> list[dict]:
    """Fase A para un (activo, año). Corre y devuelve las 2 filas de control
    tras verificarlas exitosamente contra los CSV históricos ya publicados.
    Revienta con AssertionError (sin devolver nada parcial) si cualquiera de
    las 2 verificaciones falla."""
    rows = run_control_rows(asset, year)
    row_c8 = next(r for r in rows if r["session"] == "control_8h")
    row_15 = next(r for r in rows if r["session"] == "dcv1_activo_15h")

    ref_h21 = _h21_reference(asset, year)
    _verify_against(row_c8["metrics"], row_c8["n_trades"], ref_h21,
                     f"{asset}/{year} control_8h vs H2.1 ({_H21_REF_PATH})")

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
        for distance in DISTANCE_CANDIDATES:
            trades, m = _run_distance(frame, cfg, entries, distance)
            rows.append(_row(asset, year, distance, session_label, entries, trades, m, role="candidate"))
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Internamente: Fase A completa para las 6
    combinaciones (activo, año) ANTES de que arranque la Fase B — si
    run_control_checks revienta en cualquier combinación, la excepción se
    propaga acá y la función nunca llega a calcular una sola fila
    experimental. NO incluye 2024 — ver run_blind_test."""
    control_rows: list[dict] = []
    for year in years:
        for asset in assets:
            control_rows.extend(run_control_checks(asset, year))  # Fase A — aborta acá si falla

    experimental_rows: list[dict] = []
    for year in years:
        for asset in assets:
            experimental_rows.extend(run_asset_year_experimental(asset, year))  # Fase B

    return control_rows + experimental_rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{distance} | {session}", ej. "0.5 | dcv1_activo_15h") ya congelado tras
    decidir con 2022+2023. No corre Fase A acá (exclusiva de la fase
    2022+2023, mismo criterio que "sin reglas de contingencia" en H1-H2.3)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    distance_str, session_label = (p.strip() for p in candidate.split("|"))
    distance = float(distance_str)
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_session(asset, BLIND_YEAR, session_label)
        trades, m = _run_distance(frame, cfg, entries, distance)
        results.append(_row(asset, BLIND_YEAR, distance, session_label, entries, trades, m, role="candidate"))
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
    print(f"\n{'='*100}\n  I1 — bloque distance: sesión x distance bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/be=1.0R/activation=2.0R fijos\n{'='*100}")
    cols = ["asset", "year", "role", "session", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]

    control = df[df["role"] == "control"]
    print(f"\n{'-'*100}\n  Fase A — filas de control (integridad verificada OK, ver Fase A del contrato):\n{'-'*100}")
    print(control[cols].to_string(index=False) if not control.empty else "  (sin filas de control)")

    candidate = df[df["role"] == "candidate"]
    print(f"\n{'-'*100}\n  Fase B — barrido experimental:\n{'-'*100}")
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
            print(f"\n  {asset}: ninguna combinación (distance, sesión) en {CANDIDATES} demuestra "
                  f"evidencia suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023 — "
                  f"I1-distance queda sin evidencia suficiente para este activo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{distance} | {sesión}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "integration_campaign_distance_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        candidates_only = df[df["role"] == "candidate"].reset_index(drop=True)
        decision = summarize_decision(candidates_only)
        print_decision(decision)
        decision_path = "integration_campaign_distance_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
