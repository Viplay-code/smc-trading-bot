#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/trigger_entry_campaign_rama_b.py — Rama B (Trigger/Entry), diseño
científico acordado 2026-08-13 (revisión estratégica global + análisis
formal de Value of Information). Evalúa si el techo de PF (~1.0-1.5)
observado en las 11 líneas experimentales previas del programa (H1, H2.1-3,
I1, Espacio 3, Espacio 2, `atr_mult`×sesión, Espacio 4, G/G×sesión,
Espacio 1 — todas con Trigger=T1_ema_cross/Entry=C_market_close fijos)
pertenece específicamente a ese par, o si es transversal a Trigger/Entry.

Dos celdas ÚNICAMENTE — sin celda `D_range_breakout`+`A_pullback_50`
(aclarado explícitamente en el diseño aprobado, ver ajuste 1 del
2026-08-13): `entry_A_pullback_50` requiere `event.meta["bos_level"]`, que
solo produce la familia Sweep+BOS — `trigger_D_range_breakout` emite
`meta={}` (misma incompatibilidad estructural ya documentada para T1 en el
cierre de Espacio 4, verificada en código y por test —
`research/tests/test_layers.py::test_range_breakout_incompatible_with_pullback_entry`):
  - **Trigger `D_range_breakout` + Entry `C_market_close`**: aísla el efecto
    de Trigger, con Entry fijo en el candidato ya extensamente caracterizado
    en el resto del programa.
  - **Trigger `A_sweep_bos` + Entry `A_pullback_50`**: aísla el efecto de
    Entry, con Trigger fijo en `A_sweep_bos` — comparable directamente contra
    `A_sweep_bos`+`C_market_close` bajo `dcv1_activo_15h`, ya publicado en
    Espacio 3 (`trigger_campaign_sweep_bos_session_results.csv`).

IMPORTANTE (ajuste 1, 2026-08-13): este diseño permite evaluar los efectos
de Trigger y de Entry POR SEPARADO mediante las dos comparaciones
controladas de arriba. NO permite estimar ni afirmar una interacción
Trigger×Entry — eso exigiría la celda `D_range_breakout`+`A_pullback_50`,
que no existe (incompatibilidad estructural, no una omisión). Ningún
resultado de esta campaña debe interpretarse como evidencia de interacción
Trigger×Entry.

Criterios de éxito (ajuste 2, 2026-08-13) — NO se define éxito como
"PF > el de T1+C" en una sola celda. Ver `assess_pf_ceiling_signal()`, que
distingue explícitamente:
  - Nivel 1 — mejora puntual: una sola celda (activo, año) mejora.
  - Nivel 2 — mejora consistente: dirección favorable en 2022 Y 2023 para
    al menos un activo, o en la mayoría de los activos dentro de un año —
    sin gate de magnitud (mismo estándar ya usado en G×sesión).
  - Nivel 3 — cambio de techo: dirección favorable simultáneamente en los 3
    activos Y los 2 años, y de una magnitud que acerque sustancialmente más
    el candidato al gate de PF≥1.50 que la banda histórica ya observada bajo
    T1+C (~1.0-1.5) — no solo un desplazamiento marginal.
  - Nivel 4 — gate: supera los 4 criterios originales de FRAMEWORK.md
    (`gate_check`/`summarize_decision`, sin modificar) y sobrevive 2022 Y
    2023.
  Ningún nivel se infiere automáticamente de otro; el resultado se evalúa
  siempre por (activo, año) explícito, sin seleccionar el mejor punto
  después de observar los resultados.

