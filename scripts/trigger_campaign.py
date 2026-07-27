#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/trigger_campaign.py — Campaña de validación empírica Trigger
T1_ema_cross vs A_sweep_bos (Capa 2, FRAMEWORK.md), variable única aislada
sobre la infraestructura de scripts/bias_campaign.py.

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
    permite aislar Trigger sin cambiar también Entry.
  - Datasets dc_v1 canónicos, disciplina continuo-luego-slice (P-3),
    protocolo 2022 in-sample + 2023 validación, ventana de sesión, gestión
    V3-A/V3-B, modelo de costos, gates literales de FRAMEWORK.md — todos
    idénticos a scripts/bias_campaign.py.

Reutilización de infraestructura (de scripts/bias_campaign.py, sin
modificarlo): resample_4h, apply_bias (una sola rama, "A"), to_backtest_frame,
gate_check, summarize_decision, IN_SAMPLE_YEAR/VALIDATION_YEAR/BLIND_YEAR,
FREQ_MIN_PER_MONTH/FREQ_MAX_PER_MONTH. La columna "candidate" heredada de
summarize_decision (sin renombrar, justamente para poder reutilizar esa
función tal cual) identifica acá el candidato de TRIGGER
("T1_ema_cross"/"A_sweep_bos"), no de Bias.

`_load_raw_csv` se duplica localmente en vez de importarse — misma
convención ya establecida entre scripts/build_dc_v1_datasets.py,
scripts/inspect_single_dataset.py y scripts/bias_campaign.py (cada script
de scripts/ es ejecutable de forma standalone; solo la lógica de
pipeline/decisión sustantiva se importa, no el parsing de formato).

Lo único nuevo: `_raw_events` (dispatch por firma propia de cada Trigger —
T1 parametriza ATR/EMA vía cfg, A_sweep_bos usa sus propios defaults de
estructura de velas/sweep, no comparten kwargs) y `find_entries_for_trigger`
(mismo filtro de bias/sesión/riesgo degenerado que backtest.py::find_entries,
parametrizado por nombre de Trigger en vez de tener T1 fijo adentro — mismo
principio de composición que bias_campaign.py::apply_bias ya usó para Bias).

Requiere `data/raw/` poblado por scripts/download_market_data.py (mismo
requisito que bias_campaign.py). BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, sobre datos
sintéticos, ver research/tests/test_trigger_campaign.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/trigger_campaign.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/trigger_campaign.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import research
import scripts.bias_campaign as bias_camp
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
CANDIDATES = ("T1_ema_cross", "A_sweep_bos")
BIAS_CANDIDATE = "A"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
FREQ_MIN_PER_MONTH = bias_camp.FREQ_MIN_PER_MONTH
FREQ_MAX_PER_MONTH = bias_camp.FREQ_MAX_PER_MONTH
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

# Formato del CSV crudo — ver docstring del módulo (convención de
# duplicación deliberada, no importada de bias_campaign.py).
_TIME_COL = "open_time"
_OPEN_COL, _HIGH_COL, _LOW_COL, _CLOSE_COL, _VOLUME_COL = "open", "high", "low", "close", "volume"
_TIME_UNIT = "ms"


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


# --------------------------------------------------------------------------- #
# Carga + preparación de datos (Bias fijo en "A", a diferencia de             #
# bias_campaign.py::load_asset_year que calcula A y A2 en paralelo)           #
# --------------------------------------------------------------------------- #
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
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, BIAS_CANDIDATE)

    return period_slice(df_full, year)


