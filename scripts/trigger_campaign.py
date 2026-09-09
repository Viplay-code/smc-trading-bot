#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/trigger_campaign.py — Campaña de validación empírica Trigger
T1_ema_cross vs A_sweep_bos (Capa 2, FRAMEWORK.md). MIGRADO a la
infraestructura canónica C1-C8 (2026-09-09), tras demostrar equivalencia
exacta 24/24 (ver auditoría de migración) contra la versión legacy (que
corría sobre `_raw_events`/`find_entries_for_trigger` propios +
`backtest.run_config`/`backtest.metrics` directamente — ambas funciones ya
eran, por diseño desde 2026-07-27, una réplica manual de lo que hoy vive de
forma canónica en `research/entries.py::find_entries`, Componente de
generalización Trigger/Entry, 2026-09-03).

Objetivo: determinar si alguno de los dos candidatos de Trigger registrados
en `research.TRIGGER_LAYERS` — "T1_ema_cross" (ya medido en la campaña Bias
A vs A2, commit 6687b46) o "A_sweep_bos" (lo que usa `bot.py`, nunca corrido
con datos reales dc_v1 + los gates de FRAMEWORK.md) — demuestra evidencia
suficiente para cumplir los 4 gates de FRAMEWORK.md. La pregunta NO es cuál
Trigger es relativamente mejor: si uno supera al otro pero ninguno sobrevive
los gates en un activo, la conclusión para ese activo es que AMBOS
permanecen insuficientes como Trigger principal — no se adopta
automáticamente el ganador relativo entre dos candidatos insuficientes
(precisión conceptual acordada 2026-07-27, antes de implementar este
script; ver print_decision).

Variable única bajo prueba: Trigger (Capa 2). Fijo, sin variar en esta
campaña:
  - Bias = "A" (bias_A_ema200_neutral) — la campaña Bias A vs A2 (commit
    6687b46) ya mostró que A2 no aporta diferencia material frente a A; se
    sostiene A como supuesto de trabajo (más simple, lo que ya usa
    `bot.py`), NO como reapertura de esa decisión ya cerrada.
  - Entry = "C_market_close" — única combinación válida sin escribir código
    nuevo: `entry_A_pullback_50` necesita `event.meta["bos_level"]`/
    `swing_low`/`swing_high`, que SOLO produce `trigger_A_sweep_bos`;
    `trigger_T1_ema_cross` emite `meta={}`. `entry_C_market_close` es
    trigger-agnóstico por diseño (research/layers.py:396-401) — es lo que
    permite aislar Trigger sin cambiar también Entry. Verificado en código
    (`research.ENTRY_META_REQUIREMENTS`) que "C_market_close" no tiene
    ninguna restricción de compatibilidad con ningún Trigger.
  - session = "control_8h" — sin sweep de sesión en esta campaña (a
    diferencia de `gestion_campaign_session.py`), coincide con
    `backtest.Config()` por defecto y con
    `research.runner.SESSION_WINDOWS["control_8h"]` (verificado
    byte-idéntico en la auditoría previa).
  - Datasets dc_v1 canónicos, disciplina continuo-luego-slice (P-3),
    protocolo 2022 in-sample + 2023 validación, gestión V3-A/V3-B, modelo
    de costos, gates literales de FRAMEWORK.md — todos idénticos a
    scripts/bias_campaign.py.

ALCANCE EXPERIMENTAL — Raw EXCLUIDO deliberadamente (mismo criterio que
`gestion_campaign_session.py`, auditoría de alcance 2026-09-09):
`research.EXIT_CONFIGS`/`research.runner.MANAGEMENT_LAYERS` contienen una
tercera entrada, `"Raw"`, desde Fase 5 (commit `e1f2367`, 2026-09-03) —
agregada MÁS DE UN MES DESPUÉS de que esta campaña (2026-07-27) fuera
diseñada y su artifact histórico (24 filas) publicado, para una
investigación completamente distinta (Espacio 6). Por eso `MANAGEMENTS`
abajo es una tupla EXPLÍCITA, nunca `research.runner.MANAGEMENT_LAYERS.
keys()`/`research.EXIT_CONFIGS.keys()`. De la misma forma, `TRIGGERS` es
una tupla EXPLÍCITA de solo 2 candidatos — `research.TRIGGER_LAYERS` tiene
HOY 4 entradas (también `D_range_breakout`/`C_bos_only`, agregados después,
usados por otras campañas — `trigger_c_campaign.py`/
`trigger_entry_campaign_rama_b.py`) — recorrerlo genéricamente introduciría
2 candidatos fuera del alcance de ESTA campaña. Ver
`test_raw_y_triggers_extra_explicitamente_excluidos_del_universo` en
`research/tests/test_trigger_campaign.py` (guardia de regresión).