Fijo durante toda la campaña (ninguno de estos elementos se varía ni se
modifica su implementación — congelado según el diseño aprobado): Bias=A,
sesión=`dcv1_activo_15h` única, Gestión V3-A ancla (`be`=1.0R/
`activation`=2.0R/`distance`=1.0R), `atr_mult`=1.5, `atr_period`=14,
`max_hold`=20, `risk`=0.005, BTCUSDT/ETHUSDT/SOLUSDT, 2022+2023 (2024
permanece ciego, no se toca), gates literales de FRAMEWORK.md,
`gate_check`/`summarize_decision` reutilizados por identidad. Sin V3-B en
paralelo. No se implementa ni se evalúa ningún otro candidato de Trigger o
Entry además de los dos de arriba (Trigger B/C de la familia Sweep+BOS,
Entry B quedan fuera de alcance).

Verificación de integridad (Fase A) — diseño distinto a toda campaña
anterior, porque NINGUNA de las 2 celdas objetivo tiene antecedente
histórico bajo NINGUNA sesión (`D_range_breakout` es un candidato
completamente nuevo; `A_sweep_bos`+`A_pullback_50` solo tiene un antecedente
de muestra insuficiente bajo `control_8h`, nunca bajo `dcv1_activo_15h`).
Por eso la Fase A no verifica ninguna de las 2 celdas objetivo directamente
— verifica la infraestructura COMPARTIDA por ambas: se computa la celda
auxiliar `A_sweep_bos`+`C_market_close` bajo `dcv1_activo_15h` (mismo frame/
Bias/sesión/eventos crudos de `A_sweep_bos`/filtro genérico de entradas que
usa la celda objetivo `A_sweep_bos`+`A_pullback_50`, y el mismo frame/Bias/
sesión/filtro genérico de entradas que usa `D_range_breakout`+`C_market_
close`) y se compara EXACTO contra el resultado ya publicado en Espacio 3
(`trigger_campaign_sweep_bos_session_results.csv`, role="candidate",
candidate="dcv1_activo_15h"). Si esta verificación pasa, confirma que el
pipeline compartido es correcto — dando base para confiar en las 2 celdas
objetivo, que reutilizan ese mismo pipeline sin ninguna lógica adicional
específica de Trigger. 6 verificaciones totales (una por combinación
activo/año), comparación NaN-consciente (ETHUSDT/2023 es no-computable en la
referencia de Espacio 3). Si CUALQUIERA falla, `AssertionError` inmediato
con celda/activo/año/referencia/métrica/esperado/obtenido — la corrida
aborta antes de calcular las 2 celdas objetivo.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de `scripts/bias_campaign.py` —
`load_asset_year` (vía `trigger_camp`), `to_backtest_frame`, `gate_check`,
`summarize_decision`. De `scripts/trigger_campaign.py` — `load_asset_year`
(fija Bias=A). De `scripts/gestion_campaign_session.py` — `SESSION_WINDOWS`.
De `scripts/entry_campaign_sweep_bos.py` — `find_entries_for_entry`
(reutilizada LITERAL: ya es agnóstica al Trigger que produjo los eventos
crudos — los recibe como parámetro — sin ninguna lógica específica de T1 a
diferencia de `trigger_campaign.py::find_entries_for_trigger`, que sí tiene
un dispatch con una rama especial para T1). De `research.TRIGGER_LAYERS` —
`A_sweep_bos` (ya registrado) y `D_range_breakout` (nuevo, implementado en
`research/layers.py`, Rama B).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción real
sobre `trigger_campaign_sweep_bos_session_results.csv` (ya committeado, no
requiere data/raw/), ver
research/tests/test_trigger_entry_campaign_rama_b.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/trigger_entry_campaign_rama_b.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/trigger_entry_campaign_rama_b.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import research
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
import scripts.entry_campaign_sweep_bos as entry_sweep_bos
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"              # fijado en trigger_camp.load_asset_year, no parametrizado acá
SESSION_LABEL = "dcv1_activo_15h"  # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — ya evaluado y falsificado en Espacio 2
BE_ANCHOR = 1.0            # V3-A, congelado
ACTIVATION_ANCHOR = 2.0    # V3-A, congelado
DISTANCE_ANCHOR = 1.0      # V3-A, congelado
EXIT_CFG = {"be": BE_ANCHOR, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}

