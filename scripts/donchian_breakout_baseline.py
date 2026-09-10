#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/donchian_breakout_baseline.py — Primer experimento fuera del
universo SMC/legacy: Donchian Channel Breakout / Trend Following, baseline
científico mínimo (2026-09-10, auditoría de readiness C1-C8 aprobada el
mismo día — decisión A: sin modificar el motor canónico).

Pregunta científica ÚNICA de este baseline: ¿un breakout Donchian de 10
períodos (`range_lookback=10`, el default YA EXISTENTE de
`research.layers::trigger_D_range_breakout`, sin ningún sweep de
parámetros), bajo el protocolo ya establecido por el resto del programa
(Bias=`A_ema200_neutral`, Entry=`C_market_close`, sesión
`sin_filtro_24h`, Gestión V3-A/V3-B en paralelo como comparadores fijos,
mismo riesgo/costos/gates/protocolo train-validate que toda campaña previa),
produce evidencia suficiente de edge para justificar una siguiente fase de
investigación? Explícitamente NO responde: cuál es el mejor período
Donchian, la mejor Gestión, ni ninguna combinación de filtros — eso queda
fuera de alcance por diseño (ver auditoría de readiness).

Arquitectura: construido DIRECTAMENTE sobre C1-C8 (`research.expand_universe`
/`research.runner.run_many`/`research.summarize_decision`/
`research.write_experiment_results_csv`/`write_decision_csv`) desde el
inicio — a diferencia de `gestion_campaign_session.py`/`trigger_campaign.py`
(migrados desde una versión legacy previa), este script NO tiene
predecesor legacy: es la primera estrategia nueva escrita directamente
sobre el motor canónico, sin ninguna orquestación manual que reemplazar.
`research.layers::trigger_D_range_breakout` YA ES, por definición, un
Trigger de canal Donchian — máximo/mínimo de las `range_lookback` velas
ANTERIORES a la vela evaluada (la vela de ruptura no se incluye en su
propio rango de referencia); `direction="long"` si el cierre rompe el
máximo, `"short"` si rompe el mínimo — sin mirar bias ni sesión (mismo
principio de composición que el resto de `research.TRIGGER_LAYERS`). Ver
la auditoría de readiness (2026-09-10) para la evidencia completa de por
qué esto no requiere ninguna capa nueva ni modificación de C1-C8.

RESTRICCIÓN ARQUITECTÓNICA DELIBERADA, NO RESUELTA ACÁ (auditoría de
readiness 2026-09-10): `research.entries.find_entries`/`_raw_events` NO
propaga `trigger.params` genéricamente a ningún Trigger salvo
`T1_ema_cross` (que recibe `atr_period`/`atr_mult` derivados de `cfg`, no
de `trigger.params`) — cualquier valor declarado en `trigger.params` para
`D_range_breakout` sería aceptado por `validate_contract` (que no lo
valida) pero IGNORADO EN SILENCIO por `find_entries`, que siempre invoca
el Trigger con su default (`range_lookback=10`). Por eso, en este script,
`trigger.params` se deja deliberadamente vacío (`{}`) — declarar un valor
ahí crearía la apariencia de un parámetro controlado que en realidad no lo
está. Extender esa propagación (para permitir un futuro sweep de
`range_lookback`) es trabajo identificado y explícitamente fuera de
alcance de este baseline — no se resuelve en este script ni se modifica
ningún archivo de C1-C8 para lograrlo.

Universo: 3 assets × 2 años × 2 managements = 12 contratos — un template
por management (V3-A/V3-B), cada uno expandido vía `research.expand_universe`
(assets × years). Sesión, Trigger, Entry, Bias fijos en los 12 contratos.

Gestión: V3-A y V3-B se ejecutan EN PARALELO, exactamente como comparadores
ya establecidos por el protocolo del resto del programa — no son la
variable bajo prueba, y NO se diseña acá ningún mecanismo de salida
específico de Donchian (ej. trailing por canal N/2); ambos usan el mismo
`MANAGEMENT_LAYERS` genérico (ATR-stop + BE + trailing por R-múltiplo) que
ya usa toda campaña SMC del programa.

Artifacts: `donchian_breakout_baseline_results.csv`/
`donchian_breakout_baseline_decision.csv` — namespace propio de esta
familia de estrategia, nunca mezclado con artifacts SMC/legacy.

Requiere `data/raw/` poblado.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/donchian_breakout_baseline.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import pandas as pd

import research
from research import runner
from research.expand import expand_universe
from research.decision import summarize_decision
from research.persistence import (
    write_experiment_results_csv, write_decision_csv, to_experiment_rows,
)
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Alcance experimental de este baseline (ver docstring del módulo)           #
# --------------------------------------------------------------------------- #
IN_SAMPLE_YEAR = 2022
VALIDATION_YEAR = 2023

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

RESULTS_PATH = "donchian_breakout_baseline_results.csv"
DECISION_PATH = "donchian_breakout_baseline_decision.csv"


