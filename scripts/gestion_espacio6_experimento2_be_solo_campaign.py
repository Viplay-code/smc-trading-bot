#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_espacio6_experimento2_be_solo_campaign.py — Espacio 6,
Experimento 2: mecanismo "BE_solo_1.0R" (V3-A sin trailing, con breakeven
intacto en 1.0R, sin TP) contra el comparador V3-A, bajo el mismo contrato
en todo lo demás ya usado por Espacio 6-E1. Contrato final aprobado
2026-08-28 (2 revisiones: MFE/avg_win degradado a evidencia mecanística
secundaria, nunca decide el veredicto por sí sola; verificación conceptual
de invariancia de la ablación antes de implementar).

Encuadre (obligatorio, ver contrato E2 §0-§3): este experimento aísla UN
SOLO componente estructural de V3-A — el trailing (activación + ratchet) —
manteniendo el breakeven intacto en su valor ya canónico (be_lvl=1.0R,
IDÉNTICO al que usa V3-A) y sin ningún techo de ganancia. Es la ablación
más directa disponible para responder la pregunta que Espacio 6-E1 dejó
abierta: de los tres cambios que E1 hizo a la vez (quitar breakeven, quitar
trailing, agregar techo), ¿cuál explica la mejora observada?

Hipótesis a falsificar:
  H0: bajo el contrato congelado, `BE_solo_1.0R` no reproduce ninguna
      mejora material de PF/MaxDD/exp_r respecto de V3-A — el trailing no
      es el componente que explica la mejora observada en E1.
  H1: `BE_solo_1.0R` reproduce una mejora de magnitud comparable a la de
      E1 en la mayoría de las celdas — evidencia de que el trailing es el
      componente principal detrás del resultado de E1.
La comparación `avg_win` vs. MFE (ver más abajo) es evidencia MECANÍSTICA
SECUNDARIA — nunca decide el veredicto por sí sola (revisión 2026-08-28
del contrato): la evidencia primaria sigue siendo PF/MaxDD/exp_r frente a
V3-A, exactamente igual que en E1.

Implementación — SIN reimplementar ni duplicar `simulate_v3` (decisión de
diseño central, resultado de la verificación conceptual de invariancia
2026-08-28): la ablación se logra reutilizando `backtest.simulate_v3`/
`backtest.run_config` SIN MODIFICAR, con
    exit_cfg = {"be": 1.0, "activation": float("inf"), "distance": 0.0}
Con `activation=inf`, la condición del paso 4 de `simulate_v3`
(`fav_r >= act_lvl`) nunca es verdadera → `trailing_on` nunca pasa a
`True` → el paso 5 (ratchet) nunca se ejecuta (protegido por
`if trailing_on:`). `distance`=0.0 es un valor estructuralmente
INALCANZABLE, no un parámetro experimental — nunca se lee porque el
bloque que lo usaría nunca se ejecuta (verificado por test,
`test_distance_es_inalcanzable_no_es_parametro`). Verificación paso a
paso de `simulate_v3` (backtest.py:144-198) confirmó que los pasos 1
(test de stop), 2 (acumulación de MFE), 3 (breakeven) y el timeout son
estructuralmente independientes de los pasos 4-5 — remover el trailing no
interactúa indirectamente con ninguno de ellos. Único efecto de segundo
orden esperado (no es una interacción a corregir, es la variable
experimental en acción): el instante de salida de cada operación cambia,
lo que puede desplazar en ±1 el `n_trades` de alguna celda vía la regla
"una posición a la vez" — mismo fenómeno ya documentado en el cierre de
Espacio 6-E1.

Diagnóstico `mfe_r` — estrictamente de solo lectura, POSTERIOR a que
`backtest.run_config` ya determinó qué entradas se ejecutaron como
trades; no participa en ninguna decisión de entrada/salida, no modifica
`simulate_v3` ni `run_config`. Se empareja cada fila de `trades` con su
`entry` original por `entry_time` (único por entrada real de Capa 2) y se
recorre `high`/`low` de forma independiente sobre la misma ventana de
`max_hold` — sin testear stop, sin breakeven, sin trailing. Mismo
principio metodológico que `gestion_mfe_diagnostico_summary.csv`
(2026-07-30, bajo `control_8h`) — pero calculado sobre esta misma sesión
(`dcv1_activo_15h`), evitando mezclar sesiones distintas en una
comparación cuantitativa (ver contrato E2 §10 revisado).

