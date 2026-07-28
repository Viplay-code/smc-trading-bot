#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_atr_mult.py — Campaña de validación empírica
Gestión: distancia del stop-loss inicial (`atr_mult`), bajo Trigger=T1_ema_cross
fijo, sobre la infraestructura de scripts/bias_campaign.py y
scripts/trigger_campaign.py.

Hipótesis (H1) a falsificar: existe un valor de `atr_mult` distinto del
actual (1.5) que, sin modificar ningún otro parámetro, permite que al menos
una combinación (activo, atr_mult, exit_config) supere los 4 gates de
FRAMEWORK.md en 2022 Y 2023 para ese activo. Se considera falsificada si,
barriendo todo el rango candidato, ninguna combinación sobrevive ambos años
en ningún activo.

Por qué `atr_mult` es la primera variable de Gestión a aislar (acordado
2026-07-28, revisado — NO por el patrón "la mayoría termina en stop", que
resultó ser una categoría demasiado agregada para sostener esa lectura por
sí sola):
  1. Orden de dependencia: `be`/`activation`/`distance` (V3-A/V3-B, ya
     parcialmente explorados) están definidos en múltiplos de R, y R =
     `risk_pts` = la distancia del SL inicial. Tocar los múltiplos antes de
     saber si R mismo está bien calibrado arriesga confundir "R mal
     dimensionado" con "mal múltiplo de R".
  2. `atr_mult` nunca varió en Bias, Trigger ni Entry — máxima ganancia de
     información esperada de cualquier parámetro de Gestión.

Variable independiente: `atr_mult` (Config.atr_mult), rango candidato
{1.0, 1.5 (control/baseline), 2.0, 3.0} — 1.5 es el valor ya corrido en las
tres campañas anteriores (ancla obligatoria de comparación); 1.0 es el
control de falsificación en la dirección de endurecimiento; 2.0/3.0 cubren
la práctica habitual de stops basados en ATR (1-3×ATR) en la dirección de
ensanchamiento que la hipótesis anticipa como más probable.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no A_sweep_bos
— su problema es de escasez de eventos, que Gestión no puede resolver),
Entry=C_market_close, `atr_period`=14, `be`/`activation`/`distance` (V3-A y
V3-B corridos en paralelo, no es la variable bajo prueba), `max_hold`=20,
sesión Londres+NY, `risk`=0.005, una-posición-a-la-vez, datasets dc_v1
canónicos, disciplina P-3, modelo de costos, gates literales de
FRAMEWORK.md.

Instrumentación nueva (no toca `backtest.py`): `avg_win`/`avg_loss`, que
`backtest.metrics()` ya calcula pero ningún script anterior exportaba —
necesarios para leer correctamente el resultado, dado que `reason="stop"`
mezcla pérdida completa, scratch de breakeven y ganancia bloqueada por
trailing en una sola categoría.

Verificación de acoplamiento (2026-07-28): `trigger_T1_ema_cross` recibe
`atr_mult` (research/layers.py:376-380) SOLO para un chequeo de riesgo
degenerado posterior a la detección del cruce — `risk_pts =
max(rango_de_la_vela, atr_mult·ATR)`, que solo podría ser <1e-9 si AMBOS
términos fueran ~0 simultáneamente (vela sin mecha Y ATR≈0), algo que no
ocurre en datos reales 1H de BTC/ETH/SOL. La detección del cruce en sí
(`cross_up`/`cross_down`) depende solo de EMA9/EMA21, nunca de `atr_mult`.
Conclusión: el Trigger es efectivamente independiente de `atr_mult` para el
rango probado. `assert_trigger_invariant_to_atr_mult` convierte esa prueba
de código en una verificación empírica que corre en cada ejecución real —
si alguna vez fallara, sería evidencia de que el análisis de código no se
sostiene en datos reales y la campaña no podría tratarse como un
experimento puro de Gestión sin investigar eso primero.

Reutilización de infraestructura (sin modificar ninguno de los dos): de
scripts/bias_campaign.py — `to_backtest_frame`, `gate_check`,
`summarize_decision`. De scripts/trigger_campaign.py — `load_asset_year`
(Bias=A ya resuelto), `_raw_events`/`find_entries_for_trigger` (el punto
exacto donde `atr_mult` entra en la detección de T1, reutilizado tal cual
para la verificación de acoplamiento). La columna "candidate" identifica
acá el valor de `atr_mult` probado (como string, ej. "1.0"), no un
candidato de Bias/Trigger/Entry.

Requiere `data/raw/` poblado (mismo requisito que las campañas anteriores).
BLOQUEADO en este sandbox (HTTP 451, data/raw/ vacío) — validado acá solo
estructuralmente, ver research/tests/test_gestion_campaign_atr_mult.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_atr_mult.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_atr_mult.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
ATR_MULT_VALUES = (1.0, 1.5, 2.0, 3.0)
CANDIDATES = tuple(str(v) for v in ATR_MULT_VALUES)  # ("1.0", "1.5", "2.0", "3.0")

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision


def _label(atr_mult: float) -> str:
    return str(atr_mult)


