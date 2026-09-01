#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_espacio6_raw_campaign.py — Espacio 6, Experimento 3:
mecanismo "Raw" (SL inicial fijo, sin breakeven, sin trailing, sin TP —
única salida antes del timeout es el stop original) contra DOS
comparadores bajo el mismo contrato en todo lo demás ya usado por
Espacio 6-E1/E2. Contrato final aprobado en sesión de diseño previa a esta
implementación (auditoría de código incluida: `be=inf`/`activation=inf`
sobre `backtest.simulate_v3` reproducen exactamente "SL inicial + timeout",
sin ningún movimiento de stop — verificado línea por línea antes de
autorizar esta campaña).

Encuadre: E1 (TP fijo 2.5R) cambió TRES componentes a la vez respecto de
V3-A (quitar breakeven, quitar trailing, agregar TP) usando una función de
simulación separada (`simulate_tp_fixed`, no `simulate_v3`). E2 (BE_solo)
aisló el trailing en solitario (BE intacto) y empeoró. Ninguno de los dos
permite, por sí solo, atribuir la mejora de E1 a un componente específico.
`Raw` cierra ese hueco: es EXACTAMENTE la base de E1 (BE off, trailing
off) SIN el TP — comparando E1 contra Raw se aísla el TP como única
variable real, porque ambas funciones (`simulate_tp_fixed` y `simulate_v3`
con esta parametrización) comparten SL inicial idéntico, misma
precedencia intrabar conservadora, mismo `cfg.max_hold`, mismo
`COST_PER_TRADE`, y las mismas entradas (misma ruta determinista de
generación: Bias=A vía `trigger_camp.load_asset_year` + `backtest.
find_entries`) — verificado en este script comparando `n_entries` contra
los ya publicados de E1, no solo asumido.

Hipótesis a falsificar:
  H0: Raw no reproduce ninguna mejora material de PF/MaxDD/exp_r respecto
      de V3-A, y/o Raw no difiere de forma material de E1 — el TP no es
      el componente que explica la diferencia entre E1 y V3-A.
  H1: Raw se comporta de forma similar a V3-A (sin mejora), mientras E1
      sí mejora — evidencia de que el TP, específicamente, es el
      componente responsable de la mejora observada en E1.

Implementación — SIN reimplementar ni duplicar `simulate_v3` (misma
decisión de diseño que E2): la ablación se logra reutilizando
`backtest.simulate_v3`/`backtest.run_config` SIN MODIFICAR, con
    exit_cfg = {"be": float("inf"), "activation": float("inf"), "distance": 0.0}
Con `be=inf`, el paso 3 (`fav_r >= be_lvl`) nunca es verdadero → `be_done`
nunca pasa a `True` → el stop nunca se mueve a breakeven. Con
`activation=inf`, el paso 4 (`fav_r >= act_lvl`) nunca es verdadero →
`trailing_on` nunca pasa a `True` → el paso 5 (ratchet) nunca se ejecuta
(protegido por `if trailing_on:`). `distance=0.0` es estructuralmente
INALCANZABLE, no un parámetro experimental — nunca se lee (mismo patrón
ya verificado por test en E2, ahora extendido a `be`). Consecuencia:
`stop` se inicializa una sola vez a `entry["sl0"]` y NUNCA se reasigna en
ningún punto del bucle — el único punto de salida antes del timeout es el
stop original.

Verificación de integridad reforzada (más allá de la Fase A estándar
contra V3-A, punto nuevo de este contrato): además de reproducir V3-A 6/6
antes de calcular cualquier celda del candidato, se verifica que
`n_entries` de Raw coincide EXACTAMENTE con `n_entries` ya publicado por
E1 (`gestion_espacio6_tp_fijo_campaign_results.csv`) para cada (activo,
año) — ambos deberían ser idénticos por construcción (misma ruta
determinista), y esta coincidencia es una verificación independiente,
no solo una suposición, de que "E1 vs Raw" compara sobre el mismo
universo de entradas. Se verifica también, trade por trade, que todo
trade con `reason=="stop"` cierra exactamente en `entry["sl0"]` (sin
movimiento de stop) — chequeo de solo lectura, posterior a la simulación,
que no participa en ninguna decisión de entrada/salida.

