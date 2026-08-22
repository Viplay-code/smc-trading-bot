#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/bias_b_campaign.py — Bias B: EMA50+EMA200 4H (cruce de medias),
candidato "B" de Capa 1 de FRAMEWORK.md, contra el comparador Bias A bajo el
MISMO contrato. Diseño científico formal cerrado 2026-08-22 (desempate ex
ante Espacio 5 Bias B vs Bias C — B elegido por reutilización de primitivas
ya canónicas, `dc_v1.ema()`, NO por expectativa de resultado; ver
`docs/research/EXPERIMENTAL_ROADMAP.md`, "Estado de priorización — Espacio
5"). Ver `research.layers::bias_B_ema50_ema200_cross` para la formalización
matemática completa (sign(EMA50_4H-EMA200_4H), sin zona neutral, estado por
vela 4H, convención NaN->0 igual a Bias A).

Objetivo científico: bajo un contrato idéntico en todo lo demás (Trigger,
Entry, sesión, Gestión, ATR, `max_hold`, riesgo, activos, años), ¿el filtro
de contexto HTF por cruce de medias (B) produce métricas distintas —mejores,
peores o estadísticamente indistinguibles— de las del filtro de distancia a
un solo nivel de EMA200 con zona neutral (A)? Bias es la ÚNICA variable
experimental.

Comparador principal: Bias A bajo el MISMO Trigger/Entry/sesión/Gestión que
B — único diseño que aísla Bias como variable (mismo argumento lógico que
hizo de `A_sweep_bos` el comparador válido de Trigger C). Contrato congelado
2026-08-22 (sin modificar): Bias objetivo=B (`research.BIAS_LAYERS
["B_ema50_ema200_cross"]`)/Bias comparador=A/Trigger=`T1_ema_cross`/
Entry=`C_market_close` (ambos vía `backtest.find_entries`, NO
`A_sweep_bos`)/Gestión V3-A ancla (`be`=1.0R/`activation`=2.0R/
`distance`=1.0R, NO V3-A+V3-B en paralelo)/`atr_mult`=1.5/`atr_period`=14/
`max_hold`=20/`risk`=0.005/sesión=`dcv1_activo_15h` única/BTCUSDT/ETHUSDT/
SOLUSDT/2022+2023 (2024 no ejecutado en esta fase).

Elección de Trigger/Entry/sesión, explícita y justificada (no elegida por
conveniencia, ver diseño formal): `T1_ema_cross`+`C_market_close` porque
`scripts/bias_campaign.py` es la ÚNICA infraestructura del repo cuyo
propósito arquitectónico es variar Bias (`CANDIDATES`/`apply_bias`), con
evidencia real ya publicada dos veces (`control_8h` y `dcv1_activo_15h`) —
a diferencia de la familia de scripts que usa `A_sweep_bos`
(`trigger_c_campaign.py`, `entry_campaign_sweep_bos.py`, etc.), que fija
`BIAS_CANDIDATE = "A"` hardcodeado por diseño, específicamente porque Bias
NO es su variable. Sesión `dcv1_activo_15h`: `control_8h` está ya
caracterizada en `FRAMEWORK.md` (H1/H2.1-H2.3/I1) como estructuralmente
incapaz de resolver el gate de frecuencia bajo cualquier Gestión probada —
hecho ya establecido sobre la variable sesión, no una predicción sobre B.
Gestión V3-A única: convención vigente en todo el programa desde el cierre
de Espacio 1.

Verificación de integridad (Fase A) — mismo diseño que Rama B/Trigger C,
porque la celda objetivo (Bias B) no tiene ningún antecedente histórico: se
verifica el pipeline COMPARTIDO (frame/sesión/Gestión/`find_entries`) vía la
celda auxiliar Bias A bajo este contrato exacto, contra la referencia YA
PUBLICADA (`gestion_campaign_session_results.csv`, `candidate=
"dcv1_activo_15h"`, `exit_config="V3-A (1R/2R/1R)"` — Bias=A/
Trigger=T1_ema_cross/Entry=C_market_close, generada por
`scripts/gestion_campaign_session.py`). 6 verificaciones totales (una por
activo/año). Si CUALQUIERA falla, `AssertionError` inmediato — la corrida
aborta antes de calcular una sola de las 6 filas candidatas de Bias B.

Reutilización de infraestructura (sin modificar `backtest.py`, sin tocar la
rama "A"/"A2" de `apply_bias`, sin tocar `bias_A_ema200_neutral`/
`bias_A2_ema200_neutral_1h_held`): de `scripts/bias_campaign.py` —
`resample_4h`, `apply_bias` (rama "B" nueva, agregada 2026-08-22),
`to_backtest_frame`, `gate_check`, `summarize_decision`. De `backtest.py` —
`find_entries` (Trigger=T1_ema_cross+Entry=C_market_close ya resueltos ahí,
el mismo camino que usa la campaña Bias A vs A2 original), `run_config`,
`metrics`, `EXIT_CONFIGS["V3-A (1R/2R/1R)"]`. De `research.BIAS_LAYERS` —
`B_ema50_ema200_cross` (nuevo, `research/layers.py`).

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, más una porción real
sobre `gestion_campaign_session_results.csv` (ya committeado, no requiere
data/raw/), ver research/tests/test_bias_b_campaign.py.

Uso (desde la raíz del repo, con data/raw/ poblado — NO ejecutado todavía,
requiere autorización explícita separada):
    python scripts/bias_b_campaign.py              # Fase 1+2 (incluye Fase A+B internas)
    python scripts/bias_b_campaign.py --blind        # Fase 3: 2024 ciego (requiere --candidate)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import research
import scripts.bias_campaign as bias_camp
import scripts.gestion_campaign_session as session_camp
from dc_v1 import build_dc_v1, validate_dc_v1
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path

# --------------------------------------------------------------------------- #
# Config de la campaña — contrato congelado 2026-08-22                       #
# --------------------------------------------------------------------------- #
BIAS_TARGET = "B"                     # research.BIAS_LAYERS["B_ema50_ema200_cross"], vía apply_bias
BIAS_COMPARATOR = "A"                 # auxiliar de Fase A únicamente, mismo contrato
SESSION_LABEL = "dcv1_activo_15h"     # ÚNICA sesión de esta campaña
SESSION_WINDOW = session_camp.SESSION_WINDOWS[SESSION_LABEL]

ATR_MULT_ANCHOR = 1.5     # ancla de H1, congelado
ATR_PERIOD_ANCHOR = 14    # fijo — excluido, ver Espacio 2
MAX_HOLD_ANCHOR = 20      # fijo — ya evaluado y falsificado en Espacio 2
EXIT_CFG = backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]  # {"be":1.0,"activation":2.0,"distance":1.0}

