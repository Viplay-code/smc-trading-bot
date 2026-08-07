#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/trigger_campaign_sweep_bos_session.py — Espacio 3 (post-cierre
I1): revisita el Trigger `A_sweep_bos` bajo la sesión `dcv1_activo_15h`,
bajo Bias=A/Entry=C_market_close/Gestión V3-A (be=1.0R/activation=2.0R/
distance=1.0R)/atr_mult=1.5 fijos — misma configuración exacta que ya usó
`scripts/trigger_campaign.py` para su fila `A_sweep_bos` publicada, con
sesión como única variable libre. Contrato acordado 2026-08-07.

Contexto: `trigger_campaign.py` (commit ya publicado) probó `A_sweep_bos`
únicamente bajo `control_8h` (`backtest.Config()` por defecto) y encontró PF
extremos en 2022 (0.79-4.02 según activo, hasta 106.6 combinando con
`A_pullback_50` en `entry_campaign_sweep_bos.py`) sobre una muestra de 7-12
trades/año, y en 2023 una muestra de apenas 2-4 trades/año — insuficiente
para que `backtest.metrics()` calcule ninguna métrica (`if trades.empty or
len(trades) < 5: return None`, `backtest.py:255`; NO ausencia total de
operaciones, precisión hecha explícita 2026-08-07 tras verificar
`trigger_campaign_results.csv` con cuidado). Nunca se probó si `A_sweep_bos`
produce una muestra evaluable, y si el PF se sostiene, bajo una sesión más
ancha — la celda que este script cierra.

Hipótesis (Espacio 3) a falsificar: bajo Bias=A/Entry=C_market_close/
Gestión V3-A/atr_mult=1.5 fijos, existe al menos un activo donde, bajo la
combinación experimental Trigger=`A_sweep_bos` × sesión `dcv1_activo_15h`,
el candidato supera los 4 gates de FRAMEWORK.md en 2022 Y 2023. Falsificada
si, evaluados los 3 activos, ninguno sobrevive ambos años.

Espacio experimental: una sola variable libre, sesión, 2 niveles —
`control_8h` (rol="control", NO candidato: su resultado ya está publicado
en `trigger_campaign_results.csv`/`entry_campaign_sweep_bos_results.csv`,
ver Fase A) y `dcv1_activo_15h` (rol="candidate", la única celda
experimental). `sin_filtro_24h` queda fuera — ya dominada objetivamente en
la campaña de sesión (excede el techo de 12) bajo `T1_ema_cross`;
reabrirla acá sin razón nueva violaría la disciplina de reutilizar el
conjunto de sesiones ya congelado en I1. No hay "Paso 0" de dominación
Pareto (a diferencia de I1): con un solo nivel candidato, no hay grilla que
podar.

Fijo durante toda la campaña: Bias=A, Trigger=`A_sweep_bos` (variable de
interés de este espacio, no se reabre), Entry=`C_market_close` (fijo —
mismo Entry que la fila `A_sweep_bos` ya publicada de `trigger_campaign.py`,
lo que permite que la fila de control sea comparable exacta contra esa
referencia; ya viene fijo así dentro de `trigger_campaign.
find_entries_for_trigger`, no se parametriza acá), Gestión = V3-A única
(`be`=1.0R/`activation`=2.0R/`distance`=1.0R — NO V3-A y V3-B en paralelo
como corrió originalmente `trigger_campaign.py`: un solo anclaje, mismo
principio que I1, para no introducir una segunda variable libre junto con
sesión), `atr_mult`=1.5 (ancla de H1), `atr_period`=14, `max_hold`=20,
`risk`=0.005, una posición a la vez, datasets dc_v1 canónicos, disciplina
P-3, protocolo 2022 in-sample + 2023 validación + 2024 ciego, modelo de
costos, gates literales de FRAMEWORK.md.

Reglas de contingencia: NO aplican en este espacio. Existían en H2.1-H2.3/
I1 para decidir si extender una grilla continua cuando el resultado era
extremo en un borde; acá la variable es categórica con un solo nivel
candidato ya justificado y un tercer nivel ya descartado por dominación en
otra campaña — no hay borde al que escalar.

