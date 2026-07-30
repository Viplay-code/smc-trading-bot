#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_trailing_distance.py — Campaña de validación
empírica Gestión (H2.1): distancia de trailing (`distance`, en R), bajo
Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/atr_mult=1.5 fijos, sobre
la infraestructura de scripts/bias_campaign.py y scripts/trigger_campaign.py.

Contexto: sigue al diagnóstico MFE/MAE (scripts/gestion_mfe_diagnostico.py,
cerrado 2026-07-30, commit d8fe51b) que encontró, sobre datos reales
2022/2023, un margen positivo y consistente entre `avg_win` realizado y la
media de MFE_R de los ganadores en los 6 combos activo×año evaluados, y que
ese margen alcanzaría el gate PF>=1.50 en 5 de 6 combos (techo teórico, sin
regla de salida real). Ese diagnóstico NO probó ninguna regla de salida —
esta campaña sí, aislando `distance` como primera variable de Gestión a
desacoplar (H2.1 de la familia H2; ver diseño acordado 2026-07-30).

Hipótesis (H2.1) a falsificar: existe un valor de `distance` distinto del
actual V3-A (1.0R) que, sin modificar ningún otro parámetro (`be`=1.0R y
`activation`=2.0R fijos en su valor de V3-A — no es un barrido V3-A/V3-B en
paralelo, esa convención queda superada para este parámetro específico),
permite que al menos una combinación (activo, distance) supere los 4 gates
de FRAMEWORK.md en 2022 Y 2023 para ese activo. Se considera falsificada
si, barriendo el rango candidato completo (incluidas las extensiones por
contingencia, ver abajo), ninguna combinación sobrevive ambos años en
ningún activo.

Por qué `distance` es la primera variable de la familia H2 a aislar (orden
acordado 2026-07-30): una vez activo el trailing, `distance` determina
directamente cuánto se devuelve desde el pico favorable antes de cerrar
(`trail_stop = max_fav_pts - distance*risk_pts`) — es la palanca
mecánicamente más cercana a la brecha que midió el diagnóstico MFE/MAE
(avg_win realizado vs techo de MFE). `activation` (cuándo empieza a operar
`distance`) y `be` (clasificación de operaciones marginales) quedan para
H2.2/H2.3, contingentes al resultado de esta campaña — no se diseñan acá.

Rango candidato base: {0.5, 0.75, 1.0 (ancla=V3-A/control), 1.5}. La
resolución es deliberadamente asimétrica, no un descuido:
  - Por encima del ancla (distance>1.0, trailing más flojo): la fórmula del
    trailing garantiza una predicción MONÓTONA — mayor `distance` nunca
    puede capturar más que uno menor para una misma trayectoria de precio.
    No hay mecanismo en el motor que genere un óptimo local ahí, así que un
    solo punto (1.5) alcanza como control de falsificación: si rompe la
    monotonía, la ruptura se detecta con cualquier punto por encima del
    ancla, no hace falta más resolución a priori.
  - Por debajo del ancla (distance<1.0, trailing más ajustado): compiten
    DOS efectos — más captura del pico (monótono, igual mecanismo) contra
    una posible caída de WR por cierres prematuros ante ruido normal de
    vela (efecto que el diagnóstico MFE/MAE, al no aplicar ninguna regla de
    salida, no pudo medir). Si existe un cruce entre ambos efectos puede
    estar en cualquier punto del rango, de ahí el paso uniforme de 0.25R en
    {0.5, 0.75, 1.0}.

Reglas de contingencia PRE-ESPECIFICADAS (no exploratorias — se evalúan
automáticamente dentro de run_asset_year, por (activo, año), antes de
cerrar cualquier conclusión; ajustadas 2026-07-30 a pedido explícito para
usar el criterio completo de FRAMEWORK.md, no una métrica aislada):
  1. Límite superior: si distance=1.5 no muestra deterioro respecto al
     ancla distance=1.0 en NINGUNA de las 4 métricas que evalúa
     gate_check() (pf, max_dd, exp_r, freq — no solo pf, ver
     `_no_deterioration`) para un (activo, año), eso es señal de posible
     confusión (algo distinto de la captura de MFE explicaría la mejora) y
     dispara una corrida adicional en distance=1.25 para ESE (activo, año).
  2. Límite inferior: si distance=0.5 tiene el mejor PF de todo el barrido
     base para un (activo, año) — el extremo, no un máximo interior — eso
     sugiere que el verdadero cruce de efectos puede estar fuera del rango
     probado, y dispara una corrida adicional en distance=0.25 para ESE
     (activo, año). Acá sí se usa PF en solitario (no las 4 métricas): es
     la misma métrica de selección entre variantes que ya usa la jerarquía
     de criterios de FRAMEWORK.md, y el propósito es de ranking/extremo, no
     de detección de confusión como la regla 1.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no A_sweep_bos