Verificación de equivalencia previa a la migración (auditoría 2026-09-09,
spot-check real vía `research.runner.run()` contra las 4 celdas
BTCUSDT/2022 × {T1_ema_cross,A_sweep_bos} × {V3-A,V3-B}): 4/4 exactas,
incluyendo A_sweep_bos (el candidato de mayor riesgo, nunca antes ejecutado
por el motor canónico end-to-end).

Mapping legacy -> canónico (migración 2026-09-09):
    asset        -> asset
    year         -> period
    candidate    -> trigger
    exit_config  -> management
    n_entries/n_trades/pf/wr/exp_r/total_r/max_dd/freq/gate_pass -> ídem
Columnas diagnósticas legacy SIN equivalente canónico (`entries_per_month`,
`fill_rate`, `be`, `reason_stop`, `reason_timeout`) — NO migradas: ya
clasificadas como puramente diagnósticas, ajenas a métricas/gates/decisión
(mismo criterio genérico aplicado en la migración de
`gestion_campaign_session.py`).

Caso especial (verificado explícitamente en la validación de la
migración): las 6 filas históricas de A_sweep_bos/2023 tienen
pf/wr/exp_r/total_r/max_dd/freq = NaN (muestra `n_trades<5` ->
`backtest.metrics` retorna `None` -> todos los campos numéricos de
`ExperimentResult` quedan `None`) — la comparación de equivalencia debe
ser NaN-aware, no debe tratarse como fila ausente.

Reutilización de infraestructura: `research.expand_universe` (C4),
`research.runner.run_many` (C3, que ya usa `research.entries.find_entries`
internamente — generalización EXACTA de la lógica legacy de este script),
`research.summarize_decision` (C5), `research.write_experiment_results_csv`/
`write_decision_csv` (C6). `scripts.bias_campaign` se sigue usando SOLO para
las constantes compartidas (`IN_SAMPLE_YEAR`/`VALIDATION_YEAR`/`BLIND_YEAR`)
— ya no para cargar datos ni calcular Bias en la ORQUESTACIÓN DE ESTA
CAMPAÑA (eso ahora lo hace `run_many` internamente, por contrato).

DEPENDENCIA CRUZADA PRESERVADA (descubierta durante la migración, resuelta
sin tocar el consumidor): `scripts/gestion_campaign_session.py` (ya
migrado, commit `c10ddb4`) importa `scripts.trigger_campaign` para sus
sanity-checks científicos (`load_asset_year`/`_raw_events`/
`find_entries_for_trigger` — verificación de acoplamiento sessions<->
Trigger, ver su propio docstring). Por eso estas 4 funciones (más
`_load_raw_csv`) se PRESERVAN acá sin modificar, aunque la orquestación de
ESTA campaña (`run_campaign`/`run_blind_test`/`build_universe`) ya NO las
invoca internamente — son legacy respecto de este script, pero producción
activa para otro consumidor real.

Artifacts: la ejecución normal de este script (`main()`) escribe a
`trigger_campaign_canonical_results.csv`/
`trigger_campaign_canonical_decision.csv` — artifacts SEPARADOS del
baseline histórico (`trigger_campaign_results.csv`/`_decision.csv`), que
nunca se sobrescriben por este script.

Requiere `data/raw/` poblado.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/trigger_campaign.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/trigger_campaign.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import research
from research import runner
from research.expand import expand_universe
from research.decision import summarize_decision as canonical_summarize_decision
from research.persistence import (
    write_experiment_results_csv, write_decision_csv, to_experiment_rows,
)
import scripts.bias_campaign as bias_camp
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Alcance experimental de esta campaña (ver docstring del módulo)            #
# --------------------------------------------------------------------------- #
TRIGGERS = ("T1_ema_cross", "A_sweep_bos")
"""Tupla EXPLÍCITA, NUNCA `research.TRIGGER_LAYERS.keys()` — ver docstring
del módulo (D_range_breakout/C_bos_only excluidos del alcance de ESTA
campaña)."""

