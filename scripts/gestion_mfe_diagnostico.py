#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_mfe_diagnostico.py — Estudio diagnóstico de la distribución
MFE/MAE del baseline (Bias=A, Trigger=T1_ema_cross, Entry=C_market_close,
atr_mult=1.5, sesión=control_8h — el mismo de gestion_campaign_atr_mult.py),
sobre datos reales dc_v1 2022+2023.

NO es una campaña con gates ni candidatos: es una medición previa a decidir
si procede una campaña de Gestión (BE/activación/trailing desacoplados,
"H2"). Diseño metodológico acordado 2026-07-29, en dos pasos deliberadamente
separados (no deben colapsarse en un solo test):

  Paso 1 — Diagnóstico (responde H_MFE tal como está formulada): ¿hay
  evidencia compatible con que la gestión activa (BE/trailing de V3-A) esté
  limitando la captura del movimiento favorable disponible? Comparación
  homogénea (media con media, MISMA población: los trades que V3-A ya marcó
  como ganadores) entre `avg_win` (ya realizado) y la media de MFE_R (el
  techo real, sin ninguna regla de salida). Es descriptivo por diseño — la
  magnitud y consistencia del gap entre activos/años ES la evidencia, no se
  fuerza un corte binario arbitrario acá.

  Paso 2 — Evaluación estratégica (solo se interpreta si el Paso 1 muestra
  gap positivo): si ese margen existe, ¿alcanzaría para el gate de PF≥1.50
  de FRAMEWORK.md? Umbral NO arbitrario: `avg_win_requerido` se deriva
  algebraicamente del gate ya ratificado, usando WR/avg_loss YA MEDIDOS de
  este mismo baseline (no una elección nueva) —
      avg_win_requerido = 1.50 * (1 - WR) * |avg_loss| / WR
  Se compara contra la misma media de MFE_R del Paso 1.

El estudio termina con una recomendación metodológica EXPLÍCITA (procede o
no procede H2), no solo con números para interpretación manual — pero esa
recomendación es de lectura humana sobre el reporte, no una decisión
automática de gates como en las campañas de Bias/Trigger/Entry/Gestión-ATR/
Gestión-sesión (esas SÍ tienen un veredicto binario por diseño; esto es un
diagnóstico previo a decidir si vale la pena correr una de esas).

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados): de scripts/bias_campaign.py — load/resample/apply_bias/
to_backtest_frame. De scripts/trigger_campaign.py — find_entries_for_trigger
(T1 fijo). De backtest.py — run_config/simulate_v3/metrics/EXIT_CONFIGS, sin
tocar ninguno. La medición de MFE/MAE en sí (`compute_mfe_mae`) es la única
pieza nueva: recorre la MISMA ventana de `max_hold` velas que ya usa
`simulate_v3`, con la MISMA fórmula de `fav_pts`, pero sin aplicar ninguna
regla de salida (sin stop-out, sin BE, sin trailing, sin TP) — de ahí que no
se reutilice `simulate_v3` directamente, esa función por diseño SÍ aplica
esas reglas.

NO depende de `archive/analisis_mfe_mae.py` (que partía de un CSV histórico
con una columna `mfe_r` ya aproximada, no de la trayectoria real) — acá el
MFE/MAE se calcula vela a vela sobre los datos reales 2022/2023 de dc_v1.

Requiere `data/raw/` poblado (mismo requisito que todas las campañas
anteriores). BLOQUEADO en este sandbox (HTTP 451, data/raw/ vacío) —
validado acá solo estructuralmente, ver
research/tests/test_gestion_mfe_diagnostico.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_mfe_diagnostico.py
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import pandas as pd

import backtest
import research
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Config del diagnóstico — mismo baseline que gestion_campaign_atr_mult.py    #
# --------------------------------------------------------------------------- #
BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"
ENTRY_CANDIDATE = "C_market_close"
V3_A = "V3-A (1R/2R/1R)"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
YEARS = (IN_SAMPLE_YEAR, VALIDATION_YEAR)  # 2024 no se toca (disciplina de blind set)

R_THRESHOLDS = (1.0, 1.5, 2.0, 2.5)  # contexto descriptivo, no decisivo

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
    """Idéntico a trigger_campaign.py::load_asset_year (Bias=A resuelto sobre
    el frame completo antes de cortar por período, disciplina P-3)."""
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
# Medición MFE/MAE — la única pieza nueva. Misma ventana (max_hold) y misma  #
# fórmula de fav_pts que backtest.py::simulate_v3, SIN ninguna regla de      #
# salida (sin stop-out, sin BE, sin trailing, sin TP).                       #
# --------------------------------------------------------------------------- #
def compute_mfe_mae(frame: pd.DataFrame, entry: dict, cfg: "backtest.Config") -> dict:
    i0 = entry["entry_idx"]
    direction = entry["direction"]
    e = entry["entry"]
    risk_pts = entry["risk_pts"]
    n = len(frame)
    end = min(i0 + cfg.max_hold + 1, n)

    max_fav_pts = 0.0
    max_adv_pts = 0.0
    for k in range(i0 + 1, end):
        c = frame.iloc[k]
        if direction == "long":
            fav_pts = c["high"] - e
            adv_pts = e - c["low"]
        else:
            fav_pts = e - c["low"]
            adv_pts = c["high"] - e
        if fav_pts > max_fav_pts:
            max_fav_pts = fav_pts
        if adv_pts > max_adv_pts:
            max_adv_pts = adv_pts

    return {
        "entry_idx": i0,
        "direction": direction,
        "mfe_r": round(max_fav_pts / risk_pts, 4),
        "mae_r": round(max_adv_pts / risk_pts, 4),
    }