CANDIDATE_LABEL = "B_ema50_ema200_cross"  # valor de la columna "candidate" de las filas objetivo
CANDIDATES = (CANDIDATE_LABEL,)           # una sola celda de candidato — sin grid

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision

EXIT_CONFIG_LABEL = (
    "Bias B — EMA50+EMA200 4H, cruce (Trigger=T1_ema_cross/Entry=C_market_close/"
    "Gestión V3-A ancla/atr_mult=1.5/atr_period=14/max_hold=20/risk=0.005 fijos; "
    "sesión=dcv1_activo_15h única; comparador principal: Bias A bajo el mismo "
    "contrato, ver diseño formal de Bias B)"
)

# Referencia de Fase A — celda AUXILIAR (Bias A bajo este contrato exacto),
# NO la celda objetivo. Mismo patrón que Rama B/Trigger C: la celda objetivo
# (Bias B) no tiene ningún antecedente histórico, así que Fase A verifica el
# pipeline COMPARTIDO por ambas (frame/sesión/Gestión/find_entries).
_BIAS_A_SESSION_REF_PATH = "gestion_campaign_session_results.csv"
_BIAS_A_SESSION_REF_CANDIDATE = "dcv1_activo_15h"
_BIAS_A_SESSION_REF_EXIT_CONFIG = "V3-A (1R/2R/1R)"
_CHECK_FIELDS = ("pf", "wr", "exp_r", "max_dd", "freq")

# --------------------------------------------------------------------------- #
# Formato del CSV crudo — misma lógica que scripts/bias_campaign.py::         #
# _load_raw_csv (duplicada por convención propia del repo, ver su docstring; #
# bias_campaign.py::load_asset_year no calcula bias_B, así que no puede       #
# reutilizarse directamente acá).                                             #
# --------------------------------------------------------------------------- #
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
    """Carga (activo, año) desde data/raw/, corre build_dc_v1()+
    validate_dc_v1(), calcula bias_A Y bias_B sobre el frame COMPLETO
    (pre-slice, disciplina P-3) y recién entonces corta con
    periods.period_slice(). bias_A se calcula únicamente como auxiliar de
    Fase A — la celda objetivo de esta campaña es bias_B."""
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
    df_full["bias_A"] = bias_camp.apply_bias(df_full, df4h_full, BIAS_COMPARATOR)
    df_full["bias_B"] = bias_camp.apply_bias(df_full, df4h_full, BIAS_TARGET)

    return period_slice(df_full, year)


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _cfg() -> "backtest.Config":
    return backtest.Config(atr_mult=ATR_MULT_ANCHOR, atr_period=ATR_PERIOD_ANCHOR,
                            max_hold=MAX_HOLD_ANCHOR, sessions=SESSION_WINDOW)


def _run_combo(df_full: pd.DataFrame, bias_col_name: str, cfg: "backtest.Config"):
    """Trigger=T1_ema_cross/Entry=C_market_close vía backtest.find_entries —
    el mismo camino que usa scripts/bias_campaign.py::run_asset_year para
    Bias A vs A2, NO research.TRIGGER_LAYERS["A_sweep_bos"] (esa familia de
    scripts fija Bias=A por diseño, ajena a esta campaña)."""
    frame = bias_camp.to_backtest_frame(df_full, df_full[bias_col_name], cfg)
    entries = backtest.find_entries(frame, cfg)
    trades = backtest.run_config(frame, entries, EXIT_CFG, cfg)
    m = backtest.metrics(trades, cfg)
    return entries, trades, m


