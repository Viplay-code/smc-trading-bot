#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_espacio6_v3a_tp_campaign.py — Espacio 6, Experimento 4:
mecanismo "V3-A + TP 2.5R" (breakeven ON, trailing ON — idénticos a V3-A —
más un techo de ganancia fijo en 2.5R) contra TRES comparadores: V3-A, E1
(TP fijo 2.5R, sin BE/trailing) y Raw (sin BE/trailing/TP). Contrato
aprobado explícitamente como la ÚLTIMA celda de Gestión de bajo costo
autorizada por defecto — un resultado atractivo aislado NO autoriza
automáticamente un quinto experimento de Gestión.

Encuadre: E1 cambió TRES componentes a la vez respecto de V3-A (quitar
BE, quitar trailing, agregar TP). Raw aisló BE+trailing (ambos apagados,
sin TP) y permitió comparar "E1 vs Raw" para aislar el TP en las
condiciones de E1. Este experimento (`V3-A + TP`) aísla el TP desde el
OTRO extremo: mantiene BE y trailing exactamente como V3-A, y agrega
ÚNICAMENTE el TP fijo. Con las cuatro celdas (V3-A, E1, Raw, V3-A+TP) el
programa tiene, por primera vez, los 4 vértices del sub-cubo BE/trailing
∈ {ON, OFF} × TP ∈ {OFF, ON-en-los-extremos-BE/trailing-off-y-on}
relevantes para decidir si el TP ayuda independientemente del estado de
BE/trailing, o solo en su ausencia.

Hipótesis a falsificar:
  H0: bajo el contrato congelado, agregar TP fijo 2.5R a V3-A (con BE y
      trailing intactos) no produce ninguna mejora material de
      PF/MaxDD/exp_r respecto de V3-A.
  H1: V3-A+TP mejora de forma material y consistente entre activos/años
      respecto de V3-A — evidencia de que el TP ayuda incluso con la
      protección completa puesta, no solo en su ausencia (como sugeriría
      la comparación E1 vs Raw si el TP solo importara sin BE/trailing).

Implementación — SIN modificar `backtest.simulate_v3` (decisión de diseño
explícita, mismo principio que E1/E2/Raw): se define una función NUEVA,
`simulate_v3_tp`, estructuralmente paralela a `simulate_v3` — MISMO
código para SL inicial, breakeven (paso 3), activación+ratchet de
trailing (pasos 4-5), timeout y modelo de costos — con una única adición:
un chequeo de TP fijo (`entry ± tp_r*risk_pts`) insertado inmediatamente
después del test de stop (paso 1) y antes de la actualización de MFE
(paso 2), con la misma precedencia intrabar conservadora ya usada en
E1/V3-A (si stop y TP caen en la misma vela, gana el STOP). Verificado
por test (`test_equivalencia_con_v3a_cuando_tp_es_inalcanzable`): con
`tp_r` fijado a un valor estructuralmente inalcanzable, `simulate_v3_tp`
reproduce trade-por-trade el resultado de `backtest.simulate_v3` bajo
`EXIT_CONFIGS["V3-A (1R/2R/1R)"]` — prueba ejecutable, no solo
documental, de que la única diferencia real respecto de V3-A es el TP.

Comparadores: V3-A (`gestion_campaign_session_results.csv`, el ancla de
siempre); E1 (`gestion_espacio6_tp_fijo_campaign_results.csv`); Raw
(`gestion_espacio6_raw_results.csv`). Verificación de integridad
reforzada (mismo patrón que Raw): `n_entries` de V3-A+TP se compara
contra `n_entries` YA PUBLICADO de E1 y de Raw para cada (activo, año) —
los tres deberían coincidir por construcción (misma ruta determinista de
generación de entradas).

Fase A (idéntica en diseño a E1/E2/Raw, obligatoria antes de cualquier
resultado del candidato):
  1. Reproducir V3-A completo (mismas entradas, `backtest.EXIT_CONFIGS
     ["V3-A (1R/2R/1R)"]`, sin modificar) y exigir coincidencia 6/6 (una
     por activo/año) contra `gestion_campaign_session_results.csv`. Si
     CUALQUIERA falla, `AssertionError` inmediato.
  2. Solo si el paso 1 pasa 6/6: reutilizar EXACTAMENTE la misma lista de
     entradas para correr `V3-A + TP`.
  3. Verificar `n_entries` contra E1 y contra Raw publicados — no aborta
     si difiere, se reporta para auditar antes de interpretar resultados.

