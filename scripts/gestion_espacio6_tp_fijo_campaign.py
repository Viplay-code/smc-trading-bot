#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_espacio6_tp_fijo_campaign.py — Espacio 6, Experimento 1:
mecanismo de salida "TP fijo 2.5R" contra el comparador V3-A, bajo un
contrato en todo lo demás idéntico al ya usado por Bias B y Trigger C.
Contrato final aprobado 2026-08-25 (`docs/research/EXPERIMENTAL_ROADMAP.md`,
"Espacio 6").

Encuadre (obligatorio, ver contrato §0): `tp_r`=2.5 proviene de la
especificación histórica/original documentada en la sección "Gestión (fija
para todas las variantes)" de `FRAMEWORK.md`. **Esto NO representa la
Gestión actualmente utilizada por el motor real del programa** — V3-A es
la Gestión empírica vigente (única usada en H1/H2/I1/Espacio 1/Bias B/
Trigger C). Este experimento NO se describe ni se interpreta como
"restaurar la gestión original"; es un mecanismo alternativo de salida,
elegido por ser determinista, reproducible y mecánicamente distinto de
V3-A — el origen documental del valor numérico (2.5R) es una coincidencia
útil para no inventar un valor arbitrario, no una justificación conceptual
del experimento.

Pregunta científica (separada del criterio de PASS, ver contrato §1):
¿cambiar el mecanismo de salida de V3-A a TP fijo 2.5R cambia materialmente
la calidad de la estrategia (PF, expectancy, DD, distribución de
resultados), bajo el resto del contrato congelado? Esto es distinto de la
pregunta "¿pasa los gates?" — un candidato puede mejorar PF/expectancy/DD
sin alcanzar PASS; PASS exige los 4 gates y supervivencia en ambos años,
nunca se sustituye por "mejora respecto de V3-A".

Hipótesis a falsificar:
  H0: bajo el contrato congelado, TP fijo 2.5R no produce ninguna celda
      (activo, año) que supere los 4 gates, ni ningún activo que sobreviva
      2022 Y 2023 — el techo de PF (~0.9-1.5) observado en H1/H2/I1/
      Espacio 1/Bias B/Trigger C persiste independientemente del mecanismo
      de salida.
  H1: al menos un activo sobrevive 2022 Y 2023 bajo TP fijo 2.5R.
Falsificada si 0/3 activos sobreviven ambos años. El mejor resultado
observado no se reinterpreta retroactivamente como hipótesis primaria.

Variable experimental — ÚNICAMENTE el mecanismo de salida, nada más:
    SL inicial:  idéntico al baseline, sin cambios — min(estructura,
                 entry ∓ atr_mult×ATR), calculado por `backtest.find_entries`
                 (reutilizado sin modificar).
    TP:          fijo en `entry ± TP_R×risk_pts`, TP_R=2.5 (constante
                 congelada, no parametrizable dentro de este experimento).
    Timeout:     `cfg.max_hold`=20 velas, cierre a mercado — misma regla
                 que `simulate_v3`, sin cambios.
    Sin breakeven, sin trailing, sin umbral de activación, sin `distance`
    — el stop nunca se mueve desde `entry["sl0"]` en ningún momento de la
    vida de la operación (a diferencia de V3-A, donde el stop puede subir/
    bajar por breakeven o trailing).