def _row(asset: str, year: int, entries: list[dict], trades: pd.DataFrame, m: dict | None) -> dict:
    return {
        "asset": asset, "year": year, "bias": BIAS_TARGET, "trigger": "T1_ema_cross",
        "entry": "C_market_close", "candidate": CANDIDATE_LABEL, "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m),
    }


# --------------------------------------------------------------------------- #
# Fase A — verificación de integridad del pipeline COMPARTIDO (6 checks)      #
# --------------------------------------------------------------------------- #
def _bias_a_session_reference(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_BIAS_A_SESSION_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)
               & (df["candidate"] == _BIAS_A_SESSION_REF_CANDIDATE)
               & (df["exit_config"] == _BIAS_A_SESSION_REF_EXIT_CONFIG)]
    if match.empty:
        raise AssertionError(
            f"No se encontró fila de referencia para celda=Bias A (verificación), "
            f"activo={asset}, año={year} en {_BIAS_A_SESSION_REF_PATH} — "
            f"no se puede verificar la Fase A."
        )
    return match.iloc[0]


def _values_match(actual, expected) -> bool:
    """Comparación NaN-consciente — mismo criterio ya usado en Rama B/Trigger C."""
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
            f"\nLa corrida aborta antes de calcular la celda objetivo de Bias B."
        )


def run_integrity_check(asset: str, year: int):
    """Fase A para un (activo, año) — 1 de las 6 verificaciones totales de
    la campaña. Verifica ÚNICAMENTE la celda auxiliar Bias A (NO la celda
    objetivo de Bias B, que carece de antecedente histórico). Devuelve
    df_full/cfg (compartidos con Fase B, ya con bias_A y bias_B calculadas)
    tras verificar. Revienta con AssertionError si la verificación falla."""
    cfg = _cfg()
    df_full = load_asset_year(asset, year)
    entries, trades, m = _run_combo(df_full, "bias_A", cfg)
    ref = _bias_a_session_reference(asset, year)
    _verify_against("Bias A (verificación de pipeline compartido)",
                     asset, year, _BIAS_A_SESSION_REF_PATH, len(entries), len(trades), m, ref)
    return df_full, cfg


# --------------------------------------------------------------------------- #
# Fase B — la celda objetivo (solo tras Fase A completa sin excepción)        #
# --------------------------------------------------------------------------- #
def run_asset_year_target(asset: str, year: int, df_full: pd.DataFrame, cfg: "backtest.Config") -> dict:
    entries, trades, m = _run_combo(df_full, "bias_B", cfg)
    return _row(asset, year, entries, trades, m)


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1(2022)+Fase 2(2023). Fase A completa para las 6 combinaciones
    (activo, año) ANTES de que arranque la Fase B — si run_integrity_check
    revienta en cualquier combinación, la excepción se propaga acá y la
    función nunca llega a calcular la celda objetivo. NO incluye 2024 — ver
    run_blind_test."""
    known: dict[tuple[str, int], tuple] = {}
    for year in years:
        for asset in assets:
            known[(asset, year)] = run_integrity_check(asset, year)  # Fase A

    rows: list[dict] = []
    for year in years:
        for asset in assets:
            df_full, cfg = known[(asset, year)]
            rows.append(run_asset_year_target(asset, year, df_full, cfg))  # Fase B
    return rows


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` ya congelado
    ("B_ema50_ema200_cross" — la única celda de esta campaña). No corre
    Fase A acá (exclusiva de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere el candidato ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    cfg = _cfg()
    results: list[dict] = []
    for asset in assets:
        df_full = load_asset_year(asset, BLIND_YEAR)
        entries, trades, m = _run_combo(df_full, "bias_B", cfg)
        results.append(_row(asset, BLIND_YEAR, entries, trades, m))
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
            "asset": r["asset"], "year": r["year"], "bias": r["bias"], "trigger": r["trigger"],
            "entry": r["entry"], "candidate": r["candidate"], "exit_config": r["exit_config"],
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
    print(f"\n{'='*100}\n  Bias B — EMA50+EMA200 4H + T1_ema_cross/C_market_close (comparador: Bias A)\n"
          f"  Gestión V3-A ancla/sesión=dcv1_activo_15h única fijos\n{'='*100}")
    cols = ["asset", "year", "bias", "trigger", "entry", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  DECISIÓN: sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: Bias B no demuestra evidencia suficiente para cumplir los 4 "
                  f"gates de FRAMEWORK.md en 2022+2023.")


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
        out_path = "bias_b_campaign_results.csv"
        df.to_csv(out_path, index=False)
        print(f"\nResultados exportados a {out_path} ({len(df)} filas)")
        return

    results = run_campaign()
    df = results_to_frame(results)
    print_report(df)
    out_path = "bias_b_campaign_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas — 1 combo x 3 activos x 2 "
          f"años = 6, todas genuinamente nuevas)")

    decision = summarize_decision(df)
    print_decision(decision)
    decision_path = "bias_b_campaign_decision.csv"
    decision.to_csv(decision_path, index=False)
    print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