Comparador: el mismo ya reutilizado por Bias B/Trigger C/Espacio 6-E1 —
`gestion_campaign_session_results.csv`, `candidate="dcv1_activo_15h"`,
`exit_config="V3-A (1R/2R/1R)"`.

Fase A (idéntica en diseño a Espacio 6-E1, obligatoria antes de cualquier
resultado del candidato):
  1. Reproducir V3-A completo (mismas entradas,
     `backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]`, sin modificar) y exigir
     coincidencia 6/6 (una por activo/año) contra
     `gestion_campaign_session_results.csv`. Si CUALQUIERA falla,
     `AssertionError` inmediato — la corrida aborta antes de calcular una
     sola celda del candidato.
  2. Solo si el paso 1 pasa 6/6: reutilizar EXACTAMENTE la misma lista de
     entradas (el mismo objeto, no recomputada) para correr
     `BE_solo_1.0R`.

Reutilización de infraestructura (sin modificar `backtest.py` ni ningún
archivo reutilizado): `backtest.Config`, `backtest.find_entries`
(T1_ema_cross+C_market_close, sin cambios), `backtest.EXIT_CONFIGS["V3-A
(1R/2R/1R)"]`, `backtest.simulate_v3`/`backtest.run_config`/
`backtest.metrics` (reutilizados SIN MODIFICAR — el mecanismo de
Experimento 2 NO es código nuevo de simulación, es una parametrización
distinta de la misma función). De `scripts/bias_campaign.py` —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
`scripts/trigger_campaign.py` — `load_asset_year` (fija Bias=A). De
`scripts/gestion_campaign_session.py` — `SESSION_WINDOWS`.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción
real sobre `gestion_campaign_session_results.csv` (ya committeado, no
requiere data/raw/), ver
research/tests/test_gestion_espacio6_experimento2_be_solo_campaign.py.

Uso (desde la raíz del repo, con data/raw/ poblado — NO ejecutado
todavía, requiere autorización explícita separada):
    python scripts/gestion_espacio6_experimento2_be_solo_campaign.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/gestion_espacio6_experimento2_be_solo_campaign.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
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
# Config de la campaña — contrato congelado 2026-08-28                       #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"                  # fijado en trigger_camp.load_asset_year, no parametrizado acá
TRIGGER_CANDIDATE = "T1_ema_cross"    # vía backtest.find_entries, sin cambios
ENTRY_CANDIDATE = "C_market_close"    # vía backtest.find_entries, sin cambios
SESSION_LABEL = "dcv1_activo_15h"     # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — mismo timeout para V3-A y BE_solo_1.0R

BE_LVL = 1.0   # constante REUTILIZADA de V3-A (backtest.EXIT_CONFIGS
               # ["V3-A (1R/2R/1R)"]["be"]) — no un valor nuevo.

# Variable experimental única: desactivar el trailing por construcción
# (activation=inf hace inalcanzable el paso 4/5 de simulate_v3).
# distance=0.0 NO es un parámetro experimental — es inalcanzable, nunca
# se lee (ver test_distance_es_inalcanzable_no_es_parametro). No pasar
# por research/layers.py ni por backtest.EXIT_CONFIGS — vive únicamente
# acá, como configuración local de esta campaña.
EXIT_CFG_BE_SOLO = {"be": BE_LVL, "activation": float("inf"), "distance": 0.0}

MECHANISM_LABEL = "BE_solo_1.0R"
CANDIDATE_LABEL = MECHANISM_LABEL
CANDIDATES = (CANDIDATE_LABEL,)   # una sola celda de candidato — sin grid

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Espacio 6 — Experimento 2: BE_solo_1.0R (V3-A sin trailing, be=1.0R intacto, "
    "sin TP; Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/atr_mult=1.5/"
    "atr_period=14/max_hold=20/risk=0.005 fijos; sesión=dcv1_activo_15h única; "
    "comparador principal: V3-A bajo el mismo contrato. Implementado reutilizando "
    "backtest.simulate_v3 sin modificar, con activation=inf/distance=0.0 "
    "estructuralmente inalcanzable — no un parámetro experimental)"
)

_V3A_REF_PATH = "gestion_campaign_session_results.csv"
_V3A_REF_CANDIDATE = "dcv1_activo_15h"
_V3A_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _cfg() -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                            max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)