2024/ciego: NO se ejecuta bajo ninguna circunstancia en este contrato —
este script no define `run_blind_test`. Este experimento es, por mandato
explícito de la autorización, la ÚLTIMA celda de Gestión de bajo costo
autorizada por defecto — un resultado favorable aislado NO autoriza un
quinto experimento sin una decisión explícita nueva.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_espacio6_v3a_tp_campaign.py
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
# Config de la campaña — contrato aprobado (última celda de Gestión de       #
# bajo costo autorizada por defecto)                                         #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"
ENTRY_CANDIDATE = "C_market_close"
SESSION_LABEL = "dcv1_activo_15h"
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5
ATR_PERIOD_ANCHOR = 14
MAX_HOLD_ANCHOR = 20

# BE/trailing IDÉNTICOS a V3-A — la única variable experimental es TP_R.
V3A_EXIT_CFG = backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]   # {"be":1.0,"activation":2.0,"distance":1.0}
TP_R = 2.5   # constante congelada — misma especificación histórica que E1
             # (FRAMEWORK.md, sección "Gestión"), reutilizada, no un valor nuevo.

MECHANISM_LABEL = "V3A_mas_TP_2.5R"
CANDIDATE_LABEL = MECHANISM_LABEL
CANDIDATES = (CANDIDATE_LABEL,)

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Espacio 6 — Experimento 4: V3-A + TP 2.5R (breakeven ON be=1.0R, trailing ON "
    "activation=2.0R/distance=1.0R — idénticos a V3-A —, más TP fijo en 2.5R; "
    "Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/atr_mult=1.5/atr_period=14/"
    "max_hold=20/risk=0.005 fijos; sesión=dcv1_activo_15h única; comparadores: "
    "V3-A, E1 (TP fijo 2.5R sin BE/trailing), Raw (sin BE/trailing/TP). "
    "simulate_v3_tp es una función NUEVA, estructuralmente paralela a "
    "backtest.simulate_v3 (sin modificarlo), que agrega únicamente el chequeo de TP)"
)

_V3A_REF_PATH = "gestion_campaign_session_results.csv"
_V3A_REF_CANDIDATE = "dcv1_activo_15h"
_V3A_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")

_E1_REF_PATH = "gestion_espacio6_tp_fijo_campaign_results.csv"
_RAW_REF_PATH = "gestion_espacio6_raw_results.csv"


# --------------------------------------------------------------------------- #
# Mecanismo nuevo — SIN modificar backtest.simulate_v3                       #
# --------------------------------------------------------------------------- #
def simulate_v3_tp(df: pd.DataFrame, entry: dict, exit_cfg: dict, cfg: "backtest.Config",
                    tp_r: float = TP_R) -> dict:
    """Estructuralmente paralelo a backtest.simulate_v3 (mismo SL inicial,
    mismo breakeven, mismo trailing, mismo timeout, mismo modelo de
    costos) — la ÚNICA adición es un chequeo de TP fijo, insertado
    inmediatamente después del test de stop (precedencia conservadora:
    si stop y TP caen en la misma vela, gana el STOP, igual que en
    `gestion_espacio6_tp_fijo_campaign.py::simulate_tp_fixed`)."""
    i0        = entry["entry_idx"]
    direction = entry["direction"]
    e         = entry["entry"]
    risk_pts  = entry["risk_pts"]
    stop      = entry["sl0"]

    be_lvl    = exit_cfg["be"]
    act_lvl   = exit_cfg["activation"]
    dist_r    = exit_cfg["distance"]

    if direction == "long":
        tp_price = e + tp_r * risk_pts
    else:
        tp_price = e - tp_r * risk_pts

    n = len(df)
    max_fav_pts = 0.0
    trailing_on = False
    be_done     = False

    exit_idx   = None
    exit_price = None
    reason     = None

    end = min(i0 + cfg.max_hold + 1, n)
    for k in range(i0 + 1, end):
        c = df.iloc[k]

        # ── 1. Test de stop-out contra extremo ADVERSO, con stop del inicio de vela
        if direction == "long":
            if c["low"] <= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break
        else:
            if c["high"] >= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break

        # ── 1b. Test de TP (extremo FAVORABLE) — precedencia: stop gana
        #        si ambos caen en la misma vela (ya descartado arriba).
        if direction == "long":
            if c["high"] >= tp_price:
                exit_idx, exit_price, reason = k, tp_price, "tp"
                break
        else:
            if c["low"] <= tp_price:
                exit_idx, exit_price, reason = k, tp_price, "tp"
                break

        # ── 2. Actualizar maximo favorable con el extremo FAVORABLE de esta vela
        if direction == "long":
            fav_pts = c["high"] - e
        else:
            fav_pts = e - c["low"]
        if fav_pts > max_fav_pts:
            max_fav_pts = fav_pts

        fav_r = max_fav_pts / risk_pts

        # ── 3. Break-even (efecto para velas siguientes)
        if not be_done and fav_r >= be_lvl:
            if direction == "long":
                stop = max(stop, e)
            else:
                stop = min(stop, e)
            be_done = True

        # ── 4. Activacion de trailing
        if not trailing_on and fav_r >= act_lvl:
            trailing_on = True

        # ── 5. Trailing ratchet (solo a favor)
        if trailing_on:
            if direction == "long":
                trail_stop = e + (max_fav_pts - dist_r * risk_pts)
                stop = max(stop, trail_stop)
            else:
                trail_stop = e - (max_fav_pts - dist_r * risk_pts)
                stop = min(stop, trail_stop)

    # ── Timeout: cierre a mercado en la ultima vela evaluada
    if exit_idx is None:
        last = min(end - 1, n - 1)
        exit_idx   = last
        exit_price = df.iloc[last]["close"]
        reason     = "timeout"

    # ── PnL en R (neto de costos) — mismo modelo que simulate_v3
    if direction == "long":
        pnl_pts = exit_price - e
    else:
        pnl_pts = e - exit_price
    pnl_r_gross = pnl_pts / risk_pts
    cost_r      = (e * backtest.COST_PER_TRADE) / risk_pts
    pnl_r_net   = pnl_r_gross - cost_r

    return {
        "entry_time": df.index[i0],
        "exit_time":  df.index[exit_idx],
        "direction":  direction,
        "reason":     reason,
        "pnl_r":      round(pnl_r_net, 4),
        "duration_h": exit_idx - i0,
    }