# Los DOS combos de Rama B — sin celda D_range_breakout+A_pullback_50, ver
# docstring del módulo. Orden fijo, sin agregar ni quitar nada acá.
COMBOS: tuple[tuple[str, str], ...] = (
    ("D_range_breakout", "C_market_close"),
    ("A_sweep_bos", "A_pullback_50"),
)


def _label(trigger_name: str, entry_name: str) -> str:
    return f"{trigger_name} + {entry_name}"


CANDIDATES = tuple(_label(t, e) for t, e in COMBOS)

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Rama B — Trigger/Entry (Bias=A/Gestión V3-A ancla/atr_mult=1.5/"
    "atr_period=14/max_hold=20/risk=0.005 fijos; sesión=dcv1_activo_15h "
    "única; Trigger y Entry variables, sin celda D_range_breakout + "
    "A_pullback_50 — incompatibilidad estructural, no interacción evaluable)"
)

# Referencia de Fase A — celda AUXILIAR (A_sweep_bos + C_market_close bajo
# dcv1_activo_15h), NO una de las 2 celdas objetivo. Ver docstring, sección
# "Verificación de integridad".
_SWEEP_BOS_SESSION_REF_PATH = "trigger_campaign_sweep_bos_session_results.csv"
_SWEEP_BOS_SESSION_REF_EXIT_CONFIG = (
    "Espacio 3 — A_sweep_bos (V3-A anchor: be=1.0R/activation=2.0R/"
    "distance=1.0R, session variable)"
)
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _frame_for_asset_year(asset: str, year: int):
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                           max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    return frame, cfg


def _run_combo(frame: pd.DataFrame, cfg: "backtest.Config", trigger_name: str, entry_name: str):
    """Genera los eventos crudos del Trigger indicado directamente desde
    `research.TRIGGER_LAYERS` (sin ningún dispatch especial por nombre) y
    reutiliza `entry_sweep_bos.find_entries_for_entry` — que ya es agnóstica
    al Trigger que produjo esos eventos (los recibe como parámetro) — para
    aplicar el filtro de bias/sesión/riesgo degenerado y calcular el precio
    de entrada. Ninguna rama de este código depende de qué Trigger se pasó."""
    raw_events = research.TRIGGER_LAYERS[trigger_name](frame)
    entries = entry_sweep_bos.find_entries_for_entry(frame, cfg, raw_events, entry_name)
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return entries, trades, m


