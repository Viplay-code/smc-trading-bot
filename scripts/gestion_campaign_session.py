#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_session.py — Campaña de validación empírica
Gestión: ventana de sesión (`Config.sessions`), bajo Trigger=T1_ema_cross
fijo, sobre la infraestructura de scripts/bias_campaign.py y
scripts/trigger_campaign.py.

Hipótesis (H1) a falsificar: existe una ventana de sesión más amplia que la
actual (07-11+13-17, 8h) que, sin modificar ningún otro parámetro, permite
que al menos una combinación (activo, ventana, exit_config) supere los 4
gates de FRAMEWORK.md en 2022 Y 2023 para ese activo — cerrando la brecha de
frecuencia que la campaña de `atr_mult` (2026-07-28) confirmó con datos
reales: 0/48 filas con freq≥6, y prácticamente invariante entre valores de
atr_mult (medias 4.92-5.03) — evidencia de que Gestión (lo que ocurre
DESPUÉS de abrir un trade) no puede mover ese gate por construcción.

Candidatos (acordados 2026-07-29, ninguno inventado):
  - control_8h: [(7,11),(13,17)] — la ventana de producción actual, ancla
    obligatoria de comparación.
  - dcv1_activo_15h: [(7,22)] — unión de las 3 categorías "de mercado
    activo" que `dc_v1.pipeline::_classify_session` ya calcula y valida
    (`london` 07-13, `overlap` 13-16, `ny` 16-22; excluye solo `off`).
  - sin_filtro_24h: [(0,24)] — techo matemático del espacio de parámetros;
    no existe una ventana más ancha, así que si acá tampoco se alcanza
    freq≥6 la hipótesis de sesión queda falsificada por completo, no por
    falta de rango.
Las 3 ventanas están anidadas por construcción: control_8h ⊂
dcv1_activo_15h ⊂ sin_filtro_24h.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no
A_sweep_bos), Entry=C_market_close, `atr_mult`=1.5 (el valor de
especificación original — la campaña de Gestión/atr_mult no produjo un
ganador que congelar, así que se revierte al valor de referencia en vez de
elegir uno arbitrariamente entre los 4 probados), `atr_period`=14,
`be`/`activation`/`distance` (V3-A y V3-B en paralelo, no es la variable
bajo prueba), `max_hold`=20, `risk`=0.005, una-posición-a-la-vez, datasets
dc_v1 canónicos, disciplina P-3, modelo de costos, gates literales.

Verificación de acoplamiento (2026-07-29) — MÁS FUERTE que la de
`atr_mult`, porque acá se pudo probar por dos vías independientes. Ambas
corren desde `_build_windows_and_verify`, punto único de verificación
compartido por `run_asset_year` (2022/2023) y `run_blind_test` (2024) — una
violación en CUALQUIERA de las dos rutas de ejecución real lanza
`AssertionError` sin capturar, antes de calcular ninguna métrica, y termina
la corrida (no son solo tests unitarios, ver
research/tests/test_gestion_campaign_session.py::test_run_blind_test_also_runs_sanity_checks):

1. `sessions` no está en la firma de `trigger_T1_ema_cross` en ningún
   punto — la detección del cruce corre sobre la serie completa, ajena a
   sesión. El conteo de eventos CRUDOS debe ser IDÉNTICO (no solo
   monótono) entre las 3 ventanas — `assert_raw_events_session_invariant`
   lo verifica en cada corrida real.
2. `n_entries` (post filtro de bias/sesión, calculado por
   `find_entries_for_trigger`) SÍ depende de `in_session`, pero es
   monótono no decreciente por una razón demostrable: como las 3 ventanas
   están anidadas, todo evento que pasa el filtro con la ventana angosta
   también pasa con las más anchas (el chequeo de bias/dirección es
   idéntico en las 3, ajeno a `sessions`) — el conjunto de eventos
   aceptados de la ventana angosta es subconjunto exacto del de la
   ventana ancha. `assert_n_entries_monotonic` lo verifica en cada corrida
   real.