def run_config_v3a_tp(df: pd.DataFrame, entries: list[dict], exit_cfg: dict,
                       cfg: "backtest.Config", tp_r: float = TP_R) -> pd.DataFrame:
    """Réplica estructural de backtest.run_config, parametrizada por
    simulate_v3_tp en vez de simulate_v3 — misma regla de 'una posición a
    la vez' (busy_until = exit_idx de la operación abierta)."""
    trades = []
    busy_until = -1
    for ent in entries:
        if ent["entry_idx"] <= busy_until:
            continue
        res = simulate_v3_tp(df, ent, exit_cfg, cfg, tp_r)
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
    return match.iloc[0] if not match.empty else None


def _raw_reference(asset: str, year: int) -> pd.Series | None:
    df = pd.read_csv(_RAW_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)]
    return match.iloc[0] if not match.empty else None


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
            f"\nLa corrida aborta antes de calcular la celda del candidato V3-A+TP."
        )


def run_integrity_check(asset: str, year: int):
    frame, cfg, entries = _entries_for_asset_year(asset, year)
    trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"], cfg)
    m_v3a = backtest.metrics(trades_v3a, cfg)
    _verify_against(asset, year, len(entries), len(trades_v3a), m_v3a, _v3a_reference(asset, year))
    return frame, cfg, entries, m_v3a


def check_entries_vs_reference(asset: str, year: int, n_entries: int) -> dict:
    e1_row = _e1_reference(asset, year)
    raw_row = _raw_reference(asset, year)
    n_e1 = int(e1_row["n_entries"]) if e1_row is not None else None
    n_raw = int(raw_row["n_entries"]) if raw_row is not None else None
    return {"asset": asset, "year": year, "n_entries": n_entries,
            "n_entries_e1": n_e1, "match_e1": (n_entries == n_e1) if n_e1 is not None else None,
            "n_entries_raw": n_raw, "match_raw": (n_entries == n_raw) if n_raw is not None else None}


def _row(asset: str, year: int, entries: list[dict], trades: pd.DataFrame,
         m: dict | None, m_v3a: dict | None, m_e1: dict | None, m_raw: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "bias": BIAS_CANDIDATE, "trigger": TRIGGER_CANDIDATE,
        "entry": ENTRY_CANDIDATE, "mechanism": MECHANISM_LABEL, "candidate": CANDIDATE_LABEL,
        "exit_config": EXIT_CONFIG_LABEL, "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "metrics_v3a": m_v3a,
        "metrics_e1": m_e1, "metrics_raw": m_raw, "trades": trades,
    }


def run_asset_year_target(asset: str, year: int, frame: pd.DataFrame, cfg: "backtest.Config",
                           entries: list[dict], m_v3a: dict | None) -> dict:
    trades = run_config_v3a_tp(frame, entries, V3A_EXIT_CFG, cfg, TP_R)
    m = backtest.metrics(trades, cfg)
    e1_row = _e1_reference(asset, year)
    raw_row = _raw_reference(asset, year)
    m_e1 = e1_row.to_dict() if e1_row is not None else None
    m_raw = raw_row.to_dict() if raw_row is not None else None
    return _row(asset, year, entries, trades, m, m_v3a, m_e1, m_raw)


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> tuple[list[dict], list[dict]]:
    known: dict[tuple[str, int], tuple] = {}
    entry_checks: list[dict] = []
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)
            frame, cfg, entries, m_v3a = known[(asset, year)]
            entry_checks.append(check_entries_vs_reference(asset, year, len(entries)))

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            frame, cfg, entries, m_v3a = known[(asset, year)]
            rows.append(run_asset_year_target(asset, year, frame, cfg, entries, m_v3a))
    return rows, entry_checks


