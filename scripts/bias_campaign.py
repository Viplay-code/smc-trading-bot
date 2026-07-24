#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/bias_campaign.py — Campaña de validación empírica Bias A vs A2
(Iniciativa G, backlog post-Fase-B). Implementa el contrato técnico aprobado
2026-07-24 (plan v2: fuente de datos dc_v1, sin umbral de desempate fijado de
antemano).

Objetivo: determinar, con datos reales 2022/2023/2024, si el candidato Bias
"A" (`research.BIAS_LAYERS["A_ema200_neutral"]`, lo que usa `bot.py`) o "A2"
(`research.bias_A2_ema200_neutral_1h_held`, lo que `backtest.py` calcula
inline) produce mejores métricas para T1 — o si ninguno pasa los 4 gates de
`FRAMEWORK.md`, señal objetiva para diseñar un tercer candidato.

Fuente de datos: datasets canónicos de dc_v1 (`build_dc_v1()` +
`validate_dc_v1()`), NO el fetch legacy de `backtest.py::download()`. Se usan
SOLO las columnas OHLCV de dc_v1 — `htf_close_prev`/`htf_ema200_prev`/
`htf_bias` del propio dc_v1 se ignoran a propósito: esa columna es un TERCER
candidato de Bias (compara el cierre 4H ya cerrado contra su EMA200, ambos
sostenidos constantes durante toda la ventana 1H — ni A ni A2), no parte de
esta comparación.

Disciplina continuo-luego-slice (P-3): el resample a 4H y el cálculo de A/A2
se hacen sobre el frame COMPLETO que devuelve `build_dc_v1()` para un
(activo, año) — que ya incluye el buffer de 90 días de warmup
(`market_data.config.WARMUP_BUFFER_DAYS`) antes del 1-ene de ese año — y
recién DESPUÉS se corta con `periods.period_slice()`. Cortar primero
reintroduciría el problema de warmup contaminado que dc_v1 existe para
evitar. Verificado que hay margen suficiente: el buffer (90 días ≈ 540 velas
4H) excede ampliamente las ~200 velas 4H (33.3 días) que necesita cualquiera
de los dos candidatos, incluso descontando lo que `trim_warmup` de dc_v1 ya
consume para su propio `htf_ema200_prev`.

Requiere `data/raw/` poblado por `scripts/download_market_data.py` — cada
(activo, año) se carga y procesa de forma INDEPENDIENTE, igual que
`scripts/build_dc_v1_datasets.py::build_one` (mismo patrón de archivo-por-año
que usa `market_data`, no un archivo continuo multi-año).

BLOQUEADO en este sandbox (HTTP 451, `data/raw/` vacío). Este script
implementa el protocolo aprobado; correrlo con datos reales queda pendiente
de un entorno con acceso a Binance. La validación de este script en este
entorno es SOLO estructural, sobre datos sintéticos con la forma del
contrato dc_v1 — ver `research/tests/test_bias_campaign.py`.

Uso (desde la raíz del repo, con `data/raw/` poblado):
    python scripts/bias_campaign.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/bias_campaign.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import research
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
CANDIDATES = ("A", "A2")
IN_SAMPLE_YEAR = 2022
VALIDATION_YEAR = 2023
BLIND_YEAR = 2024

# Gate de frecuencia de FRAMEWORK.md (rango 6-12/mes/activo), NO el piso
# freq>=4 de backtest.py::passes() — ver plan v2 §6.
FREQ_MIN_PER_MONTH = 6
FREQ_MAX_PER_MONTH = 12

# Resample 4H — misma convención que dc_v1/pipeline.py::add_htf (OHLCV /
# RESAMPLE_RULES). Replicada acá, no importada: son internos de
# dc_v1.pipeline, no del punto de entrada público (TARGET_ARCHITECTURE.md §2).
_OHLCV = ["open", "high", "low", "close", "volume"]
_RESAMPLE_RULES = {"open": "first", "high": "max", "low": "min",
                    "close": "last", "volume": "sum"}

# Formato del CSV crudo — misma lógica que scripts/build_dc_v1_datasets.py::
# load_raw_csv / scripts/inspect_single_dataset.py::load_raw_csv (ya
# duplicada entre esos dos por convención propia del repo, ver su docstring).
_TIME_COL = "open_time"
_OPEN_COL, _HIGH_COL, _LOW_COL, _CLOSE_COL, _VOLUME_COL = "open", "high", "low", "close", "volume"
_TIME_UNIT = "ms"


# --------------------------------------------------------------------------- #
# Carga + preparación de datos                                                #
# --------------------------------------------------------------------------- #
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


def resample_4h(df1h: pd.DataFrame) -> pd.DataFrame:
    """1H OHLCV -> 4H OHLCV, misma regla que dc_v1::add_htf (label='left',
    closed='left'). Necesario porque build_dc_v1() no expone el frame 4H
    intermedio que usa internamente — solo sus columnas derivadas
    (htf_close_prev/htf_ema200_prev/htf_bias), que esta campaña ignora."""
    return (
        df1h[_OHLCV]
        .resample("4h", label="left", closed="left")
        .agg(_RESAMPLE_RULES)
        .dropna(subset=["close"])
    )