# --------------------------------------------------------------------------- #
# Universo canónico (C4) + ejecución canónica (C3)                          #
# --------------------------------------------------------------------------- #
def build_universe(
    assets: tuple[str, ...] = ASSETS, years: dict[str, int] | None = None,
    managements: tuple[str, ...] = MANAGEMENTS,
) -> list[dict]:
    """Universo canónico: un template por management, expandido vía
    `research.expand_universe` (C4, assets x years) — `expand_universe` no
    expande `management`, así que esa dimensión se recorre acá
    explícitamente. `trigger.params`/`entry.params` quedan deliberadamente
    vacíos (`{}`) — ver docstring del módulo, restricción arquitectónica
    de propagación de `trigger.params` no resuelta en este baseline."""
    if years is None:
        years = {"train": IN_SAMPLE_YEAR, "validate": VALIDATION_YEAR}
    contracts: list[dict] = []
    for mgmt in managements:
        template = {
            "name": "donchian_breakout_baseline",
            "contract_version": "1",
            "assets": list(assets),
            "years": dict(years),
            "bias": {"name": BIAS_CANDIDATE, "params": {}},
            "trigger": {"name": TRIGGER_CANDIDATE, "params": {}},
            "entry": {"name": ENTRY_CANDIDATE, "params": {}},
            "session": SESSION,
            "management": {"name": mgmt, "params": {}},
            "risk": RISK,
            "cost_per_trade": COST_PER_TRADE,
            "max_hold": MAX_HOLD,
            "atr_mult": ATR_MULT,
            "gates": dict(_CANONICAL_GATES),
            "independent_variable": "trigger",
            "blind_authorized": False,
        }
        contracts.extend(expand_universe(template))
    return contracts


def run_baseline(assets: tuple[str, ...] = ASSETS) -> tuple[list[dict], list]:
    """Universo completo: 3 assets x 2 years x 2 managements = 12
    contratos/resultados. Sin fase --blind: este baseline es
    exclusivamente train+validate (2022+2023) — decidir si corresponde un
    año ciego queda para una fase posterior, condicionada al resultado de
    este baseline."""
    contracts = build_universe(assets)
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    results = runner.run_many(contracts)
    return contracts, results


# --------------------------------------------------------------------------- #
# Reporte — derivado DIRECTAMENTE de ExperimentResult (C3)                  #
# --------------------------------------------------------------------------- #
def print_report(results: list) -> None:
    df = pd.DataFrame(to_experiment_rows(results))
    cols = ["asset", "period", "period_role", "trigger", "management", "n_entries", "n_trades",
            "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass"]
    print(f"\n{'='*100}\n  DONCHIAN BREAKOUT BASELINE — range_lookback=10 (default), Bias=A, "
          f"Entry=C_market_close, session=sin_filtro_24h (canónico C1-C8, sin sweep, sin "
          f"optimización)\n{'='*100}")
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"] == True]  # noqa: E712 (gate_pass puede ser None)
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decisions: list) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — C5 summarize_decision(candidate_fields=('management',), "
          f"required_roles=('train','validate'), rank_by_role='validate')\n{'='*100}")
    if not decisions:
        print("  Sin combinaciones para evaluar.")
        return
    rows = [{"asset": d.asset, "management": d.candidate[0],
              "survives_required_roles": d.survives_required_roles, "rank_within_asset": d.rank_within_asset}
             for d in decisions]
    print(pd.DataFrame(rows).to_string(index=False))

    survivors = [d for d in decisions if d.survives_required_roles]
    if not survivors:
        print(f"\n{'-'*100}\n  Ningún management (V3-A ni V3-B) demuestra evidencia suficiente para "
              f"cumplir los gates de FRAMEWORK.md en 2022+2023, bajo un breakout Donchian de 10 "
              f"períodos — respuesta a la pregunta científica única de este baseline: no hay edge "
              f"suficiente todavía, con este período fijo y este protocolo, para justificar por sí "
              f"solo una siguiente fase de investigación sobre esta familia de estrategia.\n{'-'*100}")
    else:
        print(f"\n{'-'*100}\n  Al menos un (activo, management) sobrevive ambos años — evidencia "
              f"suficiente para considerar una siguiente fase de investigación sobre esta familia "
              f"de estrategia (NO implica optimizar range_lookback todavía).\n{'-'*100}")


def main() -> None:
    contracts, results = run_baseline()
    print_report(results)

    write_experiment_results_csv(RESULTS_PATH, results)
    print(f"\nResultados exportados a {RESULTS_PATH} ({len(results)} filas).")

    decisions = summarize_decision(
        results, candidate_fields=("management",),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    print_decision(decisions)
    write_decision_csv(DECISION_PATH, decisions, candidate_fields=("management",))
    print(f"Decisión exportada a {DECISION_PATH} ({len(decisions)} filas).")


if __name__ == "__main__":
    main()