# --------------------------------------------------------------------------- #
# Reporte                                                                     #
# --------------------------------------------------------------------------- #
def _delta(a, b):
    if a is None or b is None:
        return None
    try:
        return round(float(a) - float(b), 4)
    except (TypeError, ValueError):
        return None


def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        m_v3a = r["metrics_v3a"] or {}
        m_e1 = r["metrics_e1"] or {}
        m_raw = r["metrics_raw"] or {}
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
            "reason_stop": reasons.get("stop", 0), "reason_tp": reasons.get("tp", 0),
            "reason_timeout": reasons.get("timeout", 0),
            # vs V3-A
            "pf_v3a": m_v3a.get("pf"), "max_dd_v3a": m_v3a.get("max_dd"),
            "exp_r_v3a": m_v3a.get("exp_r"), "freq_v3a": m_v3a.get("freq"),
            "n_trades_v3a": m_v3a.get("trades"),
            "delta_pf_v3a": _delta(m.get("pf"), m_v3a.get("pf")),
            "delta_max_dd_v3a": _delta(m.get("max_dd"), m_v3a.get("max_dd")),
            "delta_exp_r_v3a": _delta(m.get("exp_r"), m_v3a.get("exp_r")),
            "delta_freq_v3a": _delta(freq, m_v3a.get("freq")),
            "delta_n_trades_v3a": (n_trades - m_v3a["trades"]) if m_v3a.get("trades") is not None else None,
            # vs E1
            "pf_e1": m_e1.get("pf"), "max_dd_e1": m_e1.get("max_dd"), "exp_r_e1": m_e1.get("exp_r"),
            "delta_pf_e1": _delta(m.get("pf"), m_e1.get("pf")),
            "delta_max_dd_e1": _delta(m.get("max_dd"), m_e1.get("max_dd")),
            "delta_exp_r_e1": _delta(m.get("exp_r"), m_e1.get("exp_r")),
            # vs Raw
            "pf_raw": m_raw.get("pf"), "max_dd_raw": m_raw.get("max_dd"), "exp_r_raw": m_raw.get("exp_r"),
            "delta_pf_raw": _delta(m.get("pf"), m_raw.get("pf")),
            "delta_max_dd_raw": _delta(m.get("max_dd"), m_raw.get("max_dd")),
            "delta_exp_r_raw": _delta(m.get("exp_r"), m_raw.get("exp_r")),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  Espacio 6 — Experimento 4: V3-A + TP 2.5R (comparadores: V3-A, E1, Raw)\n"
          f"  Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "n_entries", "n_trades", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "max_dd", "freq", "reason_stop", "reason_tp", "reason_timeout", "gate_pass",
            "pf_v3a", "delta_pf_v3a", "pf_e1", "delta_pf_e1", "pf_raw", "delta_pf_raw"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    print("  Ninguna combinación pasa los 4 gates." if passing.empty else passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN (criterio de PASS del framework): sobrevivientes (ambos años, "
          f"por activo) y ranking por PF 2023\n{'='*100}")
    print("  Sin combinaciones para evaluar." if decision.empty else decision.to_string(index=False))
    for asset, g in decision.groupby("asset"):
        if g[g["survives_both_years"]].empty:
            print(f"\n  {asset}: V3-A+TP no demuestra evidencia suficiente para cumplir "
                  f"los 4 gates de FRAMEWORK.md en 2022+2023.")


def main() -> None:
    results, entry_checks = run_campaign()

    print(f"\n{'='*100}\n  Verificación de integridad — n_entries vs E1/Raw publicados\n{'='*100}")
    for c in entry_checks:
        s_e1 = "OK" if c["match_e1"] else ("SIN REF" if c["match_e1"] is None else "MISMATCH")
        s_raw = "OK" if c["match_raw"] else ("SIN REF" if c["match_raw"] is None else "MISMATCH")
        print(f"  {c['asset']} {c['year']}: n_entries={c['n_entries']} vs E1={c['n_entries_e1']} ({s_e1})"
              f" vs Raw={c['n_entries_raw']} ({s_raw})")

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_espacio6_v3a_tp_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "gestion_espacio6_v3a_tp_campaign_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