def _entries_for_asset_year(asset: str, year: int):
    """Bias=A (vía trigger_camp.load_asset_year), Trigger=T1_ema_cross/
    Entry=C_market_close (vía backtest.find_entries, sin cambios) — misma
    ruta ya usada por Espacio 6-E1. Entradas computadas UNA sola vez por
    (activo, año) y reutilizadas para AMBOS mecanismos (V3-A en Fase A,
    BE_solo_1.0R en Fase B)."""
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
            f"\nLa corrida aborta antes de calcular la celda del candidato BE_solo_1.0R."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A — paso 1 (reproducir V3-A vía backtest.run_config/
    EXIT_CONFIGS["V3-A (1R/2R/1R)"], sin modificar) + paso 2 (reutilizar
    las mismas entradas). Devuelve (frame, cfg, entries, m_v3a); revienta
    con AssertionError si el paso 1 no coincide 6/6 contra
    gestion_campaign_session_results.csv."""
    frame, cfg, entries = _entries_for_asset_year(asset, year)
    trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    m_v3a = backtest.metrics(trades_v3a, cfg)
    _verify_against(asset, year, len(entries), len(trades_v3a), m_v3a, _v3a_reference(asset, year))
    return frame, cfg, entries, m_v3a


# --------------------------------------------------------------------------- #
# Diagnóstico mfe_r — ESTRICTAMENTE de solo lectura, posterior a la          #
# ejecución real. No testea stop, no decide breakeven/trailing, no          #
# modifica backtest.simulate_v3/run_config, no participa en ninguna         #
# decisión de entrada/salida.                                               #
# --------------------------------------------------------------------------- #
def _mfe_r_for_entry(df: pd.DataFrame, entry: dict, cfg: "backtest.Config") -> float:
    """Máximo avance favorable (en R) sobre la ventana completa de
    max_hold, calculado de forma independiente de cualquier lógica de
    salida. Mismo principio que gestion_mfe_diagnostico.py (MFE sobre la
    ventana completa, no truncado en el exit real)."""
    i0 = entry["entry_idx"]
    direction = entry["direction"]
    e = entry["entry"]
    risk_pts = entry["risk_pts"]
    n = len(df)
    end = min(i0 + cfg.max_hold + 1, n)
    max_fav_pts = 0.0
    for k in range(i0 + 1, end):
        c = df.iloc[k]
        if direction == "long":
            fav_pts = c["high"] - e
        else:
            fav_pts = e - c["low"]
        if fav_pts > max_fav_pts:
            max_fav_pts = fav_pts
    return round(max_fav_pts / risk_pts, 4)


def compute_mfe_r_for_trades(df: pd.DataFrame, entries: list[dict],
                              trades: pd.DataFrame, cfg: "backtest.Config") -> list[float]:
    """Empareja cada fila de `trades` (YA determinada por
    backtest.run_config) con su `entry` original por `entry_time`, y
    calcula mfe_r para exactamente esas operaciones — nunca al revés."""
    entry_by_time = {df.index[e["entry_idx"]]: e for e in entries}
    return [_mfe_r_for_entry(df, entry_by_time[tr["entry_time"]], cfg)
            for _, tr in trades.iterrows()]


# --------------------------------------------------------------------------- #
# Fase B — la celda objetivo (solo tras Fase A completa sin excepción)        #
# --------------------------------------------------------------------------- #
def _delta(candidate_val, v3a_val):
    if candidate_val is None or v3a_val is None:
        return None
    return round(candidate_val - v3a_val, 4)


def _row(asset: str, year: int, entries: list[dict], trades: pd.DataFrame,
         m: dict | None, m_v3a: dict | None, mfe_rs: list[float]) -> dict:
    return {
        "asset": asset, "year": year, "bias": BIAS_CANDIDATE, "trigger": TRIGGER_CANDIDATE,
        "entry": ENTRY_CANDIDATE, "mechanism": MECHANISM_LABEL, "candidate": CANDIDATE_LABEL,
        "exit_config": EXIT_CONFIG_LABEL, "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "metrics_v3a": m_v3a,
        "trades": trades, "mfe_rs": mfe_rs,
    }


def run_asset_year_target(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config",
                           entries: list[dict], m_v3a: dict | None) -> dict:
    # Reutiliza backtest.run_config/simulate_v3 SIN MODIFICAR — la única
    # diferencia con la Fase A es el exit_cfg pasado (activation=inf
    # desactiva el trailing por construcción).
    trades = backtest.run_config(frame, entries, EXIT_CFG_BE_SOLO, cfg)
    m = backtest.metrics(trades, cfg)
    mfe_rs = compute_mfe_r_for_trades(frame, entries, trades, cfg)   # solo lectura, posterior
    return _row(asset, year, entries, trades, m, m_v3a, mfe_rs)


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
    ("BE_solo_1.0R" — la única celda de esta campaña). No corre Fase A acá
    (exclusiva de la fase 2022+2023) ni calcula deltas contra V3-A."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere el candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    results: list[dict] = []
    for asset in assets:
        frame, cfg, entries = _entries_for_asset_year(asset, BLIND_YEAR)
        trades = backtest.run_config(frame, entries, EXIT_CFG_BE_SOLO, cfg)
        m = backtest.metrics(trades, cfg)
        mfe_rs = compute_mfe_r_for_trades(frame, entries, trades, cfg)
        results.append(_row(asset, BLIND_YEAR, entries, trades, m, None, mfe_rs))
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

        trades = r["trades"]
        mfe_rs = r["mfe_rs"]
        winners_mfe = [mfe for mfe, (_, tr) in zip(mfe_rs, trades.iterrows()) if tr["pnl_r"] > 0]
        mean_mfe_r_winners = round(sum(winners_mfe) / len(winners_mfe), 4) if winners_mfe else None
        avg_win = m.get("avg_win")
        gap_avg_win_mfe = (round(mean_mfe_r_winners - avg_win, 4)
                            if mean_mfe_r_winners is not None and avg_win is not None else None)

        rows.append({
            "asset": r["asset"], "year": r["year"], "bias": r["bias"], "trigger": r["trigger"],
            "entry": r["entry"], "mechanism": r["mechanism"], "candidate": r["candidate"],
            "exit_config": r["exit_config"], "n_entries": n_entries, "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": avg_win, "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"),
            # Sin TP en este mecanismo — solo stop/timeout, sin ninguna
            # categoría mezclada.
            "reason_stop": reasons.get("stop", 0), "reason_timeout": reasons.get("timeout", 0),
            # Diagnóstico MECANÍSTICO SECUNDARIO (contrato E2 §10 revisado)
            # — nunca decide el veredicto por sí solo.
            "mean_mfe_r_winners": mean_mfe_r_winners, "gap_avg_win_mfe": gap_avg_win_mfe,
            # Comparador V3-A + deltas — evidencia PRIMARIA.
            "pf_v3a": m_v3a.get("pf"), "max_dd_v3a": m_v3a.get("max_dd"),
            "exp_r_v3a": m_v3a.get("exp_r"), "freq_v3a": m_v3a.get("freq"),
            "n_trades_v3a": m_v3a.get("trades"),
            "delta_pf": _delta(m.get("pf"), m_v3a.get("pf")),
            "delta_max_dd": _delta(m.get("max_dd"), m_v3a.get("max_dd")),
            "delta_exp_r": _delta(m.get("exp_r"), m_v3a.get("exp_r")),
            "delta_freq": _delta(freq, m_v3a.get("freq")),
            "delta_n_trades": (n_trades - m_v3a["trades"]) if m_v3a.get("trades") is not None else None,
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 6 — Experimento 2: BE_solo_1.0R (comparador: V3-A)\n"
          f"  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "n_entries", "n_trades", "entries_per_month", "fill_rate",
            "pf", "wr", "exp_r", "avg_win", "avg_loss", "total_r", "max_dd", "freq", "be",
            "reason_stop", "reason_timeout", "gate_pass",
            "mean_mfe_r_winners", "gap_avg_win_mfe",
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
    print(f"\n{'='*100}\n  DECISIÓN (criterio de PASS del framework, evidencia PRIMARIA únicamente — "
          f"mean_mfe_r_winners/gap_avg_win_mfe son secundarios, no deciden acá): sobrevivientes "
          f"(ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: BE_solo_1.0R no demuestra evidencia suficiente para cumplir "
                  f"los 4 gates de FRAMEWORK.md en 2022+2023.")


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
        out_path = "gestion_espacio6_experimento2_be_solo_campaign_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_espacio6_experimento2_be_solo_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 1 mecanismo x 3 activos x 2 "
          f"años = 6, todas genuinamente nuevas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "gestion_espacio6_experimento2_be_solo_campaign_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