Verificaciones de integridad — Fase A obligatoria, SIN rol dual (`control_8h`
no es candidato bajo ninguna definición de este espacio — su resultado ya
está establecido, no se re-evalúa como pregunta abierta; a diferencia de
I1-activation/I1-be, donde el ancla era simultáneamente control y candidato
no-dominado del Paso 0). Para cada uno de los 6 combos (activo, año), la
fila `control_8h` calculada acá se compara EXACTO contra DOS referencias
independientes que ya coinciden entre sí (verificado antes de escribir este
script — 0 mismatches sobre 6 combos × 7 campos comparables — no es una
expectativa sin comprobar):
  - `trigger_campaign_results.csv` (candidate="A_sweep_bos",
    exit_config="V3-A (1R/2R/1R)")
  - `entry_campaign_sweep_bos_results.csv` (candidate="C_market_close",
    exit_config="V3-A (1R/2R/1R)")
12 verificaciones totales (6 combos × 2 referencias). Si CUALQUIERA falla,
`AssertionError` inmediato — la corrida completa aborta antes de calcular
la fila experimental. Campos verificados: SOLO los que existen en ambas
referencias históricas (`n_entries`, `n_trades`, `pf`, `wr`, `exp_r`,
`max_dd`, `freq`) — NO `avg_win`/`avg_loss` (no forman parte de esas
referencias, se agregaron recién en H2/I1; sí se exportan en el CSV nuevo
de esta campaña, solo no se verifican contra el histórico). Comparación
`NaN`-consciente: los 3 combos de 2023 tienen referencia `NaN` en
`pf`/`wr`/`exp_r`/`max_dd`/`freq` (por el piso de `metrics()`, no por
ausencia de trades — `n_entries`/`n_trades` SÍ deben coincidir exacto, sean
2, 4 o 12) — `NaN` contra `NaN` cuenta como coincidencia, no como
mismatch; una comparación con `!=` ingenua fallaría siempre en esos 3
combos aunque el mecanismo sea correcto.

Riesgos metodológicos específicos (ver contrato 2026-08-07 para el detalle
completo): la sesión ancha puede resolver computabilidad (≥5 trades) sin
resolver el gate de frecuencia (72-144/año) — un resultado "medible pero
insuficiente" distinto de "sigue sin ser medible"; el reporte distingue
ambos casos explícitamente (`metrics=None` vs `gate_pass=False` con
métricas calculadas) en vez de colapsarlos en un solo "no gate_pass". El
poder estadístico de cualquier resultado acá es menor que el de I1 (decenas
de trades por celda vs un orden de magnitud de 30-50/año en el mejor
escenario) y debe interpretarse con esa salvedad.