def apply_bias(df1h: pd.DataFrame, df4h: pd.DataFrame, candidate: str) -> pd.Series:
    """Bias a granularidad 1H para `candidate` ("A" o "A2"), dominio
    int8 {-1,0,1}, índice alineado a df1h.

    A2 (research.bias_A2_ema200_neutral_1h_held) ya opera nativamente a 1H —
    se usa tal cual, es un port literal de backtest.py::build_features.

    A (research.BIAS_LAYERS["A_ema200_neutral"]) clasifica una vez por vela
    4H, sin shift — así lo consume bot.py, donde df4h en producción solo
    contiene velas ya cerradas. Para usarla a granularidad 1H sin lookahead,
    hay que replicar lo que bot.py vería en la práctica: en cualquier
    instante, el valor de Bias disponible es el de la última vela 4H YA
    CERRADA — la clasificación de A desplazada una posición (shift(1)) antes
    de sostenerla (ffill) sobre las filas 1H siguientes. Sin este shift se
    filtrarían señales T1 usando una vela 4H todavía en formación — el mismo
    tipo de lookahead que A2 evita con su propio shift(1) interno.
    """
    if candidate == "A2":
        return research.bias_A2_ema200_neutral_1h_held(df1h, df4h)
    if candidate == "A":
        bias_fn = research.BIAS_LAYERS["A_ema200_neutral"]
        bias_4h = bias_fn(df4h)
        held = bias_4h.shift(1).rename("bias")
        merged = df1h[[]].join(held, how="left").ffill()
        # shift(1) introduce un NaN en la primera vela 4H de bias_4h; antes del
        # primer match de join, esas filas 1H iniciales también quedan NaN.
        # fillna(0) replica la misma convención NaN->neutral que ya usa
        # bias_A_ema200_neutral internamente (np.where sobre NaN cae en la
        # rama 0 por construcción) — no es una convención nueva acá.
        return merged["bias"].fillna(0).astype("int8")
    raise ValueError(f"candidato de bias desconocido: {candidate!r} (esperado 'A' o 'A2')")


def load_asset_year(asset: str, year: int) -> pd.DataFrame:
    """Carga el crudo (asset, year) de data/raw/, corre build_dc_v1() +
    validate_dc_v1(), calcula bias_A/bias_A2 sobre el frame COMPLETO
    (pre-slice, ver docstring del módulo), y recién entonces corta al año con
    periods.period_slice(). Devuelve el DataFrame 1H recortado con columnas
    bias_A/bias_A2 (int8) agregadas al contrato de dc_v1.
    """
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

    df4h_full = resample_4h(df_full)
    df_full = df_full.copy()
    df_full["bias_A"] = apply_bias(df_full, df4h_full, "A")
    df_full["bias_A2"] = apply_bias(df_full, df4h_full, "A2")

    return period_slice(df_full, year)


def to_backtest_frame(df: pd.DataFrame, bias_numeric: pd.Series, cfg: "backtest.Config") -> pd.DataFrame:
    """Adapta las columnas del contrato dc_v1 (open/high/low/close/volume/
    atr14/...) al formato que esperan backtest.py::find_entries/simulate_v3
    (mismas columnas que produce backtest.py::build_features): atr,
    in_session, bias como string "long"/"short"/"neutral" (no el int8
    {-1,0,1} de research.layers). No se modifica backtest.py — el adaptador
    vive acá.
    """
    out = df[["open", "high", "low", "close"]].copy()
    out["atr"] = df["atr14"]
    h_idx = out.index.hour
    out["in_session"] = [any(s <= hh < e for s, e in cfg.sessions) for hh in h_idx]
    bias_map = {1: "long", -1: "short", 0: "neutral"}
    out["bias"] = bias_numeric.map(bias_map)
    return out


# --------------------------------------------------------------------------- #
# Gate + orquestación                                                         #
# --------------------------------------------------------------------------- #
def gate_check(m: dict | None) -> bool:
    """Gates de FRAMEWORK.md, literales — NO backtest.py::passes() (su piso
    freq>=4 no aplica el techo de 12/mes que sí exige FRAMEWORK.md)."""
    if m is None:
        return False
    return bool(
        m["pf"] >= 1.50
        and m["max_dd"] >= -10
        and m["exp_r"] > 0
        and FREQ_MIN_PER_MONTH <= m["freq"] <= FREQ_MAX_PER_MONTH
    )