IMPORTANTE — lo que NO se afirma: `n_trades` (post "una posición a la
vez", calculado por `backtest.run_config`) NO hereda esa garantía. La regla
de concurrencia es un proceso "greedy causal" sobre entradas cuya duración
de operación es variable y depende de los datos (`simulate_v3` sale cuando
el precio toca el stop, no en un punto fijo) — una entrada nueva, habilitada
solo por ampliar la ventana, puede tener una duración larga que bloquee DOS
O MÁS entradas que antes se ejecutaban por separado, y `n_trades` puede
bajar aunque `n_entries` suba (contraejemplo numérico verificado 2026-07-29,
ver conversación de diseño). Por eso `note_concurrency_effects` reporta,
como información y no como error, cualquier (activo, año, exit_config) donde
`n_trades` no acompañe el crecimiento garantizado de `n_entries` — es
evidencia real sobre cuándo la concurrencia se vuelve una restricción
activa, no un bug.

Reutilización de infraestructura (sin modificar ninguno de los tres): de
scripts/bias_campaign.py — `to_backtest_frame` (ya genérico sobre
`cfg.sessions`), `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year` (Bias=A ya resuelto),
`_raw_events`/`find_entries_for_trigger`. La columna "candidate" identifica
acá la ventana de sesión probada (control_8h/dcv1_activo_15h/sin_filtro_24h).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_gestion_campaign_session.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_session.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_session.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
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
NESTED_ORDER = ("control_8h", "dcv1_activo_15h", "sin_filtro_24h")
SESSION_WINDOWS = {
    "control_8h": [(7, 11), (13, 17)],
    "dcv1_activo_15h": [(7, 22)],
    "sin_filtro_24h": [(0, 24)],
}
CANDIDATES = NESTED_ORDER

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"
ATR_MULT_FIXED = 1.5  # valor de especificación original, sin ganador que congelar tras atr_mult

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision


def _cfg_for(label: str) -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_FIXED, sessions=SESSION_WINDOWS[label])


# --------------------------------------------------------------------------- #
# Verificación de acoplamiento sessions <-> Trigger (sanity-checks empíricos) #
# --------------------------------------------------------------------------- #
def assert_raw_events_session_invariant(raw_counts: dict[str, int], asset: str, year: int) -> None:
    """`sessions` no está en la firma de trigger_T1_ema_cross — los eventos
    crudos deben ser IDÉNTICOS entre las 3 ventanas, no solo monótonos."""
    distinct = set(raw_counts.values())
    if len(distinct) != 1:
        raise AssertionError(
            f"`sessions` afectó el conteo de eventos crudos de {TRIGGER_CANDIDATE} para "
            f"{asset}/{year} ({raw_counts}) — contradice que `sessions` no forma parte de "
            f"la firma de trigger_T1_ema_cross. Investigar antes de tratar esta campaña "
            f"como un experimento puro de ventana horaria."
        )


def assert_n_entries_monotonic(n_entries_by_window: dict[str, int], asset: str, year: int) -> None:
    """control_8h ⊆ dcv1_activo_15h ⊆ sin_filtro_24h como conjuntos de horas
    habilitadas -> n_entries debe ser monótonamente no decreciente en ese
    orden (demostración formal: ver docstring del módulo). NO se afirma lo
    mismo de n_trades (ver docstring) — esa garantía se rompe por diseño
    con la regla de una-posición-a-la-vez + duración de operación variable,
    y por eso no se verifica acá."""
    counts = [n_entries_by_window[label] for label in NESTED_ORDER]
    if not (counts[0] <= counts[1] <= counts[2]):
        raise AssertionError(
            f"n_entries no es monótono para {asset}/{year} entre ventanas anidadas "
            f"{NESTED_ORDER}: {dict(zip(NESTED_ORDER, counts))} — contradice la "
            f"demostración formal de que in_session es una máscara monótona sobre "
            f"eventos ya detectados. Investigar antes de continuar."
        )


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _build_windows_and_verify(
    df_full: pd.DataFrame, asset: str, year: int,
) -> dict[str, tuple[pd.DataFrame, "backtest.Config", list]]:
    """Construye un frame por ventana (in_session es lo único que cambia
    entre ellos; se reconstruye completo por simplicidad, no por necesidad)
    y corre AMBOS sanity-checks antes de devolver nada — punto único de
    verificación reutilizado por run_asset_year (2022/2023) y
    run_blind_test (2024), para que ninguna de las dos rutas de ejecución
    real pueda saltárselos. Las 3 ventanas se computan siempre, incluso en
    --blind donde solo se usan las entradas de la ventana congelada, porque
    los sanity-checks son comparativos (necesitan las 3 para verificar
    invarianza/monotonicidad) y 2024 es un dataset real distinto de
    2022/2023 — vale la pena re-verificar la propiedad ahí también."""
    frames: dict[str, tuple[pd.DataFrame, "backtest.Config"]] = {}
    raw_counts: dict[str, int] = {}
    entries_by_window: dict[str, list] = {}
    for label in NESTED_ORDER:
        cfg = _cfg_for(label)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        frames[label] = (frame, cfg)
        raw_counts[label] = len(trigger_camp._raw_events(frame, TRIGGER_CANDIDATE, cfg))
        entries_by_window[label] = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)

    assert_raw_events_session_invariant(raw_counts, asset, year)
    assert_n_entries_monotonic({k: len(v) for k, v in entries_by_window.items()}, asset, year)

    return {label: (frames[label][0], frames[label][1], entries_by_window[label]) for label in NESTED_ORDER}