Precedencia intrabar (decisión de diseño explícita, no heredada
automáticamente): si en la misma vela el rango de precio contiene tanto el
nivel de SL como el de TP, la salida se registra como STOP — misma
convención conservadora ya documentada para V3 en `backtest.py` ("test del
stop contra el extremo adverso antes que cualquier actualización
favorable").

Comparador: el mismo ya reutilizado por Bias B y Trigger C —
`gestion_campaign_session_results.csv`, `candidate="dcv1_activo_15h"`,
`exit_config="V3-A (1R/2R/1R)"` (Bias=A/Trigger=T1_ema_cross/
Entry=C_market_close/atr_mult=1.5/atr_period=14/max_hold=20/risk=0.005/
sesión=dcv1_activo_15h). Tercera reutilización del mismo comparador —
ninguna referencia nueva que auditar.

Fase A (verificación de comparabilidad, obligatoria antes de cualquier
resultado del candidato — DISTINTA de la Fase A de Bias B/Trigger C, que
verificaban una celda AUXILIAR; acá se verifica el propio BASELINE):
  1. Reproducir V3-A completo (mismas entradas, `backtest.EXIT_CONFIGS
     ["V3-A (1R/2R/1R)"]`, `backtest.run_config`/`backtest.metrics` sin
     modificar) y exigir coincidencia 6/6 (una por activo/año) contra
     `gestion_campaign_session_results.csv` — n_entries/n_trades/pf/wr/
     exp_r/max_dd/freq. Si CUALQUIERA falla, `AssertionError` inmediato —
     la corrida aborta antes de calcular una sola celda del candidato.
  2. Solo si el paso 1 pasa 6/6: reutilizar EXACTAMENTE la misma lista de
     entradas (el mismo objeto, no recomputada) para correr TP fijo. Esto
     garantiza por construcción — no por verificación posterior — que la
     única diferencia entre baseline y candidato es la función de
     simulación de salida.
El `m_v3a` recomputado en el paso 1 se reutiliza para calcular los deltas
del paso 2 (ΔPF, ΔMaxDD, Δexp_r, Δfreq, Δn_trades) — no es evidencia
experimental nueva, es el comparador; recomputarlo una segunda vez sería
redundante y no cambiaría su valor (mismas entradas, mismo `simulate_v3`,
determinista).

Nomenclatura de razones de salida (sin mezclar categorías entre
mecanismos, ver contrato): V3-A solo produce reason∈{"stop","timeout"}
literalmente en su código (`simulate_v3` nunca escribe "breakeven" ni
"trailing" como razón — esos son ajustes internos del stop, no razones de
cierre); TP fijo produce reason∈{"stop","tp","timeout"}. Ninguna categoría
combinada tipo "reason_tp_o_trailing" se introduce en ningún lugar de este
módulo.

Reutilización de infraestructura (sin modificar `backtest.py` ni ningún
archivo reutilizado): `backtest.Config`, `backtest.find_entries`
(T1_ema_cross+C_market_close, sin cambios), `backtest.EXIT_CONFIGS["V3-A
(1R/2R/1R)"]`, `backtest.run_config`/`backtest.metrics`, `backtest.
COST_PER_TRADE` (mismo modelo de costos). De `scripts/bias_campaign.py` —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
`scripts/trigger_campaign.py` — `load_asset_year` (fija Bias=A). De
`scripts/gestion_campaign_session.py` — `SESSION_WINDOWS`. El mecanismo
"TP fijo" (`simulate_tp_fixed`/`run_config_tp_fixed`) es código NUEVO,
vive únicamente en este módulo — Gestión queda deliberadamente fuera del
registro de `research/layers.py` (SL/TP/sizing tratados como fijos, no
como variante de capa, ver `research/layers.py`), mismo criterio ya
aplicado a V3-A/V3-B.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción
real sobre `gestion_campaign_session_results.csv` (ya committeado, no
requiere data/raw/), ver
research/tests/test_gestion_espacio6_tp_fijo_campaign.py.

Uso (desde la raíz del repo, con data/raw/ poblado — NO ejecutado
todavía, requiere autorización explícita separada):
    python scripts/gestion_espacio6_tp_fijo_campaign.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/gestion_espacio6_tp_fijo_campaign.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña — contrato congelado 2026-08-25                       #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"                  # fijado en trigger_camp.load_asset_year, no parametrizado acá
TRIGGER_CANDIDATE = "T1_ema_cross"    # vía backtest.find_entries, sin cambios
ENTRY_CANDIDATE = "C_market_close"    # vía backtest.find_entries, sin cambios
SESSION_LABEL = "dcv1_activo_15h"     # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — mismo timeout para V3-A y TP fijo

TP_R = 2.5   # constante congelada — especificación original de FRAMEWORK.md
             # (sección "Gestión (fija para todas las variantes)"), NO la
             # Gestión vigente del motor (esa es V3-A). Ver docstring §0.

MECHANISM_LABEL = "TP_fijo_2.5R"
CANDIDATE_LABEL = MECHANISM_LABEL
CANDIDATES = (CANDIDATE_LABEL,)   # una sola celda de candidato — sin grid

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Espacio 6 — TP fijo 2.5R (Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/"
    "atr_mult=1.5/atr_period=14/max_hold=20/risk=0.005 fijos; sesión=dcv1_activo_15h "
    "única; comparador principal: V3-A bajo el mismo contrato, ver diseño formal de "
    "Espacio 6 — Experimento 1. TP_R=2.5 es la especificación histórica de "
    "FRAMEWORK.md, NO la Gestión vigente del motor)"
)

_V3A_REF_PATH = "gestion_campaign_session_results.csv"
_V3A_REF_CANDIDATE = "dcv1_activo_15h"
_V3A_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


# --------------------------------------------------------------------------- #
# Mecanismo de salida nuevo — TP fijo 2.5R (código nuevo, no modifica         #
# backtest.py). Estructuralmente paralelo a backtest.py::simulate_v3/        #
# run_config, pero sin breakeven/trailing/activation/distance.               #
# --------------------------------------------------------------------------- #
def simulate_tp_fixed(df: pd.DataFrame, entry: dict, cfg: "backtest.Config",
                       tp_r: float = TP_R) -> dict:
    """Simula una entrada con salida TP fijo, convención intrabar
    conservadora (mismo principio que `simulate_v3`): cada vela testea
    PRIMERO el extremo adverso contra el stop (fijo, nunca se mueve desde
    `entry['sl0']` — sin breakeven, sin trailing), y solo si no hay stop-out
    se testea el extremo favorable contra el TP fijo. Si ambos niveles caen
    dentro del rango de la misma vela, gana el STOP — precedencia
    conservadora explícita, no un accidente de orden de evaluación."""
    i0 = entry["entry_idx"]
    direction = entry["direction"]
    e = entry["entry"]
    risk_pts = entry["risk_pts"]
    stop = entry["sl0"]   # nunca se reasigna — sin breakeven, sin trailing
    if direction == "long":
        tp_price = e + tp_r * risk_pts
    else:
        tp_price = e - tp_r * risk_pts

    n = len(df)
    exit_idx = None
    exit_price = None
    reason = None

    end = min(i0 + cfg.max_hold + 1, n)
    for k in range(i0 + 1, end):
        c = df.iloc[k]

        # ── 1. Stop (extremo adverso) — precedencia sobre TP si ambos
        #      caen en la misma vela.
        if direction == "long":
            hit_stop = c["low"] <= stop
        else:
            hit_stop = c["high"] >= stop
        if hit_stop:
            exit_idx, exit_price, reason = k, stop, "stop"
            break

        # ── 2. Take-profit (extremo favorable)
        if direction == "long":
            hit_tp = c["high"] >= tp_price
        else:
            hit_tp = c["low"] <= tp_price
        if hit_tp:
            exit_idx, exit_price, reason = k, tp_price, "tp"
            break

    # ── Timeout: cierre a mercado en la última vela evaluada — misma
    #    regla que simulate_v3 (cfg.max_hold, close de la vela).
    if exit_idx is None:
        last = min(end - 1, n - 1)
        exit_idx = last
        exit_price = df.iloc[last]["close"]
        reason = "timeout"

    if direction == "long":
        pnl_pts = exit_price - e
    else:
        pnl_pts = e - exit_price
    pnl_r_gross = pnl_pts / risk_pts
    cost_r = (e * backtest.COST_PER_TRADE) / risk_pts   # mismo modelo de costos
    pnl_r_net = pnl_r_gross - cost_r

    return {
        "entry_time": df.index[i0],
        "exit_time": df.index[exit_idx],
        "direction": direction,
        "reason": reason,
        "pnl_r": round(pnl_r_net, 4),
        "duration_h": exit_idx - i0,
        # exit_price no existe en simulate_v3 (no es necesario para pnl_r,
        # ya incorporado) — se agrega acá porque el mecanismo TP fijo tiene
        # niveles de salida fijos y verificables (sl0/tp_price), útil para
        # tests directos del mecanismo; no se usa en metrics()/results_to_frame.
        "exit_price": exit_price,
    }


def run_config_tp_fixed(df: pd.DataFrame, entries: list[dict],
                         cfg: "backtest.Config") -> pd.DataFrame:
    """Réplica de `backtest.run_config`, parametrizada por
    `simulate_tp_fixed` en vez de `simulate_v3` — misma regla de 'una
    posición a la vez' (`busy_until`), sin modificar `entries` (no se
    reasigna ningún campo de los dicts de entrada; el `stop` local de
    `simulate_tp_fixed` es una copia por valor de `entry['sl0']`, nunca
    escribe de vuelta al dict)."""
    trades = []
    busy_until = -1
    for ent in entries:
        if ent["entry_idx"] <= busy_until:
            continue
        res = simulate_tp_fixed(df, ent, cfg)
        trades.append(res)
        exit_idx = df.index.get_loc(res["exit_time"])
        busy_until = exit_idx
    return pd.DataFrame(trades)


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _cfg() -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                            max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)