Comparador primario: V3-A — el mismo ya reutilizado por Bias B/Trigger C/
E1/E2 (`gestion_campaign_session_results.csv`, `candidate=
"dcv1_activo_15h"`, `exit_config="V3-A (1R/2R/1R)"`).
Comparador secundario (la comparación causal principal de este
experimento, contrato §7/§26): E1
(`gestion_espacio6_tp_fijo_campaign_results.csv`).

Fase A (idéntica en diseño a E1/E2, obligatoria antes de cualquier
resultado del candidato):
  1. Reproducir V3-A completo (mismas entradas,
     `backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]`, sin modificar) y exigir
     coincidencia 6/6 (una por activo/año) contra
     `gestion_campaign_session_results.csv`. Si CUALQUIERA falla,
     `AssertionError` inmediato — la corrida aborta antes de calcular una
     sola celda del candidato.
  2. Solo si el paso 1 pasa 6/6: reutilizar EXACTAMENTE la misma lista de
     entradas (el mismo objeto, no recomputada) para correr `Raw`.
  3. Verificar `n_entries` de Raw contra `n_entries` publicado de E1 para
     cada (activo, año) — no aborta la corrida si no coincide (a
     diferencia del paso 1), pero se reporta como hallazgo de integridad
     a auditar antes de interpretar cualquier resultado.

2024/ciego: NO se ejecuta bajo ninguna circunstancia en este contrato —
`run_blind_test` no existe en este script (a diferencia de E1/E2, que sí
lo definen pero nunca lo invocaron). Raw es una celda diagnóstica para
decomponer E1, no un candidato operable — gastar el año ciego en ella no
está autorizado.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_espacio6_raw_campaign.py              # Fase A + Fase B (2022+2023)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
import scripts.gestion_campaign_session as session_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña — contrato aprobado en sesión de diseño previa        #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"                  # fijado en trigger_camp.load_asset_year, no parametrizado acá
TRIGGER_CANDIDATE = "T1_ema_cross"    # vía backtest.find_entries, sin cambios
ENTRY_CANDIDATE = "C_market_close"    # vía backtest.find_entries, sin cambios
SESSION_LABEL = "dcv1_activo_15h"     # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — mismo timeout para V3-A, E1 y Raw

# Variable experimental: desactivar BE Y trailing por construcción
# (be=inf y activation=inf hacen inalcanzables los pasos 3 y 4/5 de
# simulate_v3). distance=0.0 NO es un parámetro experimental — es
# inalcanzable, nunca se lee. No pasa por research/layers.py ni por
# backtest.EXIT_CONFIGS — vive únicamente acá, como configuración local
# de esta campaña.
EXIT_CFG_RAW = {"be": float("inf"), "activation": float("inf"), "distance": 0.0}

MECHANISM_LABEL = "Raw"
CANDIDATE_LABEL = MECHANISM_LABEL
CANDIDATES = (CANDIDATE_LABEL,)   # una sola celda de candidato — sin grid

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Espacio 6 — Experimento 3: Raw (SL inicial fijo, sin breakeven, sin trailing, "
    "sin TP; Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/atr_mult=1.5/"
    "atr_period=14/max_hold=20/risk=0.005 fijos; sesión=dcv1_activo_15h única; "
    "comparador primario: V3-A; comparador secundario (comparación causal principal): "
    "E1 (TP fijo 2.5R). Implementado reutilizando backtest.simulate_v3 sin modificar, "
    "con be=inf/activation=inf/distance=0.0 estructuralmente inalcanzables — "
    "no son parámetros experimentales)"
)

_V3A_REF_PATH = "gestion_campaign_session_results.csv"
_V3A_REF_CANDIDATE = "dcv1_activo_15h"
_V3A_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")

_E1_REF_PATH = "gestion_espacio6_tp_fijo_campaign_results.csv"


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _cfg() -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                            max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)


def _entries_for_asset_year(asset: str, year: int):
    """Bias=A (vía trigger_camp.load_asset_year), Trigger=T1_ema_cross/
    Entry=C_market_close (vía backtest.find_entries, sin cambios) — misma
    ruta ya usada por E1 y E2. Entradas computadas UNA sola vez por
    (activo, año) y reutilizadas para AMBOS mecanismos (V3-A en Fase A,
    Raw en Fase B)."""
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


def _e1_reference(asset: str, year: int) -> pd.Series | None:
    df = pd.read_csv(_E1_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)]
    if match.empty:
        return None
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
            f"\nLa corrida aborta antes de calcular la celda del candidato Raw."
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