— mismo motivo que en atr_mult/H1: escasez de eventos, Gestión no lo
resuelve), Entry=C_market_close, `atr_mult`=1.5 (ancla de H1, ya cerrada),
`atr_period`=14, `be`=1.0R, `activation`=2.0R, `max_hold`=20, sesión
Londres+NY (control_8h — deliberadamente NO se cambia a `dcv1_activo_15h`
acá: mezclar un cambio de sesión con un cambio de Gestión en la misma
corrida impediría atribuir cualquier mejora a una sola causa), `risk`=0.005,
una-posición-a-la-vez, datasets dc_v1 canónicos, disciplina P-3, modelo de
costos, gates literales de FRAMEWORK.md.

Nota de acoplamiento: a diferencia de `atr_mult` (que sí entra en
`trigger_T1_ema_cross` y necesitó una verificación empírica de invarianza),
`distance` solo se usa dentro de `backtest.simulate_v3`, después de que
`find_entries_for_trigger` ya generó las entradas — la invarianza de
entradas respecto de `distance` es estructural (no hay ninguna ruta de
código que las conecte), por lo que las entradas se calculan UNA sola vez
por (activo, año) y se reutilizan tal cual para cada valor de `distance`,
sin necesitar una aserción empírica equivalente a
`assert_trigger_invariant_to_atr_mult`.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year` (Bias=A ya resuelto),
`find_entries_for_trigger`. `summarize_decision` agrupa por
(asset, candidate, exit_config) — acá `exit_config` es una columna
constante (`EXIT_CONFIG_LABEL`, no hay barrido V3-A/V3-B) para reutilizar
esa función sin modificarla; el agrupamiento efectivo queda en
(asset, candidate).

NO reutiliza `gestion_mfe_diagnostico.py`: ese script fue diagnóstico puro
(sin regla de salida). Acá la decisión es, como en toda campaña anterior,
el gate real de FRAMEWORK.md vía `backtest.simulate_v3` completo.

Requiere `data/raw/` poblado (mismo requisito que las campañas anteriores).
BLOQUEADO en este sandbox (HTTP 451, data/raw/ vacío) — validado acá solo
estructuralmente, ver research/tests/test_gestion_campaign_trailing_distance.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_trailing_distance.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_trailing_distance.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
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
BE_ANCHOR = 1.0          # V3-A, congelado — no es la variable bajo prueba
ACTIVATION_ANCHOR = 2.0  # V3-A, congelado — no es la variable bajo prueba
ATR_MULT_ANCHOR = 1.5    # ancla de H1 (ya cerrada), congelado

DISTANCE_ANCHOR = 1.0
DISTANCE_VALUES_BASE = (0.5, 0.75, 1.0, 1.5)
DISTANCE_EXT_UPPER = 1.25
DISTANCE_EXT_LOWER = 0.25

CANDIDATES = tuple(
    str(v) for v in DISTANCE_VALUES_BASE + (DISTANCE_EXT_UPPER, DISTANCE_EXT_LOWER)
)
EXIT_CONFIG_LABEL = "H2.1 anchor (be=1.0R/activation=2.0R, distance variable)"

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision


def _label(distance: float) -> str:
    return str(distance)


def _exit_cfg(distance: float) -> dict:
    return {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": distance}


# --------------------------------------------------------------------------- #
# Reglas de contingencia (pre-especificadas 2026-07-30)                      #
# --------------------------------------------------------------------------- #
def _no_deterioration(m_candidate: dict | None, m_anchor: dict | None) -> bool:
    """Regla 1 (límite superior): 'sin deterioro' respecto al ancla en NINGUNA
    de las 4 métricas de gate_check() — pf, max_dd, exp_r, freq — no una
    métrica aislada. Ajustado 2026-07-30 a pedido explícito: una mejora
    puntual de PF acompañada de deterioro en otra métrica NO dispara la
    extensión."""
    if m_candidate is None or m_anchor is None:
        return False
    return (
        m_candidate["pf"] >= m_anchor["pf"]
        and m_candidate["max_dd"] >= m_anchor["max_dd"]
        and m_candidate["exp_r"] >= m_anchor["exp_r"]
        and m_candidate["freq"] >= m_anchor["freq"]
    )


def _is_lower_extreme_best(metrics_by_distance: dict[float, dict | None]) -> bool:
    """Regla 2 (límite inferior): distance=0.5 tiene el mejor PF (o empatado)
    de todo el barrido base — ranking por PF en solitario, misma métrica de
    selección entre variantes que ya usa FRAMEWORK.md; propósito distinto de
    la Regla 1 (extremo del rango, no detección de confusión)."""
    valid = {d: m for d, m in metrics_by_distance.items() if m is not None}
    if DISTANCE_VALUES_BASE[0] not in valid or len(valid) < 2:
        return False
    pf_lower = valid[DISTANCE_VALUES_BASE[0]]["pf"]
    return all(
        pf_lower >= m["pf"] for d, m in valid.items() if d != DISTANCE_VALUES_BASE[0]
    )


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _run_distance(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
                   distance: float) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, _exit_cfg(distance), cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, distance: float, entries: list[dict],
          trades: pd.DataFrame, m: dict | None, triggered_by: str | None) -> dict:
    return {
        "asset": asset, "year": year, "candidate": _label(distance),
        "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "triggered_by": triggered_by,
    }


def run_asset_year(asset: str, year: int) -> list[dict]:
    """Corre el rango base de `distance` para un (activo, año), sobre el
    MISMO frame y las MISMAS entradas (entries no dependen de `distance` —
    invarianza estructural, ver docstring del módulo). Evalúa las dos reglas
    de contingencia sobre el resultado base y, si alguna dispara, corre el
    valor de extensión correspondiente para este mismo (activo, año)."""
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)

    rows = []
    metrics_by_distance: dict[float, dict | None] = {}
    for distance in DISTANCE_VALUES_BASE:
        trades, m = _run_distance(frame, cfg, entries, distance)
        metrics_by_distance[distance] = m
        rows.append(_row(asset, year, distance, entries, trades, m, triggered_by=None))

    if _no_deterioration(metrics_by_distance[1.5], metrics_by_distance[DISTANCE_ANCHOR]):
        trades, m = _run_distance(frame, cfg, entries, DISTANCE_EXT_UPPER)
        rows.append(_row(asset, year, DISTANCE_EXT_UPPER, entries, trades, m,
                          triggered_by="upper_contingency"))

    if _is_lower_extreme_best(metrics_by_distance):
        trades, m = _run_distance(frame, cfg, entries, DISTANCE_EXT_LOWER)
        rows.append(_row(asset, year, DISTANCE_EXT_LOWER, entries, trades, m,
                          triggered_by="lower_contingency"))

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
    """Fase 3 (2024, ciego). Requiere `candidate` (un valor de distance, como
    string, ej. "0.75") ya congelado tras decidir con 2022+2023 — mismo
    guardrail que toda campaña anterior. No evalúa reglas de contingencia acá
    (esas son exclusivas de la fase exploratoria 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un distance ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    distance = float(candidate)
    results: list[dict] = []
    for asset in assets:
        df_full = trigger_camp.load_asset_year(asset, BLIND_YEAR)
        cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
        trades, m = _run_distance(frame, cfg, entries, distance)
        results.append(_row(asset, BLIND_YEAR, distance, entries, trades, m, triggered_by=None))
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
            "gate_pass": r["gate_pass"], "triggered_by": r["triggered_by"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN H2.1 — distancia de trailing bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/be=1.0R/activation=2.0R fijos\n{'='*100}")
    cols = ["asset", "year", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout",
            "gate_pass", "triggered_by"]
    print(df[cols].to_string(index=False))

    triggered = df[df["triggered_by"].notna()]
    print(f"\n{'-'*100}\n  Extensiones por regla de contingencia disparadas:\n{'-'*100}")
    if triggered.empty:
        print("  Ninguna — el rango base {0.5, 0.75, 1.0, 1.5} no disparó ninguna de las "
              "dos reglas pre-especificadas en ningún (activo, año).")
    else:
        print(triggered[["asset", "year", "candidate", "triggered_by", "pf", "max_dd",
                          "exp_r", "freq"]].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ningún distance del rango probado "
              "(incluidas extensiones) demuestra evidencia suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Mismo formato que las campañas anteriores (reutiliza summarize_decision
    sin modificarlo)."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ningún distance en {CANDIDATES} demuestra evidencia suficiente "
                  f"para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo be={BE_ANCHOR}R/"
                  f"activation={ACTIVATION_ANCHOR}R fijos — independientemente de cuál haya "
                  f"tenido mejor PF relativo. H2.1 queda sin evidencia suficiente para este "
                  f"activo con este rango.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="distance ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el distance ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_trailing_distance_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "gestion_campaign_trailing_distance_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
