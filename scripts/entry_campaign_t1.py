#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/entry_campaign_t1.py — Campaña de validación empírica de Entrada
(Capa 3, FRAMEWORK.md) bajo Trigger=T1_ema_cross, variable única aislada
sobre la infraestructura de scripts/bias_campaign.py.

Objetivo: determinar si "D_next_candle_open" (nuevo, 2026-07-27) demuestra
evidencia suficiente para cumplir los 4 gates de FRAMEWORK.md frente a
"C_market_close" (baseline actual de T1 en backtest.py), bajo Trigger=T1.

Solo 2 candidatos de Entry aplican acá sin inventar nada: T1 (cruce EMA9/21)
emite `meta={}` — "A_pullback_50" y el candidato B (excluido de todas formas,
ver scripts/entry_campaign_sweep_bos.py) necesitan un rango sweep→BOS que un
cruce de EMA no tiene. C y D son agnósticos al candidato de Capa 2 por
diseño (research/layers.py), por eso sí aplican.

Esta campaña es un experimento COMPLETAMENTE INDEPENDIENTE de
scripts/entry_campaign_sweep_bos.py (Entry bajo Trigger=A_sweep_bos) — sus
conclusiones NO se agregan entre sí (precisión acordada 2026-07-27). Cada
script tiene su propio veredicto, su propio CSV, su propio mensaje de
decisión. Si ninguna variante de Entry aquí supera los gates, la conclusión
es que la Capa 3 tampoco demuestra evidencia suficiente bajo T1 — NO se
adopta automáticamente la variante con mejor PF relativo entre las que
fallaron.

Variable única bajo prueba: Entrada (Capa 3). Fijos, sin variar acá:
  - Bias = "A" (bias_A_ema200_neutral) — mismo supuesto de trabajo que las
    campañas anteriores, no reapertura de esa decisión cerrada.
  - Trigger = "T1_ema_cross" — eventos crudos generados UNA sola vez por
    (activo, año); no hace falta dispatch por nombre de Trigger.

Nota sobre bordes: trigger_T1_ema_cross itera `range(warmup, n-2)` — ya deja
2 velas de margen al final, así que "D_next_candle_open" (entry_idx+1)
siempre cae dentro de la serie. El guard de bordes se mantiene de todas
formas, por consistencia con scripts/entry_campaign_sweep_bos.py, no porque
se espere que dispare acá.

Reutilización de infraestructura (de scripts/bias_campaign.py, sin
modificarlo): resample_4h, apply_bias (rama "A"), gate_check,
summarize_decision, constantes de año/frecuencia. Mismos datasets dc_v1,
misma disciplina continuo-luego-slice, mismo modelo de costos, misma
ventana de sesión, misma gestión V3-A/V3-B que las campañas anteriores.

Requiere `data/raw/` poblado por scripts/download_market_data.py — BLOQUEADO
en este sandbox (HTTP 451, data/raw/ vacío). Validado acá solo
estructuralmente sobre datos sintéticos, ver
research/tests/test_entry_campaign_t1.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/entry_campaign_t1.py              # Fase 1+2: 2022+2023
    python scripts/entry_campaign_t1.py --blind       # Fase 3: 2024 ciego, requiere --candidate
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
CANDIDATES = ("C_market_close", "D_next_candle_open")
BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
FREQ_MIN_PER_MONTH = bias_camp.FREQ_MIN_PER_MONTH
FREQ_MAX_PER_MONTH = bias_camp.FREQ_MAX_PER_MONTH
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

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


def load_asset_year(asset: str, year: int) -> pd.DataFrame:
    """Carga (activo, año) desde data/raw/, corre build_dc_v1()+validate_dc_v1(),
    calcula bias_A sobre el frame COMPLETO (pre-slice, disciplina P-3) y
    recién entonces corta con periods.period_slice()."""
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
# Capa 2 fija (T1_ema_cross) + Capa 3 variable (Entry)                        #
# --------------------------------------------------------------------------- #
def _raw_events(frame: pd.DataFrame, cfg: "backtest.Config") -> list:
    """Eventos crudos de T1 — se generan UNA sola vez por (activo, año); no
    varían entre candidatos de Entry."""
    return research.TRIGGER_LAYERS[TRIGGER_CANDIDATE](
        frame, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult,
    )


def find_entries_for_entry(frame: pd.DataFrame, cfg: "backtest.Config",
                            raw_events: list, entry_name: str) -> list[dict]:
    """Réplica de backtest.py::find_entries, parametrizada por `entry_name`
    en vez de tener "C_market_close" fijo adentro — Trigger se mantiene fijo
    en T1 (eventos ya generados en `raw_events`)."""
    entry_fn = research.ENTRY_LAYERS[entry_name]
    n = len(frame)

    entries = []
    for ev in raw_events:
        row = frame.iloc[ev.entry_idx]
        if not row["in_session"] or row["bias"] != ev.direction:
            continue
        if entry_name == "D_next_candle_open" and ev.entry_idx + 1 >= n:
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
    """Corre los 2 candidatos de Entry × ambas configs de salida para un
    (activo, año), sobre el MISMO frame y los MISMOS eventos crudos de T1."""
    df_full = load_asset_year(asset, year)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    raw_events = _raw_events(frame, cfg)
    rows = []
    for entry_name in CANDIDATES:
        entries = find_entries_for_entry(frame, cfg, raw_events, entry_name)
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            rows.append({
                "asset": asset, "year": year, "candidate": entry_name,
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
    """Fase 3 (2024, ciego). Requiere `candidate` (Entry) ya congelado tras
    decidir con 2022+2023."""
    if candidate not in CANDIDATES:
        raise ValueError(
            "run_blind_test requiere un candidato de Entry ya congelado "
            f"{CANDIDATES} tras decidir con 2022+2023 — no se corre 2024 "
            "a ciegas de una decisión previa."
        )
    cfg = backtest.Config()
    results: list[dict] = []
    for asset in assets:
        df_full = load_asset_year(asset, BLIND_YEAR)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        raw_events = _raw_events(frame, cfg)
        entries = find_entries_for_entry(frame, cfg, raw_events, candidate)
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
    print(f"\n{'='*100}\n  CAMPAÑA ENTRADA bajo Trigger=T1_ema_cross "
          f"(Bias=A fijo) — C_market_close vs D_next_candle_open\n{'='*100}")
    cols = ["asset", "year", "candidate", "exit_config", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "total_r",
            "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ningún candidato de Entry demuestra "
              "evidencia suficiente todavía bajo T1_ema_cross.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Si ningún candidato de Entry sobrevive ambos años en un activo, la
    conclusión es que la Capa 3 TAMPOCO demuestra evidencia suficiente bajo
    T1 en ese activo — no se adopta automáticamente el candidato con mejor
    PF relativo entre los que fallaron los gates (precisión acordada
    2026-07-27, mismo principio que trigger_campaign.py)."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ningún candidato de Entry (C_market_close/D_next_candle_open) "
                  f"demuestra evidencia suficiente para cumplir los gates de FRAMEWORK.md en "
                  f"2022+2023 bajo Trigger=T1_ema_cross — la Capa 3 tampoco demuestra evidencia "
                  f"suficiente en este activo, independientemente de cuál haya tenido mejor PF "
                  f"relativo. Señal para considerar otra dirección de investigación en este "
                  f"activo (no un tercer candidato de Entry por defecto).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="Candidato de Entry ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato de Entry ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "entry_campaign_t1_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "entry_campaign_t1_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