Impacto esperado (resumen — ver contrato para el detalle completo): si se
respalda, reabre Capa 2 (Trigger deja de estar cerrado en `T1_ema_cross`) y
la transferibilidad de las anclas de Gestión calibradas bajo `T1_ema_cross`
queda en duda, no se hereda automáticamente. Si se falsifica con muestra ya
computable, la evidencia fortalece la elección actual de `T1_ema_cross`
como trigger de trabajo al reducir significativamente la incertidumbre
sobre `A_sweep_bos`, sin demostrar por sí sola que sea el trigger óptimo.
Si se falsifica sin resolver computabilidad, cierra el espacio igual pero
de forma más débil respecto de la duda original sobre los PF de 2022.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year` (Bias=A ya aplicado),
`find_entries_for_trigger` (Entry=C_market_close ya fijo adentro). De
scripts/gestion_campaign_session.py — `SESSION_WINDOWS` (las 2 ventanas
usadas acá, reutilizadas directamente, no re-declaradas).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_trigger_campaign_sweep_bos_session.py. Las referencias
históricas (`trigger_campaign_results.csv`/`entry_campaign_sweep_bos_
results.csv`) SÍ están disponibles en este sandbox y su consistencia mutua
se verifica con datos reales en esos tests, aunque la corrida completa de
Fase A+B no pueda ejercitarse sin `data/raw/`.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/trigger_campaign_sweep_bos_session.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/trigger_campaign_sweep_bos_session.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse
import math

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
DISTANCE_ANCHOR = 1.0    # V3-A, congelado
ATR_MULT_ANCHOR = 1.5    # ancla de H1, congelado
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

TRIGGER_CANDIDATE = "A_sweep_bos"
BIAS_CANDIDATE = "A"

SESSION_CONTROL = "control_8h"
SESSION_CANDIDATE = "dcv1_activo_15h"
SESSION_WINDOWS = {
    label: session_camp.SESSION_WINDOWS[label] for label in (SESSION_CONTROL, SESSION_CANDIDATE)
}

# Un solo nivel candidato — a diferencia de I1, esta campaña no tiene una
# grilla que podar (ver docstring del módulo, "Espacio experimental").
CANDIDATES = (SESSION_CANDIDATE,)
EXIT_CONFIG_LABEL = "Espacio 3 — A_sweep_bos (V3-A anchor: be=1.0R/activation=2.0R/distance=1.0R, session variable)"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

_TRIGGER_REF_PATH = "trigger_campaign_results.csv"
_TRIGGER_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_ENTRY_REF_PATH = "entry_campaign_sweep_bos_results.csv"
_ENTRY_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
# Solo campos presentes en AMBAS referencias históricas — NO avg_win/avg_loss
# (se agregaron recién en H2/I1, no existen en estos dos CSV).
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


def _eq_or_both_nan(a, b) -> bool:
    """Compara dos valores tratando NaN==NaN como coincidencia — necesario
    porque las 3 filas de 2023 tienen referencia NaN por el piso de
    `backtest.metrics()` (n_trades<5 -> None), no por ausencia de trades."""
    a_nan = a is None or (isinstance(a, float) and math.isnan(a))
    b_nan = b is None or (isinstance(b, float) and math.isnan(b))
    if a_nan and b_nan:
        return True
    if a_nan != b_nan:
        return False
    return a == b


# --------------------------------------------------------------------------- #
# Orquestación por sesión                                                     #
# --------------------------------------------------------------------------- #
def _entries_for_session(asset: str, year: int, session_label: str):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, sessions=SESSION_WINDOWS[session_label])
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
    return frame, cfg, entries


def _run(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict]) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, session_label: str, entries: list[dict],
         trades: pd.DataFrame, m: dict | None, role: str) -> dict:
    return {
        "asset": asset, "year": year, "role": role, "session": session_label,
        "candidate": session_label, "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad contra DOS referencias ya publicadas    #
# que ya coinciden entre sí (12 verificaciones: 6 combos x 2 referencias)     #
# --------------------------------------------------------------------------- #
def _trigger_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_TRIGGER_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == TRIGGER_CANDIDATE)
               & (df["exit_config"] == _TRIGGER_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/"
            f"{TRIGGER_CANDIDATE} en {_TRIGGER_REF_PATH} — no se puede "
            f"verificar la Fase A."
        )
    return match.iloc[0]


def _entry_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_ENTRY_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == "C_market_close")
               & (df["exit_config"] == _ENTRY_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para {asset}/{year}/"
            f"C_market_close en {_ENTRY_REF_PATH} — no se puede verificar "
            f"la Fase A."
        )
    return match.iloc[0]


def _verify_against(n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series, context: str) -> None:
    mismatches = []
    if n_entries != ref_row["n_entries"]:
        mismatches.append(f"n_entries: actual={n_entries!r} vs esperado={ref_row['n_entries']!r}")
    if n_trades != ref_row["n_trades"]:
        mismatches.append(f"n_trades: actual={n_trades!r} vs esperado={ref_row['n_trades']!r}")
    for field in _CHECK_FIELDS:
        actual = m.get(field) if m else None
        expected = ref_row[field]
        if not _eq_or_both_nan(actual, expected):
            mismatches.append(f"{field}: actual={actual!r} vs esperado={expected!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad) falló en {context}: "
            f"{'; '.join(mismatches)} — el mecanismo de variación de sesión "
            f"para A_sweep_bos no reproduce un resultado histórico ya "
            f"publicado. Corrida abortada antes de calcular cualquier "
            f"resultado de la Fase B."
        )


def run_control_row(asset: str, year: int) -> dict:
    """Corre la única fila de control (role='control', session='control_8h')
    para un (activo, año)."""
    frame, cfg, entries = _entries_for_session(asset, year, SESSION_CONTROL)
    trades, m = _run(frame, cfg, entries)
    return _row(asset, year, SESSION_CONTROL, entries, trades, m, role="control")


def run_control_checks(asset: str, year: int) -> dict:
    """Fase A para un (activo, año) — 2 de las 12 verificaciones totales de
    la campaña. Corre y devuelve la fila de control tras verificarla
    exitosamente contra las dos referencias históricas ya publicadas.
    Revienta con AssertionError (sin devolver nada parcial) si cualquiera de
    las 2 verificaciones falla."""
    row = run_control_row(asset, year)

    ref_trigger = _trigger_reference(asset, year)
    _verify_against(row["n_entries"], row["n_trades"], row["metrics"], ref_trigger,
                     f"{asset}/{year} control_8h vs {_TRIGGER_REF_PATH}")

    ref_entry = _entry_reference(asset, year)
    _verify_against(row["n_entries"], row["n_trades"], row["metrics"], ref_entry,
                     f"{asset}/{year} control_8h vs {_ENTRY_REF_PATH}")

    return row


# --------------------------------------------------------------------------- #
# Fase B — barrido experimental (solo tras Fase A completa sin excepción)     #
# --------------------------------------------------------------------------- #
def run_asset_year_experimental(asset: str, year: int) -> dict:
    frame, cfg, entries = _entries_for_session(asset, year, SESSION_CANDIDATE)
    trades, m = _run(frame, cfg, entries)
    return _row(asset, year, SESSION_CANDIDATE, entries, trades, m, role="candidate")


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
            control_rows.append(run_control_checks(asset, year))  # Fase A — aborta acá si falla

    experimental_rows: list[dict] = []
    for year in years:
        for asset in assets:
            experimental_rows.append(run_asset_year_experimental(asset, year))  # Fase B

    return control_rows + experimental_rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` == "dcv1_activo_15h" (el
    único nivel candidato de este espacio) ya congelado tras decidir con
    2022+2023. No corre Fase A acá (exclusiva de la fase 2022+2023, mismo
    criterio que en H1-H2.3/I1)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_session(asset, BLIND_YEAR, candidate)
        trades, m = _run(frame, cfg, entries)
        results.append(_row(asset, BLIND_YEAR, candidate, entries, trades, m, role="candidate"))
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
            "gate_pass": r["gate_pass"], "metrics_computable": r["metrics"] is not None,
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 3 — A_sweep_bos bajo control_8h (control) vs dcv1_activo_15h "
          f"(candidato)\n  Bias=A/Entry=C_market_close/Gestión V3-A/atr_mult=1.5 fijos\n{'='*100}")
    cols = ["asset", "year", "role", "session", "n_entries", "n_trades", "metrics_computable",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]

    control = df[df["role"] == "control"]
    print(f"\n{'-'*100}\n  Fase A — fila de control (integridad verificada OK contra trigger_campaign "
          f"y entry_campaign_sweep_bos):\n{'-'*100}")
    print(control[cols].to_string(index=False) if not control.empty else "  (sin fila de control)")

    candidate = df[df["role"] == "candidate"]
    print(f"\n{'-'*100}\n  Fase B — dcv1_activo_15h:\n{'-'*100}")
    print(candidate[cols].to_string(index=False) if not candidate.empty else "  (sin filas experimentales)")

    print(f"\n{'-'*100}\n  Distinción metodológica (ver contrato): filas sin gate_pass por muestra "
          f"insuficiente (metrics_computable=False, n_trades<5) vs filas con métricas ya "
          f"calculadas que no alcanzan los gates:\n{'-'*100}")
    if not candidate.empty:
        not_computable = candidate[~candidate["metrics_computable"]]
        computable_no_gate = candidate[candidate["metrics_computable"] & ~candidate["gate_pass"]]
        print(f"  metrics_computable=False (n_trades<5): {len(not_computable)}/{len(candidate)} filas")
        print(f"  metrics_computable=True, gate_pass=False: {len(computable_no_gate)}/{len(candidate)} filas")

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
            print(f"\n  {asset}: A_sweep_bos bajo dcv1_activo_15h no demuestra evidencia "
                  f"suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023 — "
                  f"Espacio 3 queda sin evidencia suficiente para este activo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('dcv1_activo_15h') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "trigger_campaign_sweep_bos_session_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        candidates_only = df[df["role"] == "candidate"].reset_index(drop=True)
        decision = summarize_decision(candidates_only)
        print_decision(decision)
        decision_path = "trigger_campaign_sweep_bos_session_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