# --------------------------------------------------------------------------- #
# Capa 2 — dispatch de Trigger + adaptador find_entries                       #
# --------------------------------------------------------------------------- #
def _raw_events(frame: pd.DataFrame, trigger_name: str, cfg: "backtest.Config") -> list:
    """Genera los eventos crudos de Capa 2 para `trigger_name`. T1 y
    A_sweep_bos no comparten firma (T1 parametriza ATR/EMA vía `cfg`,
    A_sweep_bos usa sus propios defaults de estructura de velas/sweep) — no
    hay un único set de kwargs genérico a pasar, igual que
    bias_campaign.py::apply_bias necesitó un dispatch por nombre para A/A2."""
    if trigger_name == "T1_ema_cross":
        return research.TRIGGER_LAYERS[trigger_name](frame, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult)
    if trigger_name == "A_sweep_bos":
        return research.TRIGGER_LAYERS[trigger_name](frame)
    raise ValueError(f"trigger de Capa 2 desconocido: {trigger_name!r} (esperado uno de {CANDIDATES})")


def find_entries_for_trigger(frame: pd.DataFrame, cfg: "backtest.Config", trigger_name: str) -> list[dict]:
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
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def run_asset_year(asset: str, year: int, cfg: "backtest.Config") -> list[dict]:
    """Corre ambos candidatos de Trigger × ambas configs de salida para un
    (activo, año), sobre el MISMO frame (Bias=A no varía entre candidatos
    acá, a diferencia de bias_campaign.py::run_asset_year donde cada
    candidato necesitaba su propio frame por tener su propio Bias)."""
    df_full = load_asset_year(asset, year)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    rows = []
    for trigger_name in CANDIDATES:
        entries = find_entries_for_trigger(frame, cfg, trigger_name)
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            rows.append({
                "asset": asset, "year": year, "candidate": trigger_name,
                "exit_config": exit_name, "n_entries": len(entries),
                "n_trades": len(trades), "metrics": m, "gate_pass": gate_check(m),
            })
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test."""
    cfg = backtest.Config()
    results: list[dict] = []
    for year in years:
        for asset in assets:
            results.extend(run_asset_year(asset, year, cfg))
    return results


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (Trigger) ya congelado tras
    decidir con 2022+2023 — mismo guardrail que
    bias_campaign.py::run_blind_test, contra el mismo mal uso del blind set."""
    if candidate not in CANDIDATES:
        raise ValueError(
            "run_blind_test requiere un candidato de Trigger ya congelado "
            f"{CANDIDATES} tras decidir con 2022+2023 — no se corre 2024 "
            "a ciegas de una decisión previa."
        )
    cfg = backtest.Config()
    results: list[dict] = []
    for asset in assets:
        df_full = load_asset_year(asset, BLIND_YEAR)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        entries = find_entries_for_trigger(frame, cfg, candidate)
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            results.append({
                "asset": asset, "year": BLIND_YEAR, "candidate": candidate,
                "exit_config": exit_name, "n_entries": len(entries),
                "n_trades": len(trades), "metrics": m, "gate_pass": gate_check(m),
            })
    return results


# --------------------------------------------------------------------------- #
# Reporte — incluye entries_per_month/fill_rate desde el inicio (el          #
# diagnóstico manual post-campaña Bias, 2026-07-27, mostró que distingue     #
# "el Trigger genera pocas oportunidades" de "se descartan después por la    #
# regla de una-posición-a-la-vez"; se incorpora acá para no recalcularlo a   #
# mano otra vez).                                                            #
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
            "asset": r["asset"], "year": r["year"], "candidate": r["candidate"],
            "exit_config": r["exit_config"], "n_entries": n_entries,
            "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA TRIGGER T1_ema_cross vs A_sweep_bos "
          f"(Bias=A y Entry=C_market_close fijos)\n{'='*100}")
    cols = ["asset", "year", "candidate", "exit_config", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "total_r",
            "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ningún Trigger demuestra evidencia "
              "suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Mismo formato que bias_campaign.py::print_decision (reutiliza
    summarize_decision sin modificarlo), con el mensaje por-activo ajustado
    a la precisión conceptual acordada: si ningún Trigger sobrevive ambos
    años en un activo, la conclusión es que AMBOS permanecen insuficientes
    como Trigger principal para ese activo — no "ninguno le gana al otro",
    ni se adopta el que haya tenido mejor PF relativo entre los que
    fallaron los gates."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
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
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "trigger_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "trigger_campaign_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
