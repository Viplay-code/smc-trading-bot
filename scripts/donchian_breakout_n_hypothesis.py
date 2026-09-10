#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/donchian_breakout_n_hypothesis.py — Fase 3: investigación de
`range_lookback` (N) para Donchian Channel Breakout (2026-09-10), diseño
científico pre-registrado y aprobado antes de esta implementación.

HIPÓTESIS H-N: el período N del canal Donchian modifica estructuralmente
la frecuencia y el perfil de retorno de la estrategia, y un N mayor podría
producir un comportamiento más compatible con los gates de FRAMEWORK.md
sin alterar ningún otro elemento del protocolo.

Punto de partida: baseline Donchian N=10 ya congelado (commit `e20d3e24`,
`donchian_breakout_baseline_results.csv`/`_decision.csv`) — 0/12 celdas
pasan gates, freq 18.4-23.8/mes (gate de frecuencia falla en 12/12), PF
máximo observado 1.411. N=10 es CONTROL HISTÓRICO — se usa como referencia
de comparación en el análisis, NUNCA se re-ejecuta acá (su resultado ya
está cerrado y persistido).

ÚNICA VARIABLE EXPERIMENTAL NUEVA: `range_lookback ∈ {20, 55}` — dos
valores, PRE-REGISTRADOS antes de ejecutar cualquier celda, con
justificación EXTERNA al programa (System 1/System 2 del sistema Turtle
clásico — la referencia histórica más citada de la familia Donchian
Breakout/Trend Following), no elegidos por su resultado esperado. Ningún
tercer valor se agrega dentro de esta corrida — ver el diseño de Fase 3
para la justificación completa de por qué 2 valores (no más) son el
mínimo necesario para responder H-N direccionalmente.

Todo lo demás permanece EXACTAMENTE fijo, igual que el baseline N=10:
Bias=A_ema200_neutral, Entry=C_market_close, session=sin_filtro_24h,
Management=V3-A/V3-B (en paralelo, comparadores fijos — NO la variable
bajo prueba, NO se investiga Gestión específica de Donchian en esta fase),
risk=0.005, cost_per_trade=0.0009, max_hold=20, atr_mult=1.5,
atr_period=14, gates canónicos SIN modificar, train=2022/validate=2023.

Usa la capacidad de propagación genérica de `trigger.params` (Fase 2,
commit `490323e`, `research/entries.py`/`research/runner.py`) — cada
contrato declara `trigger.params={"range_lookback": N}`, validado por
`research.runner.validate_contract` (rechaza cualquier clave desconocida
ANTES de tocar datos) y propagado hasta `trigger_D_range_breakout` sin
ninguna ruta especial nueva.

SEPARACIÓN DE CAPAS (exigida explícitamente por el diseño aprobado de
Fase 3, no una elección de implementación libre):

  1. UNIDAD EXPERIMENTAL: asset x N x management x year — una fila de
     `ExperimentResult` por combinación, 24 en total (2 N x 2 managements
     x 3 assets x 2 years). Es lo que `run_hypothesis()` produce.

  2. UNIDAD DE DECISIÓN (C5, SIN MODIFICAR): asset x N x management,
     exige `gate_pass=True` en 2022 Y 2023. `ExperimentResult` no tiene
     ningún campo `range_lookback` (no es parte de su esquema, y este
     componente NO modifica `research/schema.py`) — por eso
     `summarize_decision` (C5) se invoca UNA VEZ POR CADA N por separado
     (`candidate_fields=("management",)`, el único campo real de
     `ExperimentResult` que varía dentro de cada corrida por N), sobre el
     subconjunto de resultados de ESE N — nunca se le pide a C5 agrupar
     por N porque N no es un atributo que C5 pueda leer. El resultado de
     cada llamada se reetiqueta (`candidate=(N, management)`) SOLO para
     fines de reporte/persistencia — la decisión en sí (`survives_
     required_roles`) la sigue calculando C5 exclusivamente, sin
     modificación.

  3. UNIDAD DE PROMOCIÓN A FASE 4 (capa NUEVA, externa a C5, NO parte de
     `research/decision.py`): N x management, agregado sobre los 3
     assets — un `(N, management)` se PROMUEVE si `survives_required_
     roles=True` en >= 2 de los 3 activos (regla 2/3 pre-registrada y
     justificada antes de esta implementación, NO modificable después de
     ver resultados). Esta capa NUNCA toca ni reinterpreta ningún gate
     individual — solo cuenta cuántas decisiones de C5 (ya tomadas, sin
     tocar) dieron `True` para un mismo (N, management).

Artifacts: `donchian_breakout_n_hypothesis_results.csv`/`_decision.csv` —
namespace propio, distinto del baseline (`donchian_breakout_baseline_*.csv`,
Fase 1, NUNCA sobrescrito).

Requiere `data/raw/` poblado.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/donchian_breakout_n_hypothesis.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from dataclasses import replace

import pandas as pd