def _row(asset: str, year: int, trigger_name: str, entry_name: str,
         entries: list[dict], trades: pd.DataFrame, m: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "trigger": trigger_name, "entry": entry_name,
        "candidate": _label(trigger_name, entry_name), "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad del pipeline COMPARTIDO (6 checks)      #
# --------------------------------------------------------------------------- #
def _sweep_bos_dcv1_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_SWEEP_BOS_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["role"] == "candidate") & (df["candidate"] == SESSION_LABEL)
               & (df["exit_config"] == _SWEEP_BOS_SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=A_sweep_bos + C_market_close "
            f"(verificación), activo={asset}, año={year} en {_SWEEP_BOS_SESSION_REF_PATH} — "
            f"no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _values_match(actual, expected) -> bool:
    """Comparación NaN-consciente: ETHUSDT/2023 es no-computable en la
    referencia de Espacio 3 (NaN != NaN normalmente), mismo criterio ya
    usado en el cierre de Espacio 3."""
    if pd.isna(actual) and pd.isna(expected):
        return True
    return actual == expected


def _verify_against(cell_label: str, asset: str, year: int, ref_name: str,
                     n_entries: int, n_trades: int, m: dict | None,
                     ref_row: pd.Series) -> None:
    mismatches = []
    if not _values_match(n_entries, ref_row["n_entries"]):
        mismatches.append(f"n_entries: esperado={ref_row['n_entries']!r}, obtenido={n_entries!r}")
    if not _values_match(n_trades, ref_row["n_trades"]):
        mismatches.append(f"n_trades: esperado={ref_row['n_trades']!r}, obtenido={n_trades!r}")
    for field in _CHECK_FIELDS:
        expected = ref_row[field]
        actual = m.get(field) if m else None
        if not _values_match(actual, expected):
            mismatches.append(f"{field}: esperado={expected!r}, obtenido={actual!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (verificación de integridad del pipeline compartido) falló — "
            f"celda={cell_label}, activo={asset}, año={year}, referencia={ref_name}:\n  "
            + "\n  ".join(mismatches) +
            f"\nLa corrida aborta antes de calcular las 2 celdas objetivo de Rama B."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A para un (activo, año) — 1 de las 6 verificaciones totales de
    la campaña. Verifica ÚNICAMENTE la celda auxiliar A_sweep_bos+
    C_market_close (NO ninguna de las 2 celdas objetivo, que carecen de
    antecedente histórico bajo cualquier sesión). Devuelve frame/cfg
    (compartidos con Fase B) tras verificar. Revienta con AssertionError si
    la verificación falla."""
    frame, cfg = _frame_for_asset_year(asset, year)
    entries, trades, m = _run_combo(frame, cfg, "A_sweep_bos", "C_market_close")
    ref = _sweep_bos_dcv1_reference(asset, year)
    _verify_against("A_sweep_bos + C_market_close (verificación de pipeline compartido)",
                     asset, year, _SWEEP_BOS_SESSION_REF_PATH, len(entries), len(trades), m, ref)
    return frame, cfg


# --------------------------------------------------------------------------- #
# Fase B — las 2 celdas objetivo (solo tras Fase A completa sin excepción)    #
# --------------------------------------------------------------------------- #
def run_asset_year_targets(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config") -> list[dict]:
    rows: list[dict] = []
    for trigger_name, entry_name in COMBOS:
        entries, trades, m = _run_combo(frame, cfg, trigger_name, entry_name)
        rows.append(_row(asset, year, trigger_name, entry_name, entries, trades, m))
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa para las 6 combinaciones
    (activo, año) ANTES de que arranque la Fase B — si run_integrity_check
    revienta en cualquier combinación, la excepción se propaga acá y la
    función nunca llega a calcular ninguna de las 2 celdas objetivo. NO
    incluye 2024 — ver run_blind_test."""
    known: dict[tuple[str, int], tuple] = {}
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg = known[(asset, year)]
            rows.extend(run_asset_year_targets(asset, year, frame, cfg))  # Fase B
    return rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (string compuesto
    "{trigger} + {entry}") ya congelado tras decidir con 2022+2023. No corre
    Fase A acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    trigger_name, entry_name = (p.strip() for p in candidate.split("+"))
    results: list[dict] = []
    for asset in assets:
        frame, cfg = _frame_for_asset_year(asset, BLIND_YEAR)
        entries, trades, m = _run_combo(frame, cfg, trigger_name, entry_name)
        results.append(_row(asset, BLIND_YEAR, trigger_name, entry_name, entries, trades, m))
    return results


# --------------------------------------------------------------------------- #
# Criterio de éxito (ajuste 2, 2026-08-13) — 4 niveles explícitos, ninguno    #
# se infiere automáticamente de otro                                         #
# --------------------------------------------------------------------------- #
# Banda histórica de PF ya observada bajo T1_ema_cross+C_market_close en las
# 11 líneas experimentales previas del programa (H1 a Espacio 1) — literal,
# no recalculada acá. Ver FRAMEWORK.md para el detalle campaña por campaña.
HISTORICAL_T1_C_PF_BAND = (1.0, 1.5)


def assess_pf_ceiling_signal(df: pd.DataFrame) -> dict:
    """Evalúa, POR CANDIDATO, los 4 niveles del criterio de éxito acordado
    2026-08-13 — sin seleccionar el mejor punto después de observar los
    resultados: cada nivel se computa sobre TODAS las celdas del candidato,
    no sobre la celda más favorable.

    Nivel 1 (mejora puntual): al menos una celda (activo, año) con PF por
    encima del techo histórico superior (1.5) — reportado, no interpretado
    como suficiente.
    Nivel 2 (mejora consistente): PF por encima de 1.5 en 2022 Y 2023 para
    al menos un activo, SIN gate de magnitud adicional.
    Nivel 3 (cambio de techo): PF por encima de 1.5 simultáneamente en los 3
    activos Y los 2 años — el estándar más alto de dirección, análogo a las
    "13 combinaciones" de Espacio 1.
    Nivel 4 (gate): resultado de gate_check/summarize_decision sin
    modificar — supervivencia 2022 Y 2023.
    """
    upper = HISTORICAL_T1_C_PF_BAND[1]
    out = {}
    for candidate in df["candidate"].unique():
        sub = df[df["candidate"] == candidate]
        nivel1 = sub[sub["pf"] > upper]
        piv = sub.pivot_table(index="asset", columns="year", values="pf")
        nivel2_por_activo = {}
        for asset in piv.index:
            vals = piv.loc[asset].dropna()
            nivel2_por_activo[asset] = bool((vals > upper).all()) if len(vals) == 2 else False
        nivel2 = any(nivel2_por_activo.values())
        nivel3 = all(nivel2_por_activo.get(a, False) for a in piv.index) and len(piv.index) == 3
        out[candidate] = {
            "nivel1_mejora_puntual": {"n_celdas": int(len(nivel1)),
                                       "celdas": nivel1[["asset", "year", "pf"]].to_dict("records")},
            "nivel2_mejora_consistente": {"por_activo": nivel2_por_activo, "alcanzado": nivel2},
            "nivel3_cambio_de_techo": {"alcanzado": nivel3},
        }
    return out


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
            "asset": r["asset"], "year": r["year"], "trigger": r["trigger"], "entry": r["entry"],
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
    print(f"\n{'='*100}\n  Rama B — Trigger/Entry: D_range_breakout+C_market_close vs "
          f"A_sweep_bos+A_pullback_50\n  Bias=A/Gestión V3-A ancla/sesión=dcv1_activo_15h única "
          f"fijos\n{'='*100}")
    cols = ["asset", "year", "trigger", "entry", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (Nivel 4, por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_ceiling_assessment(assessment: dict) -> None:
    print(f"\n{'='*100}\n  Criterio de éxito (4 niveles, ajuste 2026-08-13) — por candidato\n{'='*100}")
    for candidate, levels in assessment.items():
        print(f"\n  {candidate}:")
        print(f"    Nivel 1 (mejora puntual): {levels['nivel1_mejora_puntual']['n_celdas']} celda(s) "
              f"con PF>{HISTORICAL_T1_C_PF_BAND[1]}")
        print(f"    Nivel 2 (mejora consistente, por activo): {levels['nivel2_mejora_consistente']['por_activo']}"
              f" -> alcanzado: {levels['nivel2_mejora_consistente']['alcanzado']}")
        print(f"    Nivel 3 (cambio de techo, 3 activos x 2 años): "
              f"{levels['nivel3_cambio_de_techo']['alcanzado']}")


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Nivel 4 — DECISIÓN: sobrevivientes (ambos años, por activo) y ranking "
          f"por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación Trigger+Entry demuestra evidencia "
                  f"suficiente para cumplir los 4 gates de FRAMEWORK.md en 2022+2023.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado ('{trigger} + {entry}') para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "trigger_entry_campaign_rama_b_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "trigger_entry_campaign_rama_b_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 2 combos x 3 activos x 2 "
          f"años = 12, todas genuinamente nuevas)")

    assessment = assess_pf_ceiling_signal(df)
    print_ceiling_assessment(assessment)

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "trigger_entry_campaign_rama_b_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