def run_asset_year(asset: str, year: int, cfg: "backtest.Config") -> list[dict]:
    """Corre ambos candidatos × ambas configs de salida para un (activo,
    año). Devuelve una fila de resultado por combinación (candidato, config
    de salida) con todas las métricas — no aplica ninguna regla de selección
    entre A/A2 ni agrega entre años/activos; eso queda para la interpretación
    posterior de bias_campaign_results.csv (plan v2 §6: sin umbral de
    desempate fijado de antemano)."""
    df_full = load_asset_year(asset, year)
    rows = []
    for candidate in CANDIDATES:
        bias_col = df_full[f"bias_{candidate}"]
        frame = to_backtest_frame(df_full, bias_col, cfg)
        entries = backtest.find_entries(frame, cfg)
        for exit_name, exit_cfg in backtest.EXIT_CONFIGS.items():
            trades = backtest.run_config(frame, entries, exit_cfg, cfg)
            m = backtest.metrics(trades, cfg)
            rows.append({
                "asset": asset, "year": year, "candidate": candidate,
                "exit_config": exit_name, "n_entries": len(entries),
                "n_trades": len(trades), "metrics": m, "gate_pass": gate_check(m),
            })
    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test,
    invocación deliberadamente separada (TARGET_ARCHITECTURE.md §8)."""
    cfg = backtest.Config()
    results: list[dict] = []
    for year in years:
        for asset in assets:
            results.extend(run_asset_year(asset, year, cfg))
    return results


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` explícito (el ganador ya
    congelado tras Fases 1+2) — correr esto sin haber decidido antes A/A2
    sobre 2022+2023 sería exactamente el uso indebido del blind set que
    FRAMEWORK.md prohíbe."""
    if candidate not in CANDIDATES:
        raise ValueError(
            "run_blind_test requiere un candidato ya congelado ('A' o 'A2') "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una decisión previa."
        )
    cfg = backtest.Config()
    results: list[dict] = []
    for asset in assets:
        df_full = load_asset_year(asset, BLIND_YEAR)
        bias_col = df_full[f"bias_{candidate}"]
        frame = to_backtest_frame(df_full, bias_col, cfg)
        entries = backtest.find_entries(frame, cfg)
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
# Reporte — todas las métricas, SIN umbral de desempate (plan v2 §6): la
# campaña no elige un ganador cuando ambos pasan los gates, solo reporta.
# --------------------------------------------------------------------------- #
def results_to_frame(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["metrics"] or {}
        reasons = m.get("reasons") or {}
        rows.append({
            "asset": r["asset"], "year": r["year"], "candidate": r["candidate"],
            "exit_config": r["exit_config"], "n_entries": r["n_entries"],
            "n_trades": r["n_trades"], "gate_pass": r["gate_pass"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": m.get("freq"),
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA BIAS A vs A2 — resultados completos (sin desempate aplicado)\n{'='*100}")
    cols = ["asset", "year", "candidate", "exit_config", "n_trades",
            "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "be",
            "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — señal para considerar un tercer candidato.")
    else:
        print(passing[cols].to_string(index=False))


# --------------------------------------------------------------------------- #
# Decisión programática (plan v2 §5-6, grano confirmado 2026-07-24): gates y
# ranking se evalúan POR ACTIVO, nunca agregados entre los 3 — un activo no
# puede compensar el mal desempeño de otro. Solo aplica al flujo 2022+2023
# (run_campaign); no tiene sentido para --blind (un solo año, un candidato ya
# congelado, nada que "sobrevivir ambos años").
# --------------------------------------------------------------------------- #
def summarize_decision(df: pd.DataFrame) -> pd.DataFrame:
    """Por cada (activo, candidato, config de salida): sobrevive si pasa los
    4 gates en 2022 Y en 2023 para ESE activo (plan v2 §6, puntos 1-2). Entre
    sobrevivientes, rankea por PF de 2023, por activo — el ranking nunca
    compara entre activos ni promedia entre ellos. Combinaciones a las que
    les falta alguno de los dos años en `df` se reportan como no evaluables
    (survives_both_years=False), no se descartan en silencio.
    """
    required_years = (IN_SAMPLE_YEAR, VALIDATION_YEAR)
    rows = []
    for (asset, candidate, exit_config), g in df.groupby(["asset", "candidate", "exit_config"]):
        by_year = g.set_index("year")
        pf_2022 = by_year["pf"].get(IN_SAMPLE_YEAR)
        pf_2023 = by_year["pf"].get(VALIDATION_YEAR)
        gate_2022 = by_year["gate_pass"].get(IN_SAMPLE_YEAR)
        gate_2023 = by_year["gate_pass"].get(VALIDATION_YEAR)
        has_both_years = all(y in by_year.index for y in required_years)
        survives = bool(has_both_years and gate_2022 and gate_2023)
        rows.append({
            "asset": asset, "candidate": candidate, "exit_config": exit_config,
            "pf_2022": pf_2022, "pf_2023": pf_2023,
            "gate_2022": bool(gate_2022) if gate_2022 is not None else None,
            "gate_2023": bool(gate_2023) if gate_2023 is not None else None,
            "survives_both_years": survives,
        })
    decision = pd.DataFrame(rows)
    decision["rank_within_asset"] = pd.NA
    if decision.empty:
        return decision

    survivors = decision[decision["survives_both_years"]]
    for asset, g in survivors.groupby("asset"):
        ranked = g.sort_values("pf_2023", ascending=False)
        decision.loc[ranked.index, "rank_within_asset"] = range(1, len(ranked) + 1)

    return decision.sort_values(
        ["asset", "survives_both_years", "rank_within_asset"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ninguna combinación sobrevive 2022+2023 — "
                  f"señal para considerar un tercer candidato en este activo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="Candidato ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el ganador ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "bias_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "bias_campaign_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