import research
from research import runner
from research.expand import expand_universe
from research.decision import summarize_decision, CandidateDecision
from research.persistence import (
    write_experiment_results_csv, write_decision_csv, to_experiment_rows,
)
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Alcance experimental de esta fase (ver docstring del módulo)               #
# --------------------------------------------------------------------------- #
IN_SAMPLE_YEAR = 2022
VALIDATION_YEAR = 2023

N_VALUES = (20, 55)
"""Tupla EXPLÍCITA, pre-registrada — System 1/System 2 del sistema Turtle
clásico, justificación externa al programa. NINGÚN valor adicional se
agrega dentro de esta corrida (ver docstring del módulo)."""

BIAS_CANDIDATE = "A_ema200_neutral"
TRIGGER_CANDIDATE = "D_range_breakout"
ENTRY_CANDIDATE = "C_market_close"
SESSION = "sin_filtro_24h"
MANAGEMENTS = ("V3-A", "V3-B")

ATR_MULT = 1.5
ATR_PERIOD = 14
RISK = 0.005
COST_PER_TRADE = 0.0009
MAX_HOLD = 20

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}

# Regla de promoción (unidad de promoción, capa 3 — ver docstring del
# módulo). Pre-registrada, NO modificable después de ver resultados.
PROMOTION_MIN_ASSETS = 2  # de 3 — justificación completa en el diseño de Fase 3

RESULTS_PATH = "donchian_breakout_n_hypothesis_results.csv"
DECISION_PATH = "donchian_breakout_n_hypothesis_decision.csv"


# --------------------------------------------------------------------------- #
# Capa 1 — Unidad experimental: universo canónico (C4) + ejecución (C3)     #
# --------------------------------------------------------------------------- #
def build_universe(
    assets: tuple[str, ...] = ASSETS, years: dict[str, int] | None = None,
    n_values: tuple[int, ...] = N_VALUES, managements: tuple[str, ...] = MANAGEMENTS,
) -> list[dict]:
    """Universo canónico: un template por (N, management), expandido vía
    `research.expand_universe` (C4, assets x years) — `expand_universe` no
    expande `trigger.params`/`management`, así que esas 2 dimensiones se
    recorren acá explícitamente, con listas EXPLÍCITAS (`n_values`,
    `managements`), nunca leyendo un registro genérico."""
    if years is None:
        years = {"train": IN_SAMPLE_YEAR, "validate": VALIDATION_YEAR}
    contracts: list[dict] = []
    for n in n_values:
        for mgmt in managements:
            template = {
                "name": "donchian_breakout_n_hypothesis",
                "contract_version": "1",
                "assets": list(assets),
                "years": dict(years),
                "bias": {"name": BIAS_CANDIDATE, "params": {}},
                "trigger": {"name": TRIGGER_CANDIDATE, "params": {"range_lookback": n}},
                "entry": {"name": ENTRY_CANDIDATE, "params": {}},
                "session": SESSION,
                "management": {"name": mgmt, "params": {}},
                "risk": RISK,
                "cost_per_trade": COST_PER_TRADE,
                "max_hold": MAX_HOLD,
                "atr_mult": ATR_MULT,
                "gates": dict(_CANONICAL_GATES),
                "independent_variable": "trigger.params.range_lookback",
                "blind_authorized": False,
            }
            contracts.extend(expand_universe(template))
    return contracts


def run_hypothesis(assets: tuple[str, ...] = ASSETS) -> tuple[list[dict], list]:
    """Universo completo: 2 N x 2 managements x 3 assets x 2 years = 24
    contratos/resultados. Ejecutados TODOS, sin selección secuencial —
    ningún candidato se descarta después de ver solo 2022 (regla
    pre-registrada de Fase 3, sección 4 del diseño)."""
    contracts = build_universe(assets)
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    results = runner.run_many(contracts)
    return contracts, results


def n_of(contract: dict) -> int:
    """Extrae N de un contrato — único punto de lectura de
    trigger.params.range_lookback en todo el script (evita repetir el
    acceso a la estructura del contrato en cada consumidor)."""
    return contract["trigger"]["params"]["range_lookback"]


# --------------------------------------------------------------------------- #
# Reporte — Capa 1 (unidad experimental), enriquecido con N (que           #
# ExperimentResult NO almacena — ver docstring del módulo) a partir de los  #
# contratos ya conocidos, sin tocar research/schema.py ni C6.               #
# --------------------------------------------------------------------------- #
def results_to_frame(contracts: list[dict], results: list) -> pd.DataFrame:
    df = pd.DataFrame(to_experiment_rows(results))
    df.insert(df.columns.get_loc("trigger") + 1, "range_lookback", [n_of(c) for c in contracts])
    return df


def print_report(df: pd.DataFrame) -> None:
    cols = ["asset", "period", "period_role", "trigger", "range_lookback", "management",
            "n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass"]
    print(f"\n{'='*100}\n  DONCHIAN N-HYPOTHESIS — range_lookback ∈ {{20, 55}} (pre-registrado, H-N), "
          f"Bias=A, Entry=C_market_close, session=sin_filtro_24h (canónico C1-C8)\n{'='*100}")
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"] == True]  # noqa: E712
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