MANAGEMENTS = ("V3-A", "V3-B")
"""Tupla EXPLÍCITA, NUNCA `research.runner.MANAGEMENT_LAYERS.keys()` ni
`research.EXIT_CONFIGS.keys()` — ver docstring del módulo (Raw excluido
deliberadamente del alcance de ESTA campaña)."""

CANDIDATES = TRIGGERS  # nombre heredado del legacy: identifica el candidato bajo --blind/--candidate

BIAS_CANDIDATE = "A_ema200_neutral"
ENTRY_CANDIDATE = "C_market_close"
SESSION = "control_8h"
ATR_MULT = 1.5
ATR_PERIOD = 14
RISK = 0.005
COST_PER_TRADE = 0.0009
MAX_HOLD = 20

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}

# Formato del CSV crudo — ver docstring del módulo (convención de
# duplicación deliberada, no importada de bias_campaign.py).
_TIME_COL = "open_time"
_OPEN_COL, _HIGH_COL, _LOW_COL, _CLOSE_COL, _VOLUME_COL = "open", "high", "low", "close", "volume"
_TIME_UNIT = "ms"


# --------------------------------------------------------------------------- #
# PRESERVADAS sin modificar — dependencia cruzada real de                    #
# scripts/gestion_campaign_session.py (ver docstring del módulo, sección     #
# "DEPENDENCIA CRUZADA PRESERVADA"). La orquestación de ESTA campaña         #
# (más abajo) ya NO las invoca — usa research.runner.run_many (C3), que      #
# internamente delega en research.entries.find_entries, la generalización   #
# canónica de exactamente esta misma lógica.                                #
# --------------------------------------------------------------------------- #
def _load_raw_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, header=0)
    ts = pd.to_datetime(df[_TIME_COL], unit=_TIME_UNIT, utc=True)
    raw = pd.DataFrame(
        {
            "open":   pd.to_numeric(df[_OPEN_COL],   errors="coerce").to_numpy(),
            "high":   pd.to_numeric(df[_HIGH_COL],   errors="coerce").to_numpy(),
            "low":    pd.to_numeric(df[_LOW_COL],    errors="coerce").to_numpy(),
            "close":  pd.to_numeric(df[_CLOSE_COL],  errors="coerce").to_numpy(),
            "volume": pd.to_numeric(df[_VOLUME_COL], errors="coerce").to_numpy(),
        },
        index=pd.DatetimeIndex(ts, name="open_time"),
    )
    return raw


def load_asset_year(asset: str, year: int) -> pd.DataFrame:
    """Carga (activo, año) desde data/raw/, corre build_dc_v1()+validate_dc_v1(),
    calcula bias_A sobre el frame COMPLETO (pre-slice, misma disciplina P-3 que
    bias_campaign.py::load_asset_year) y recién entonces corta con
    periods.period_slice(). Un solo Bias (A, fijo por diseño de esta
    campaña), no dos."""
    path = raw_path(asset, INTERVAL_1H, year, RAW_DIR)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} no existe — corré scripts/download_market_data.py primero."
        )
    raw = _load_raw_csv(path)
    df_full = build_dc_v1(raw, asset=asset, dataset_version=DATASET_VERSION,
                           pipeline_version=PIPELINE_VERSION)
    errs = validate_dc_v1(df_full, strict=False)
    if errs:
        raise ValueError(f"validate_dc_v1 falló para {asset}/{year}: {errs}")

    df4h_full = bias_camp.resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, "A")

    return period_slice(df_full, year)