def mfe_mae_for_v3a_trades(frame: pd.DataFrame, cfg: "backtest.Config",
                            entries: list[dict], trades_v3a: pd.DataFrame) -> pd.DataFrame:
    """Empareja cada trade que V3-A realmente generó (tras el filtro de
    'una posición a la vez', que depende de la dinámica de salida de V3-A y
    no se puede re-derivar sin correrlo) con su entrada original, y calcula
    MFE_R/MAE_R para esa MISMA población — necesario para que la comparación
    del Paso 1/2 sea sobre los mismos trades que ya componen `avg_win`/`wr`/
    `avg_loss` en `backtest.metrics()`."""
    by_idx = {ent["entry_idx"]: ent for ent in entries}
    rows = []
    for _, trade in trades_v3a.iterrows():
        entry_idx = frame.index.get_loc(trade["entry_time"])
        ent = by_idx[entry_idx]
        m = compute_mfe_mae(frame, ent, cfg)
        rows.append({
            "entry_idx": entry_idx, "direction": ent["direction"],
            "pnl_r_v3a": trade["pnl_r"], "is_winner": bool(trade["pnl_r"] > 0),
            "mfe_r": m["mfe_r"], "mae_r": m["mae_r"],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Orquestación por (activo, año)                                             #
# --------------------------------------------------------------------------- #
def run_asset_year(asset: str, year: int) -> dict:
    cfg = backtest.Config()
    df_full = load_asset_year(asset, year)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)

    trades_v3a = backtest.run_config(frame, entries, backtest.EXIT_CONFIGS[V3_A], cfg)
    m = backtest.metrics(trades_v3a, cfg)

    per_trade = mfe_mae_for_v3a_trades(frame, cfg, entries, trades_v3a)

    winners = per_trade[per_trade["is_winner"]]
    mean_mfe_winners = round(winners["mfe_r"].mean(), 4) if not winners.empty else None
    median_mfe_winners = round(winners["mfe_r"].median(), 4) if not winners.empty else None
    mean_mfe_all = round(per_trade["mfe_r"].mean(), 4) if not per_trade.empty else None

    dist = {}
    for th in R_THRESHOLDS:
        dist[f"pct_mfe_ge_{th}"] = (
            round(100 * (per_trade["mfe_r"] >= th).mean(), 1) if not per_trade.empty else None
        )

    avg_win_requerido = None
    if m is not None and m["wr"] > 0:
        wr_frac = m["wr"] / 100.0
        avg_win_requerido = round(1.50 * (1 - wr_frac) * abs(m["avg_loss"]) / wr_frac, 4)

    return {
        "asset": asset, "year": year,
        "n_trades": len(trades_v3a), "n_winners": int(winners.shape[0]),
        "avg_win": m["avg_win"] if m else None,
        "avg_loss": m["avg_loss"] if m else None,
        "wr": m["wr"] if m else None,
        "exp_r": m["exp_r"] if m else None,
        "mean_mfe_winners": mean_mfe_winners,
        "median_mfe_winners": median_mfe_winners,
        "mean_mfe_all": mean_mfe_all,
        "avg_win_requerido": avg_win_requerido,
        "gap_paso1": (round(mean_mfe_winners - m["avg_win"], 4)
                      if (mean_mfe_winners is not None and m is not None) else None),
        **dist,
        "_per_trade": per_trade,
    }


def run_diagnostico(assets: tuple[str, ...] = ASSETS, years: tuple[int, ...] = YEARS) -> list[dict]:
    return [run_asset_year(asset, year) for year in years for asset in assets]


# --------------------------------------------------------------------------- #
# Reporte — dos pasos separados + recomendación metodológica explícita       #
# --------------------------------------------------------------------------- #
def summary_frame(results: list[dict]) -> pd.DataFrame:
    cols = ["asset", "year", "n_trades", "n_winners", "avg_win", "avg_loss", "wr", "exp_r",
            "mean_mfe_winners", "median_mfe_winners", "mean_mfe_all", "gap_paso1",
            "avg_win_requerido"] + [f"pct_mfe_ge_{th}" for th in R_THRESHOLDS]
    return pd.DataFrame([{k: r[k] for k in cols} for r in results])


def print_report(results: list[dict]) -> str:
    df = summary_frame(results)
    lines = []
    lines.append("=" * 100)
    lines.append("  DIAGNÓSTICO MFE/MAE — Bias=A, Trigger=T1, Entry=C, atr_mult=1.5, sesión=control_8h")
    lines.append("=" * 100)
    lines.append(df.to_string(index=False))

    lines.append("\n" + "-" * 100)
    lines.append("  PASO 1 — ¿hay evidencia compatible con que la gestión limite la captura?")
    lines.append("-" * 100)
    paso1_positivo = []
    for r in results:
        gap = r["gap_paso1"]
        if gap is None:
            lines.append(f"  {r['asset']} {r['year']}: sin datos suficientes para evaluar.")
            continue
        signo = "positivo" if gap > 0 else ("nulo" if gap == 0 else "negativo")
        lines.append(f"  {r['asset']} {r['year']}: media(MFE_R) en ganadores={r['mean_mfe_winners']} "
                      f"vs avg_win={r['avg_win']} -> gap {signo} ({gap:+.3f}R)")
        if gap is not None and gap > 0:
            paso1_positivo.append((r["asset"], r["year"]))

    consistente = len(paso1_positivo) == len(results)
    if consistente and results:
        lines.append("\n  Gap positivo y consistente en todos los (activo, año) evaluados: "
                      "evidencia compatible con que la gestión activa (BE/trailing de V3-A) "
                      "esté limitando la captura del movimiento favorable disponible.")
    elif paso1_positivo:
        lines.append(f"\n  Gap positivo solo en {paso1_positivo} — evidencia INCONSISTENTE entre "
                      "activos/años, no se reporta un veredicto único para el Paso 1.")
    else:
        lines.append("\n  Sin gap positivo en ningún (activo, año): sin evidencia de que la "
                      "gestión activa esté limitando la captura en este baseline.")

    lines.append("\n" + "-" * 100)
    lines.append("  PASO 2 — si el margen existe, ¿alcanzaría el gate de PF>=1.50?")
    lines.append("-" * 100)
    paso2_alcanza = []
    for r in results:
        if r["mean_mfe_winners"] is None or r["avg_win_requerido"] is None:
            continue
        alcanza = r["mean_mfe_winners"] >= r["avg_win_requerido"]
        lines.append(f"  {r['asset']} {r['year']}: media(MFE_R)={r['mean_mfe_winners']} vs "
                      f"avg_win_requerido={r['avg_win_requerido']} -> "
                      f"{'ALCANZA' if alcanza else 'NO ALCANZA'}")
        if alcanza:
            paso2_alcanza.append((r["asset"], r["year"]))

    lines.append("\n" + "=" * 100)
    lines.append("  RECOMENDACIÓN METODOLÓGICA")
    lines.append("=" * 100)
    if not results:
        lines.append("  Sin datos para recomendar.")
    elif consistente and len(paso2_alcanza) == len(results):
        lines.append("  Evidencia suficiente para justificar una campaña experimental específica "
                      "sobre gestión (H2: BE/activación/trailing desacoplados) — el margen de "
                      "captura existe (Paso 1) y, en el mejor de los casos, alcanzaría el gate de "
                      "PF>=1.50 (Paso 2) de forma consistente en los activos/años evaluados. "
                      "PROCEDE H2.")
    elif consistente and paso2_alcanza:
        lines.append(f"  Paso 1 respaldado en todos los (activo,año); Paso 2 alcanza solo en "
                      f"{paso2_alcanza}. Evidencia MIXTA — H2 podría justificarse para un "
                      "subconjunto de activos, no de forma uniforme. NO se recomienda proceder "
                      "con H2 aplicada a los 3 activos por igual sin acotar el alcance.")
    elif consistente:
        lines.append("  Paso 1 respaldado (hay margen de captura), pero Paso 2 no alcanza el gate "
                      "de PF>=1.50 en ningún (activo,año) evaluado — ni una captura perfecta del "
                      "movimiento disponible cumpliría el framework. NO PROCEDE H2 como respuesta "
                      "suficiente; redirigir hacia recalibración de TP o candidatos de Capa 1/2 "
                      "todavía sin probar.")
    else:
        lines.append("  Sin evidencia consistente de que la gestión limite la captura (Paso 1). "
                      "NO PROCEDE H2 — lo que sea que limita el resultado no parece ser la "
                      "gestión activa; redirigir la investigación hacia otra hipótesis.")

    return "\n".join(lines)


def main() -> None:
    results = run_diagnostico()

    per_trade_all = pd.concat(
        [r["_per_trade"].assign(asset=r["asset"], year=r["year"]) for r in results],
        ignore_index=True,
    ) if results else pd.DataFrame()

    report = print_report(results)
    print(report)

    summary_frame(results).to_csv("gestion_mfe_diagnostico_summary.csv", index=False)
    per_trade_all.to_csv("gestion_mfe_diagnostico_trades.csv", index=False)
    print(f"\nResumen exportado a gestion_mfe_diagnostico_summary.csv "
          f"({len(results)} filas), detalle por trade a gestion_mfe_diagnostico_trades.csv "
          f"({len(per_trade_all)} filas)")


if __name__ == "__main__":
    main()