def run_asset_year(asset: str, year: int) -> list[dict]:
    """Corre las 3 ventanas de sesión × ambas configs de salida para un
    (activo, año), sobre lo ya verificado por _build_windows_and_verify."""
    df_full = trigger_camp.load_asset_year(asset, year)
    windows = _build_windows_and_verify(df_full, asset, year)

    rows = []
    for label in NESTED_ORDER:
        frame, cfg, entries = windows[label]
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            rows.append({
                "asset": asset, "year": year, "candidate": label,
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
    """Fase 3 (2024, ciego). Requiere `candidate` (una ventana de sesión, ej.
    "dcv1_activo_15h") ya congelada tras decidir con 2022+2023. Pasa por
    _build_windows_and_verify igual que run_asset_year — ambos
    sanity-checks corren también acá, sobre 2024, antes de calcular
    ninguna métrica, aunque solo se usen las entradas de la ventana
    congelada para el resultado."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere una ventana ya congelada {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    results: list[dict] = []
    for asset in assets:
        df_full = trigger_camp.load_asset_year(asset, BLIND_YEAR)
        windows = _build_windows_and_verify(df_full, asset, BLIND_YEAR)
        frame, cfg, entries = windows[candidate]
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
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def note_concurrency_effects(df: pd.DataFrame) -> None:
    """Informativo, NO un error: reporta cuándo n_trades no acompaña el
    crecimiento (garantizado) de n_entries entre ventanas anidadas — efecto
    esperado de una-posición-a-la-vez + duración de operación variable (ver
    docstring del módulo), no un bug de la campaña."""
    flagged = []
    for (asset, year, exit_config), g in df.groupby(["asset", "year", "exit_config"]):
        g = g.set_index("candidate").reindex(NESTED_ORDER)
        trades = g["n_trades"]
        if trades.isna().any():
            continue
        if not (trades.iloc[0] <= trades.iloc[1] <= trades.iloc[2]):
            flagged.append((asset, year, exit_config, dict(zip(NESTED_ORDER, trades.tolist()))))

    if flagged:
        print(f"\n{'-'*100}\n  Nota (no es un error): n_trades no acompañó el crecimiento garantizado de "
              f"n_entries en estos casos — consistente con una-posición-a-la-vez + duración de "
              f"operación variable, no con un fallo de la campaña:\n{'-'*100}")
        for asset, year, exit_config, trades in flagged:
            print(f"  {asset} {year} {exit_config}: {trades}")


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN — ventana de sesión bajo Trigger=T1_ema_cross, "
          f"Bias=A, Entry=C_market_close y atr_mult=1.5 fijos\n{'='*100}")
    cols = ["asset", "year", "candidate", "exit_config", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ninguna ventana de sesión probada "
              "demuestra evidencia suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))

    note_concurrency_effects(df)


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna ventana de sesión en {CANDIDATES} demuestra evidencia "
                  f"suficiente para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo Trigger="
                  f"{TRIGGER_CANDIDATE} — dado que sin_filtro_24h es el techo matemático del "
                  f"espacio de parámetros, esto descarta la ventana horaria como explicación "
                  f"completa en este activo (no por falta de rango). Si dcv1_activo_15h o "
                  f"sin_filtro_24h superaron el techo de 12 mientras control_8h seguía bajo el "
                  f"piso de 6, la rama ya declarada es descomponer en london/overlap/ny "
                  f"individuales para buscar la sub-ventana mínima suficiente, no ampliar el "
                  f"rango de nuevo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="Ventana de sesión ya congelada para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (la ventana ya congelada)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_session_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "gestion_campaign_session_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