def check_entries_vs_e1(asset: str, year: int, n_entries: int) -> dict:
    """Fase A — paso 3 (verificación de integridad reforzada, específica
    de este contrato): compara n_entries de Raw contra n_entries YA
    PUBLICADO de E1. NO aborta la corrida si difiere (a diferencia del
    paso 1) — se reporta para que se audite antes de interpretar
    cualquier resultado, tal como exige el contrato (punto E del informe
    final)."""
    e1_row = _e1_reference(asset, year)
    if e1_row is None:
        return {"asset": asset, "year": year, "n_entries_raw": n_entries,
                 "n_entries_e1": None, "match": None,
                 "note": f"Sin fila de referencia E1 en {_E1_REF_PATH}"}
    n_entries_e1 = int(e1_row["n_entries"])
    return {"asset": asset, "year": year, "n_entries_raw": n_entries,
             "n_entries_e1": n_entries_e1, "match": n_entries == n_entries_e1}


def _row(asset: str, year: int, entries: list[dict], trades: pd.DataFrame,
         m: dict | None, m_v3a: dict | None, m_e1: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "bias": BIAS_CANDIDATE, "trigger": TRIGGER_CANDIDATE,
        "entry": ENTRY_CANDIDATE, "mechanism": MECHANISM_LABEL, "candidate": CANDIDATE_LABEL,
        "exit_config": EXIT_CONFIG_LABEL, "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "metrics_v3a": m_v3a, "metrics_e1": m_e1,
        "trades": trades,
    }