def _raw_events(frame: pd.DataFrame, trigger_name: str, cfg) -> list:
    """Genera los eventos crudos de Capa 2 para `trigger_name`. T1 y
    A_sweep_bos no comparten firma (T1 parametriza ATR/EMA vía `cfg`,
    A_sweep_bos usa sus propios defaults de estructura de velas/sweep) — no
    hay un único set de kwargs genérico a pasar, igual que
    bias_campaign.py::apply_bias necesitó un dispatch por nombre para A/A2."""
    if trigger_name == "T1_ema_cross":
        return research.TRIGGER_LAYERS[trigger_name](frame, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult)
    if trigger_name == "A_sweep_bos":
        return research.TRIGGER_LAYERS[trigger_name](frame)
    raise ValueError(f"trigger de Capa 2 desconocido: {trigger_name!r} (esperado uno de {TRIGGERS})")


def find_entries_for_trigger(frame: pd.DataFrame, cfg, trigger_name: str) -> list[dict]:
    """Réplica de backtest.py::find_entries, parametrizada por `trigger_name`
    en vez de tener "T1_ema_cross" fijo adentro. Entry se mantiene fija en
    "C_market_close" (única combinación válida sin escribir código nuevo,
    ver docstring del módulo) y el filtro de bias/sesión/riesgo degenerado
    es EXACTAMENTE el mismo que aplica backtest.find_entries — para
    trigger_name="T1_ema_cross" sobre el mismo frame, produce las mismas
    entradas que backtest.find_entries (ver
    research/tests/test_trigger_campaign.py, chequeo de paridad)."""
    raw_events = _raw_events(frame, trigger_name, cfg)
    entry_fn = research.ENTRY_LAYERS["C_market_close"]

    entries = []
    for ev in raw_events:
        row = frame.iloc[ev.entry_idx]
        if not row["in_session"] or row["bias"] != ev.direction:
            continue

        entry = entry_fn(frame, ev).price
        atr = row["atr"]
        if ev.direction == "long":
            sl = min(row["low"], entry - cfg.atr_mult * atr)
        else:
            sl = max(row["high"], entry + cfg.atr_mult * atr)
        risk_pts = abs(entry - sl)
        if risk_pts < 1e-9:
            continue

        entries.append({
            "entry_idx": ev.entry_idx, "direction": ev.direction,
            "entry": entry, "sl0": sl, "risk_pts": risk_pts,
        })
    return entries


# --------------------------------------------------------------------------- #
# Universo canónico (C4) + ejecución canónica (C3)                          #
# --------------------------------------------------------------------------- #
def build_universe(
    assets: tuple[str, ...], years: dict[str, int],
    triggers: tuple[str, ...] = TRIGGERS, managements: tuple[str, ...] = MANAGEMENTS,
) -> list[dict]:
    """Universo canónico: un template por (trigger, management), expandido
    vía `research.expand_universe` (C4, assets x years) — `expand_universe`
    no expande `trigger`/`management`, así que esas 2 dimensiones se
    recorren acá explícitamente, con listas EXPLÍCITAS (`triggers`,
    `managements`), nunca leyendo un registro genérico (ver docstring del
    módulo, alcance experimental)."""
    contracts: list[dict] = []
    for trigger in triggers:
        for mgmt in managements:
            template = {
                "name": "trigger_campaign",
                "contract_version": "1",
                "assets": list(assets),
                "years": dict(years),
                "bias": {"name": BIAS_CANDIDATE, "params": {}},
                "trigger": {"name": trigger, "params": {}},
                "entry": {"name": ENTRY_CANDIDATE, "params": {}},
                "session": SESSION,
                "management": {"name": mgmt, "params": {}},
                "risk": RISK,
                "cost_per_trade": COST_PER_TRADE,
                "max_hold": MAX_HOLD,
                "atr_mult": ATR_MULT,
                "gates": dict(_CANONICAL_GATES),
                "independent_variable": "trigger",
                "blind_authorized": "blind" in years,
            }
            contracts.extend(expand_universe(template))
    return contracts


def run_campaign(assets: tuple[str, ...] = ASSETS) -> tuple[list[dict], list]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test.
    Universo completo: 2 triggers x 2 managements x 3 assets x 2 years =
    24 contratos/resultados."""
    contracts = build_universe(assets, {"train": IN_SAMPLE_YEAR, "validate": VALIDATION_YEAR})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    results = runner.run_many(contracts)
    return contracts, results


def run_blind_test(assets: tuple[str, ...] = ASSETS, candidate: str | None = None) -> tuple[list[dict], list]:
    """Fase 3 (2024, ciego). Requiere `candidate` (un Trigger, ej.
    "A_sweep_bos") ya congelado tras decidir con 2022+2023 — mismo
    guardrail que la versión legacy, contra el mismo mal uso del blind
    set. El universo ejecutado se restringe al único Trigger congelado
    (ambos managements, todos los activos)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato de Trigger ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una decisión previa."
        )
    contracts = build_universe(assets, {"blind": BLIND_YEAR}, triggers=(candidate,))
    for c in contracts:
        runner.validate_contract(c)
    results = runner.run_many(contracts)
    return contracts, results