# --------------------------------------------------------------------------- #
# Capa 2 — Unidad de decisión: C5, sin modificar, invocada UNA VEZ POR N.   #
# --------------------------------------------------------------------------- #
def decisions_by_n(contracts: list[dict], results: list) -> dict[int, list[CandidateDecision]]:
    """Para cada N, filtra los resultados de ESE N (vía los contratos, que
    sí conocen N) y llama a `research.summarize_decision` (C5) SIN
    modificarla — `candidate_fields=("management",)`, el único campo real
    de `ExperimentResult` que varía dentro del subconjunto de un N. C5
    nunca sabe que existe una dimensión N — esa separación es deliberada
    (ver docstring del módulo)."""
    out: dict[int, list[CandidateDecision]] = {}
    for n in N_VALUES:
        results_n = [r for c, r in zip(contracts, results) if n_of(c) == n]
        out[n] = summarize_decision(
            results_n, candidate_fields=("management",),
            required_roles=("train", "validate"), rank_by_role="validate",
        )
    return out


def decisions_for_persistence(by_n: dict[int, list[CandidateDecision]]) -> list[CandidateDecision]:
    """Reetiqueta cada CandidateDecision (candidate=(management,)) a
    candidate=(range_lookback, management) SOLO para persistencia/reporte
    — `dataclasses.replace` sobre instancias YA producidas por C5, sin
    alterar cómo C5 calculó `survives_required_roles`/`rank_within_asset`
    (esos campos se copian tal cual, nunca se recalculan acá)."""
    out: list[CandidateDecision] = []
    for n, decisions in by_n.items():
        for d in decisions:
            out.append(replace(d, candidate=(n,) + d.candidate))
    return out


def print_decision(by_n: dict[int, list[CandidateDecision]]) -> None:
    print(f"\n{'='*100}\n  DECISIÓN (C5, por N) — candidate_fields=('management',), "
          f"required_roles=('train','validate'), rank_by_role='validate'\n{'='*100}")
    for n in N_VALUES:
        print(f"\n  -- range_lookback={n} --")
        rows = [{"asset": d.asset, "management": d.candidate[0],
                  "survives_required_roles": d.survives_required_roles,
                  "rank_within_asset": d.rank_within_asset} for d in by_n[n]]
        print(pd.DataFrame(rows).to_string(index=False))


# --------------------------------------------------------------------------- #
# Capa 3 — Unidad de promoción a Fase 4 (NUEVA, externa a C5).              #
# --------------------------------------------------------------------------- #
def promotion_summary(by_n: dict[int, list[CandidateDecision]]) -> pd.DataFrame:
    """Para cada (N, management), cuenta cuántos de los 3 activos
    sobreviven (C5, sin tocar) y aplica la regla de promoción PRE-
    REGISTRADA: >= PROMOTION_MIN_ASSETS (2 de 3). Esta función NUNCA
    accede a ningún gate individual — solo cuenta decisiones ya tomadas
    por C5."""
    rows = []
    for n in N_VALUES:
        for mgmt in MANAGEMENTS:
            surviving_assets = [
                d.asset for d in by_n[n] if d.candidate[0] == mgmt and d.survives_required_roles
            ]
            rows.append({
                "range_lookback": n, "management": mgmt,
                "assets_surviving": len(surviving_assets),
                "assets_total": 3,
                "surviving_assets": ", ".join(sorted(surviving_assets)) or "(ninguno)",
                "promoted": len(surviving_assets) >= PROMOTION_MIN_ASSETS,
            })
    return pd.DataFrame(rows)


def print_promotion_summary(promo: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  PROMOCIÓN A FASE 4 — regla pre-registrada: >= {PROMOTION_MIN_ASSETS}/3 "
          f"activos sobreviven (C5), por (N, management)\n{'='*100}")
    print(promo.to_string(index=False))
    if promo["promoted"].any():
        promoted = promo[promo["promoted"]]
        print(f"\n  PROMOVIDO(S): {len(promoted)} combinación(es) (N, management) cumplen la regla "
              f"2/3 — ver detalle arriba.")
    else:
        print(f"\n  NINGUNA combinación (N, management) cumple la regla de promoción "
              f"(>= {PROMOTION_MIN_ASSETS}/3 activos) — H-N no confirmada con N=20/N=55 bajo "
              f"este protocolo.")


def main() -> None:
    contracts, results = run_hypothesis()

    df = results_to_frame(contracts, results)
    print_report(df)

    write_experiment_results_csv(RESULTS_PATH, results)
    print(f"\nResultados exportados a {RESULTS_PATH} ({len(results)} filas) "
          f"-- nota: range_lookback NO es columna de este artifact (ExperimentResult no lo "
          f"almacena); recuperable vía contract_hash o el reporte de consola de este script.")

    by_n = decisions_by_n(contracts, results)
    print_decision(by_n)

    decisions_persist = decisions_for_persistence(by_n)
    write_decision_csv(DECISION_PATH, decisions_persist, candidate_fields=("range_lookback", "management"))
    print(f"Decisión exportada a {DECISION_PATH} ({len(decisions_persist)} filas).")

    promo = promotion_summary(by_n)
    print_promotion_summary(promo)


if __name__ == "__main__":
    main()