def run_asset_year_target(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config",
                           entries: list[dict], m_v3a: dict | None) -> tuple[dict, dict]:
    # Reutiliza backtest.run_config/simulate_v3 SIN MODIFICAR — la única
    # diferencia con la Fase A es el exit_cfg pasado (be=inf/activation=inf
    # desactivan breakeven y trailing por construcción).
    trades = backtest.run_config(frame, entries, EXIT_CFG_RAW, cfg)
    m = backtest.metrics(trades, cfg)
    m_e1 = _e1_reference(asset, year)
    m_e1_dict = m_e1.to_dict() if m_e1 is not None else None

    # Verificación de solo lectura: todo trade con reason=="stop" debe
    # cerrar exactamente en entry["sl0"] (sin movimiento de stop).
    entry_by_idx = {e["entry_idx"]: e for e in entries}
    idx_by_time = {frame.index[e["entry_idx"]]: e for e in entries}
    stop_mismatches = []
    for _, tr in trades.iterrows():
        if tr["reason"] != "stop":
            continue
        ent = idx_by_time.get(tr["entry_time"])
        if ent is None:
            stop_mismatches.append((tr["entry_time"], "sin entrada emparejada"))
            continue
        # pnl_r_gross esperado si el stop nunca se movio: (sl0-entry)/risk_pts
        # (o su espejo short) menos costos -- se verifica indirectamente
        # reconstruyendo el pnl bruto esperado desde sl0.
        e_price = ent["entry"]; sl0 = ent["sl0"]; risk_pts = ent["risk_pts"]
        if ent["direction"] == "long":
            pnl_pts_expected = sl0 - e_price
        else:
            pnl_pts_expected = e_price - sl0
        pnl_r_gross_expected = pnl_pts_expected / risk_pts
        cost_r = (e_price * backtest.COST_PER_TRADE) / risk_pts
        pnl_r_expected = round(pnl_r_gross_expected - cost_r, 4)
        if abs(tr["pnl_r"] - pnl_r_expected) > 1e-6:
            stop_mismatches.append((tr["entry_time"], f"pnl_r={tr['pnl_r']} vs esperado={pnl_r_expected}"))

    integrity = {"asset": asset, "year": year, "n_stop_trades": int((trades["reason"] == "stop").sum()),
                 "stop_mismatches": stop_mismatches}
    return _row(asset, year, entries, trades, m, m_v3a, m_e1_dict), integrity


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> tuple[list[dict], list[dict], list[dict]]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa (reproducir V3-A) para
    las 6 combinaciones (activo, año) ANTES de que arranque la Fase B —
    si run_integrity_check revienta en cualquier combinación, la
    excepción se propaga acá y la función nunca llega a calcular la celda
    del candidato. NO incluye 2024 — este script no define run_blind_test."""
    known: dict[tuple[str, int], tuple] = {}
    entry_checks: list[dict] = []
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)  # Fase A paso 1+2
            frame, cfg, entries, m_v3a = known[(asset, year)]
            entry_checks.append(check_entries_vs_e1(asset, year, len(entries)))  # Fase A paso 3

    rows: list[dict] = []
    integrity_rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg, entries, m_v3a = known[(asset, year)]
            row, integrity = run_asset_year_target(asset, year, frame, cfg, entries, m_v3a)
            rows.append(row)
            integrity_rows.append(integrity)
    return rows, entry_checks, integrity_rows


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def _delta(candidate_val, ref_val):
    if candidate_val is None or ref_val is None:
        return None
    try:
        return round(float(candidate_val) - float(ref_val), 4)
    except (TypeError, ValueError):
        return None


def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        m_v3a = r["metrics_v3a"] or {}
        m_e1 = r["metrics_e1"] or {}
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
            # Sin BE, sin trailing, sin TP en este mecanismo — solo stop/timeout.
            "reason_stop": reasons.get("stop", 0), "reason_timeout": reasons.get("timeout", 0),
            # Comparador V3-A + deltas
            "pf_v3a": m_v3a.get("pf"), "max_dd_v3a": m_v3a.get("max_dd"),
            "exp_r_v3a": m_v3a.get("exp_r"), "freq_v3a": m_v3a.get("freq"),
            "n_trades_v3a": m_v3a.get("trades"),
            "delta_pf_v3a": _delta(m.get("pf"), m_v3a.get("pf")),
            "delta_max_dd_v3a": _delta(m.get("max_dd"), m_v3a.get("max_dd")),
            "delta_exp_r_v3a": _delta(m.get("exp_r"), m_v3a.get("exp_r")),
            "delta_freq_v3a": _delta(freq, m_v3a.get("freq")),
            "delta_n_trades_v3a": (n_trades - m_v3a["trades"]) if m_v3a.get("trades") is not None else None,
            # Comparador E1 (comparación causal principal) + deltas
            "pf_e1": m_e1.get("pf"), "max_dd_e1": m_e1.get("max_dd"),
            "exp_r_e1": m_e1.get("exp_r"), "freq_e1": m_e1.get("freq"),
            "n_entries_e1": m_e1.get("n_entries"), "n_trades_e1": m_e1.get("n_trades"),
            "delta_pf_e1": _delta(m.get("pf"), m_e1.get("pf")),
            "delta_max_dd_e1": _delta(m.get("max_dd"), m_e1.get("max_dd")),
            "delta_exp_r_e1": _delta(m.get("exp_r"), m_e1.get("exp_r")),
            "delta_freq_e1": _delta(freq, m_e1.get("freq")),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 6 — Experimento 3: Raw (comparadores: V3-A y E1)\n"
          f"  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "n_entries", "n_trades", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "reason_stop", "reason_timeout", "gate_pass",
            "pf_v3a", "delta_pf_v3a", "max_dd_v3a", "delta_max_dd_v3a", "exp_r_v3a", "delta_exp_r_v3a",
            "pf_e1", "delta_pf_e1", "max_dd_e1", "delta_max_dd_e1", "exp_r_e1", "delta_exp_r_e1"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN (criterio de PASS del framework, evidencia PRIMARIA únicamente): "
          f"sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: Raw no demuestra evidencia suficiente para cumplir "
                  f"los 4 gates de FRAMEWORK.md en 2022+2023.")


def main() -> None:
    results, entry_checks, integrity_rows = run_campaign()

    print(f"\n{'='*100}\n  Verificación de integridad — n_entries Raw vs n_entries E1 publicado\n{'='*100}")
    for c in entry_checks:
        status = "OK" if c["match"] else ("SIN REFERENCIA" if c["match"] is None else "MISMATCH")
        print(f"  {c['asset']} {c['year']}: Raw={c['n_entries_raw']} E1={c['n_entries_e1']} -> {status}")

    print(f"\n{'='*100}\n  Verificación de integridad — sin movimiento de stop (trades reason=='stop')\n{'='*100}")
    for ir in integrity_rows:
        status = "OK" if not ir["stop_mismatches"] else "MISMATCH"
        print(f"  {ir['asset']} {ir['year']}: n_stop_trades={ir['n_stop_trades']} -> {status}")
        for mm in ir["stop_mismatches"]:
            print(f"    ! {mm}")

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_espacio6_raw_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 1 mecanismo x 3 activos x 2 "
          f"años = 6, todas genuinamente nuevas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "gestion_espacio6_raw_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