# --------------------------------------------------------------------------- #
# Reporte — derivado DIRECTAMENTE de ExperimentResult (C3), ninguna métrica #
# se recalcula acá (ver mapping legacy->canónico en el docstring)           #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list) -> pd.DataFrame:
    """`list[ExperimentResult]` -> DataFrame de reporte, vía
    `research.to_experiment_rows` (C6, transformación pura ya existente) —
    ninguna columna se fabrica ni se recalcula acá."""
    return pd.DataFrame(to_experiment_rows(results))


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA TRIGGER T1_ema_cross vs A_sweep_bos "
          f"(Bias=A, Entry=C_market_close, session=control_8h fijos — canónico C1-C8)\n{'='*100}")
    cols = ["asset", "period", "period_role", "trigger", "management", "n_entries", "n_trades",
            "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"] == True]  # noqa: E712 (gate_pass puede ser None)
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ningún Trigger demuestra evidencia "
              "suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decisions: list) -> None:
    """Mismo criterio conceptual que la versión legacy: si ningún Trigger
    sobrevive ambos años en un activo, la conclusión es que AMBOS
    permanecen insuficientes como Trigger principal para ese activo — no
    "ninguno le gana al otro", ni se adopta el que haya tenido mejor PF
    relativo entre los que fallaron los gates."""
    print(f"\n{'='*100}\n  DECISIÓN — C5 summarize_decision(candidate_fields=('trigger','management'), "
          f"required_roles=('train','validate'), rank_by_role='validate')\n{'='*100}")
    if not decisions:
        print("  Sin combinaciones para evaluar.")
        return
    rows = [{"asset": d.asset, "trigger": d.candidate[0], "management": d.candidate[1],
              "survives_required_roles": d.survives_required_roles, "rank_within_asset": d.rank_within_asset}
             for d in decisions]
    print(pd.DataFrame(rows).to_string(index=False))

    by_asset: dict[str, list] = {}
    for d in decisions:
        by_asset.setdefault(d.asset, []).append(d)
    for asset, ds in by_asset.items():
        survivors = [d for d in ds if d.survives_required_roles]
        if not survivors:
            print(f"\n  {asset}: ningún Trigger (T1_ema_cross ni A_sweep_bos) demuestra evidencia "
                  f"suficiente para cumplir los gates de FRAMEWORK.md en 2022+2023 — ambos "
                  f"permanecen insuficientes como Trigger principal en este activo, "
                  f"independientemente de cuál haya tenido mejor PF relativo. Señal para "
                  f"considerar un tercer candidato de Capa 2.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="Trigger ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el Trigger ya congelado)")
        contracts, results = run_blind_test(candidate=args.candidate)
    else:
        contracts, results = run_campaign()

    df = results_to_frame(results)
    print_report(df)

    out_results_path = "trigger_campaign_canonical_results.csv"
    write_experiment_results_csv(out_results_path, results)
    print(f"\nResultados canónicos exportados a {out_results_path} ({len(results)} filas) "
          f"-- artifact SEPARADO del histórico trigger_campaign_results.csv (NO sobrescrito).")

    if not args.blind:
        decisions = canonical_summarize_decision(
            results, candidate_fields=("trigger", "management"),
            required_roles=("train", "validate"), rank_by_role="validate",
        )
        print_decision(decisions)
        out_decision_path = "trigger_campaign_canonical_decision.csv"
        write_decision_csv(out_decision_path, decisions, candidate_fields=("trigger", "management"))
        print(f"Decisión canónica exportada a {out_decision_path} ({len(decisions)} filas) "
              f"-- artifact SEPARADO del histórico trigger_campaign_decision.csv (NO sobrescrito).")


if __name__ == "__main__":
    main()
