#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dc_v1_datasets.py — Gate-runner de los 9 datasets reales DC-v1.

Generaliza a los 9 (activo, año) lo que scripts/inspect_single_dataset.py hace
a mano para un solo caso: carga el CSV crudo de market_data, corre
build_dc_v1() + validate_dc_v1(), recorta al período con periods.period_slice(),
y al final confirma que los 9 comparten pipeline_version/dataset_version.

Materializa el criterio de éxito de la Fase B
(docs/architecture/TARGET_ARCHITECTURE.md §6.1):
  1. Los 9 datasets se generan automáticamente desde data/raw/ (market_data).
  2. Los 9 pasan validate_dc_v1() sin errores.
  3. Los 9 comparten el mismo pipeline_version/dataset_version.

Requiere data/raw/ poblado por scripts/download_market_data.py. Nunca lanza a
mitad de camino: cada (activo, año) se intenta de forma independiente y se
reporta OK/FAIL, para que un dataset roto no oculte el resultado de los otros 8.

Uso (desde la raíz del repo):  python scripts/build_dc_v1_datasets.py
"""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")   # ejecutar desde la raíz del repo
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION
from market_data import ASSETS, INTERVAL_1H, RAW_DIR, raw_path, years_in_range

from dc_v1 import build_dc_v1, validate_dc_v1

# Formato del CSV crudo (12 columnas nativas de una kline de Binance,
# ver market_data.config.KLINE_COLUMNS / storage.write_raw_csv).
TIME_COL = "open_time"
OPEN_COL, HIGH_COL, LOW_COL, CLOSE_COL, VOLUME_COL = "open", "high", "low", "close", "volume"
TIME_UNIT = "ms"


def hr(title: str) -> None:
    print("\n" + "═" * 68 + "\n  " + title + "\n" + "═" * 68)


def load_raw_csv(path) -> pd.DataFrame:
    """CSV crudo (market_data) -> DataFrame OHLCV con DatetimeIndex UTC.

    Misma lógica que scripts/inspect_single_dataset.py::load_raw_csv,
    generalizada a un `path` arbitrario en vez de una constante.
    """
    df = pd.read_csv(path, header=0)
    ts = pd.to_datetime(df[TIME_COL], unit=TIME_UNIT, utc=True)
    # .to_numpy() -> asignación POSICIONAL. Sin esto, las Series (RangeIndex) se
    # alinean por etiqueta contra el DatetimeIndex y todo queda NaN.
    raw = pd.DataFrame(
        {
            "open":   pd.to_numeric(df[OPEN_COL],   errors="coerce").to_numpy(),
            "high":   pd.to_numeric(df[HIGH_COL],   errors="coerce").to_numpy(),
            "low":    pd.to_numeric(df[LOW_COL],    errors="coerce").to_numpy(),
            "close":  pd.to_numeric(df[CLOSE_COL],  errors="coerce").to_numpy(),
            "volume": pd.to_numeric(df[VOLUME_COL], errors="coerce").to_numpy(),
        },
        index=pd.DatetimeIndex(ts, name="open_time"),
    )
    return raw


def build_one(asset: str, year: int) -> dict:
    """Corre el pipeline completo para un (asset, year). Nunca lanza: captura
    y reporta los errores en el dict de resultado."""
    path = raw_path(asset, INTERVAL_1H, year, RAW_DIR)
    result = {
        "asset": asset, "year": year, "path": str(path), "ok": False,
        "errors": [], "pipeline_version": None, "dataset_version": None,
    }

    if not path.exists():
        result["errors"].append(
            f"CSV no encontrado: {path} (¿corriste scripts/download_market_data.py?)"
        )
        return result

    try:
        raw = load_raw_csv(path)
    except Exception as e:
        result["errors"].append(f"Fallo cargando CSV: {type(e).__name__}: {e}")
        return result

    try:
        df_full = build_dc_v1(
            raw, asset=asset,
            dataset_version=DATASET_VERSION,
            pipeline_version=PIPELINE_VERSION,
        )
    except Exception as e:
        result["errors"].append(f"build_dc_v1 lanzó: {type(e).__name__}: {e}")
        return result

    errs = validate_dc_v1(df_full, strict=False)
    if errs:
        result["errors"].extend(f"validate_dc_v1: {e}" for e in errs)

    try:
        sliced = period_slice(df_full, year)
    except Exception as e:
        result["errors"].append(f"period_slice lanzó: {type(e).__name__}: {e}")
        return result

    if len(sliced) == 0:
        result["errors"].append(f"period_slice devolvió 0 filas para {year}")

    result["pipeline_version"] = df_full.attrs.get("pipeline_version")
    result["dataset_version"] = df_full.attrs.get("dataset_version")
    result["rows_full"] = len(df_full)
    result["rows_sliced"] = len(sliced)
    result["ok"] = not result["errors"]
    return result


def main() -> None:
    hr(f"DC-v1 — gate-runner de los 9 datasets reales "
       f"(pipeline_version={PIPELINE_VERSION!r}, dataset_version={DATASET_VERSION!r})")

    years = years_in_range()
    combos = [(asset, year) for year in years for asset in ASSETS]
    print(f"  Activos: {', '.join(ASSETS)}  |  Años: {years}  |  Combos: {len(combos)}")

    results = [build_one(asset, year) for asset, year in combos]

    hr("Resultado por dataset")
    for r in results:
        status = "OK  " if r["ok"] else "FAIL"
        extra = f"  ({r['rows_sliced']:,} filas in-period)" if r["ok"] else ""
        print(f"  [{status}] {r['asset']} {r['year']}{extra}")
        for e in r["errors"]:
            print(f"           - {e}")

    hr("Consistencia de versiones (pipeline_version / dataset_version)")
    pvs = {r["pipeline_version"] for r in results if r["pipeline_version"] is not None}
    dvs = {r["dataset_version"] for r in results if r["dataset_version"] is not None}
    version_ok = len(pvs) <= 1 and len(dvs) <= 1
    print(f"  pipeline_version observados: {pvs or '-'}")
    print(f"  dataset_version observados:  {dvs or '-'}")
    print(f"  {'OK' if version_ok else 'FAIL'} — "
         f"{'consistentes' if version_ok else 'DIVERGEN entre datasets'}")

    hr("Resumen — criterio de éxito Fase B")
    n_ok = sum(r["ok"] for r in results)
    all_ok = n_ok == len(results) and version_ok
    print(f"  Datasets OK: {n_ok}/{len(results)}")
    print(f"  Versiones consistentes: {version_ok}")
    print(f"  {'PASS' if all_ok else 'FAIL'} — "
         f"Fase B {'cumple' if all_ok else 'NO cumple (todavía)'} su criterio de éxito")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