def _entries_for_asset_year(asset: str, year: int):
    """Bias=A (vía trigger_camp.load_asset_year), Trigger=T1_ema_cross/
    Entry=C_market_close (vía backtest.find_entries, sin cambios) — misma
    ruta ya usada por scripts/bias_b_campaign.py. Entradas computadas UNA
    sola vez por (activo, año) y reutilizadas para AMBOS mecanismos (V3-A
    en Fase A, TP fijo en Fase B) — ver docstring del módulo."""
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = _cfg()
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = backtest.find_entries(frame, cfg)
    return frame, cfg, entries


def _v3a_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_V3A_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == _V3A_REF_CANDIDATE)
               & (df["exit_config"] == _V3A_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia V3-A para activo={asset}, "
            f"año={year} en {_V3A_REF_PATH} — no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _verify_against(asset: str, year: int, n_entries: int, n_trades: int,
                     m: dict | None, ref_row: pd.Series) -> None:
    mismatches = []
    if n_entries != ref_row["n_entries"]:
        mismatches.append(f"n_entries: esperado={ref_row['n_entries']!r}, obtenido={n_entries!r}")
    if n_trades != ref_row["n_trades"]:
        mismatches.append(f"n_trades: esperado={ref_row['n_trades']!r}, obtenido={n_trades!r}")
    for field in _CHECK_FIELDS:
        expected = ref_row[field]
        actual = m.get(field) if m else None
        if actual != expected:
            mismatches.append(f"{field}: esperado={expected!r}, obtenido={actual!r}")
    if mismatches:
        raise AssertionError(
            f"Fase A (reproducción del baseline V3-A) falló — activo={asset}, "
            f"año={year}:\n  " + "\n  ".join(mismatches) +
            f"\nLa corrida aborta antes de calcular la celda del candidato TP fijo."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A — paso 1 (reproducir V3-A) + paso 2 (reutilizar las mismas
    entradas). Devuelve (frame, cfg, entries, m_v3a); revienta con
    AssertionError si el paso 1 no coincide 6/6 contra
    gestion_campaign_session_results.csv. `m_v3a` es el comparador —
    reutilizado para los deltas de Fase B, no recalculado dos veces."""
    frame, cfg, entries = _entries_for_asset_year(asset, year)
    trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    m_v3a = backtest.metrics(trades_v3a, cfg)
    _verify_against(asset, year, len(entries), len(trades_v3a), m_v3a, _v3a_reference(asset, year))
    return frame, cfg, entries, m_v3a


# --------------------------------------------------------------------------- #
# Fase B — la celda objetivo (solo tras Fase A completa sin excepción)        #
# --------------------------------------------------------------------------- #
def _delta(candidate_val, v3a_val):
    if candidate_val is None or v3a_val is None:
        return None
    return round(candidate_val - v3a_val, 4)


def _row(asset: str, year: int, entries: list[dict], trades: pd.DataFrame,
         m: dict | None, m_v3a: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "bias": BIAS_CANDIDATE, "trigger": TRIGGER_CANDIDATE,
        "entry": ENTRY_CANDIDATE, "mechanism": MECHANISM_LABEL, "candidate": CANDIDATE_LABEL,
        "exit_config": EXIT_CONFIG_LABEL, "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "metrics_v3a": m_v3a,
    }


def run_asset_year_target(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config",
                           entries: list[dict], m_v3a: dict | None) -> dict:
    trades = run_config_tp_fixed(frame, entries, cfg)
    m = backtest.metrics(trades, cfg)
    return _row(asset, year, entries, trades, m, m_v3a)


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa (reproducir V3-A) para
    las 6 combinaciones (activo, año) ANTES de que arranque la Fase B — si
    run_integrity_check revienta en cualquier combinación, la excepción se
    propaga acá y la función nunca llega a calcular la celda del candidato.
    NO incluye 2024 — ver run_blind_test."""
    known: dict[tuple[str, int], tuple] = {}
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg, entries, m_v3a = known[(asset, year)]
            rows.append(run_asset_year_target(asset, year, frame, cfg, entries, m_v3a))  # Fase B
    return rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` ya congelado
    ("TP_fijo_2.5R" — la única celda de esta campaña). No corre Fase A acá
    (exclusiva de la fase 2022+2023) ni calcula deltas contra V3-A (sin
    referencia de 2024 publicada para ese comparador en este contrato)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere el candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_asset_year(asset, BLIND_YEAR)
        trades = run_config_tp_fixed(frame, entries, cfg)
        m = backtest.metrics(trades, cfg)
        results.append(_row(asset, BLIND_YEAR, entries, trades, m, m_v3a=None))
    return results


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        m_v3a = r["metrics_v3a"] or {}
        reasons = m.get("reasons") or {}
        freq = m.get("freq")
        n_entries = r["n_entries"]
        n_trades = r["n_trades"]
        months = (n_trades / freq) if freq else None
        entries_per_month = (n_entries / months) if months else None
        fill_rate = (n_trades / n_entries) if n_entries else None
        rows.append({
            "asset": r["asset"], "year": r["year"], "bias": r["bias"], "trigger": r["trigger"],
            "entry": r["entry"], "mechanism": r["mechanism"], "candidate": r["candidate"],
            "exit_config": r["exit_config"], "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"),
            # Razones de salida SIN mezclar categorías entre mecanismos —
            # TP fijo produce exactamente {"stop","tp","timeout"}.
            "reason_stop": reasons.get("stop", 0), "reason_tp": reasons.get("tp", 0),
            "reason_timeout": reasons.get("timeout", 0),
            # Comparador V3-A (recomputado en Fase A, no re-derivado) — para
            # que los deltas de abajo sean auditables sin releer el CSV.
            "pf_v3a": m_v3a.get("pf"), "max_dd_v3a": m_v3a.get("max_dd"),
            "exp_r_v3a": m_v3a.get("exp_r"), "freq_v3a": m_v3a.get("freq"),
            "n_trades_v3a": m_v3a.get("trades"),
            # Deltas explícitos (candidato − V3-A) — puramente descriptivos,
            # no definen ningún gate nuevo ni alteran el criterio de PASS.
            "delta_pf": _delta(m.get("pf"), m_v3a.get("pf")),
            "delta_max_dd": _delta(m.get("max_dd"), m_v3a.get("max_dd")),
            "delta_exp_r": _delta(m.get("exp_r"), m_v3a.get("exp_r")),
            "delta_freq": _delta(freq, m_v3a.get("freq")),
            "delta_n_trades": (n_trades - m_v3a["trades"]) if m_v3a.get("trades") is not None else None,
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 6 — Experimento 1: TP fijo 2.5R (comparador: V3-A)\n"
          f"  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "n_entries", "n_trades", "entries_per_month", "fill_rate",
            "pf", "wr", "exp_r", "avg_win", "avg_loss", "total_r", "max_dd", "freq", "be",
            "reason_stop", "reason_tp", "reason_timeout", "gate_pass",
            "pf_v3a", "delta_pf", "max_dd_v3a", "delta_max_dd",
            "exp_r_v3a", "delta_exp_r", "freq_v3a", "delta_freq", "delta_n_trades"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN (criterio de PASS del framework, NO 'mejora respecto de V3-A'): "
          f"sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: TP fijo 2.5R no demuestra evidencia suficiente para cumplir "
                  f"los 4 gates de FRAMEWORK.md en 2022+2023 (esto no descarta que haya "
                  f"mejorado alguna métrica respecto de V3-A — ver columnas delta_*, sección "
                  f"separada de la decisión de PASS).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="candidato ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el candidato ya congelado)")
        results = run_blind_test(candidate=args.candidate)
        df = results_to_frame(results)
        print_report(df)
        out_path = "gestion_espacio6_tp_fijo_campaign_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_espacio6_tp_fijo_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 1 mecanismo x 3 activos x 2 "
          f"años = 6, todas genuinamente nuevas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "gestion_espacio6_tp_fijo_campaign_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