# --------------------------------------------------------------------------- #
# Verificación de acoplamiento atr_mult <-> Trigger (sanity-check empírico)   #
# --------------------------------------------------------------------------- #
def raw_trigger_event_counts(frame: pd.DataFrame) -> dict[float, int]:
    """Conteo de eventos CRUDOS (antes del filtro de bias/sesión) de
    TRIGGER_CANDIDATE para cada valor de ATR_MULT_VALUES, usando
    trigger_campaign.py::_raw_events — el punto exacto donde `atr_mult`
    entra en la detección de T1 (ver verificación de acoplamiento en el
    docstring del módulo)."""
    counts = {}
    for atr_mult in ATR_MULT_VALUES:
        cfg = backtest.Config(atr_mult=atr_mult)
        counts[atr_mult] = len(trigger_camp._raw_events(frame, TRIGGER_CANDIDATE, cfg))
    return counts


def assert_counts_invariant(counts: dict[float, int], asset: str, year: int) -> None:
    """Falla ruidosamente si el conteo de eventos crudos varía entre
    valores de atr_mult — señal de que el acoplamiento verificado como
    inerte en código (research/layers.py:376-380) no se sostiene en estos
    datos reales, y la campaña NO puede tratarse como un experimento puro
    de Gestión sin investigar eso primero."""
    distinct = set(counts.values())
    if len(distinct) != 1:
        raise AssertionError(
            f"Acoplamiento atr_mult<->{TRIGGER_CANDIDATE} detectado en datos reales "
            f"para {asset}/{year}: el conteo de eventos crudos varía con atr_mult "
            f"({counts}) — contradice la verificación de código de 2026-07-28. "
            f"Esta campaña no aísla Gestión hasta que esto se investigue."
        )


def assert_trigger_invariant_to_atr_mult(frame: pd.DataFrame, asset: str, year: int) -> None:
    assert_counts_invariant(raw_trigger_event_counts(frame), asset, year)


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def run_asset_year(asset: str, year: int) -> list[dict]:
    """Corre los 4 valores de atr_mult × ambas configs de salida para un
    (activo, año), sobre el MISMO frame (Bias=A y Trigger=T1_ema_cross no
    varían entre valores de atr_mult — solo el SL/riesgo inicial que
    `find_entries_for_trigger` calcula por dentro). Corre el sanity-check de
    invarianza del Trigger antes de generar ninguna métrica."""
    df_full = trigger_camp.load_asset_year(asset, year)
    base_cfg = backtest.Config()
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], base_cfg)

    assert_trigger_invariant_to_atr_mult(frame, asset, year)

    rows = []
    for atr_mult in ATR_MULT_VALUES:
        cfg = backtest.Config(atr_mult=atr_mult)
        entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            rows.append({
                "asset": asset, "year": year, "candidate": _label(atr_mult),
                "exit_config": exit_name, "n_entries": len(entries),
                "n_trades": len(trades), "metrics": m, "gate_pass": gate_check(m),
            })
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test."""
    results: list[dict] = []
    for year in years:
        for asset in assets:
            results.extend(run_asset_year(asset, year))
    return results


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (un valor de atr_mult, como
    string, ej. "2.0") ya congelado tras decidir con 2022+2023 — mismo
    guardrail que bias_campaign.py/trigger_campaign.py."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un atr_mult ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    atr_mult = float(candidate)
    results: list[dict] = []
    for asset in assets:
        df_full = trigger_camp.load_asset_year(asset, BLIND_YEAR)
        base_cfg = backtest.Config()
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], base_cfg)
        assert_trigger_invariant_to_atr_mult(frame, asset, BLIND_YEAR)

        cfg = backtest.Config(atr_mult=atr_mult)
        entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
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
# Reporte — incluye avg_win/avg_loss (instrumentación nueva acordada         #
# 2026-07-28, ya calculada por backtest.metrics() pero nunca exportada) más  #
# entries_per_month/fill_rate (heredado de trigger_campaign.py).             #
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
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN — atr_mult (SL inicial) bajo Trigger=T1_ema_cross, "
          f"Bias=A y Entry=C_market_close fijos\n{'='*100}")
    cols = ["asset", "year", "candidate", "exit_config", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ningún atr_mult del rango probado "
              "demuestra evidencia suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Mismo formato que bias_campaign.py/trigger_campaign.py::print_decision
    (reutiliza summarize_decision sin modificarlo). Si ningún atr_mult
    sobrevive ambos años en un activo, la lectura del patrón (monótono sin
    amesetarse -> ampliar rango; plano o no monótono -> pasar a la siguiente
    variable de Gestión) es una decisión de interpretación humana sobre el
    CSV completo, no algo que este script decida solo."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ningún atr_mult en {CANDIDATES} demuestra evidencia suficiente "
                  f"para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo Trigger="
                  f"{TRIGGER_CANDIDATE} — el riesgo inicial (Gestión) tampoco explica la falla "
                  f"en este activo con este rango, independientemente de cuál haya tenido mejor "
                  f"PF relativo. Revisar el patrón PF/freq vs atr_mult en el CSV: si mejora de "
                  f"forma monótona sin amesetarse, ampliar el rango antes de descartar la "
                  f"hipótesis; si es plano o no monótono, pasar a protección/trailing "
                  f"desacoplados como siguiente variable.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="atr_mult ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el atr_mult ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_atr_mult_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "gestion_campaign_atr_mult_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
