#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_single_dataset.py — Inspección manual de UN dataset real bajo DC-v1.

Corre build_dc_v1() + validate_dc_v1() sobre un único dataset real
(BTCUSDT 1H, in-sample 2022 por defecto — editar la CONFIG de abajo para otro
caso) e imprime un reporte de consola detallado, para debug puntual de un
(activo, año) específico.

Relación con scripts/build_dc_v1_datasets.py (Fase B): ese script es el
gate-runner que automatiza esta misma verificación sobre los 9 (activo, año)
y decide el criterio de éxito de la Fase B. Este script NO fue reemplazado
por aquel — sigue siendo la herramienta para bajar a un solo caso e
inspeccionar contenido en detalle (gaps, distribución de htf_bias/sesiones)
cuando el gate-runner reporta un FAIL y hace falta ver el detalle a ojo.

Flujo (post-integración D-004 + I-1):
  cargar CSV crudo (data/raw, con buffer) -> build_dc_v1 (4 args) ->
  validate_dc_v1 (sobre la salida completa) -> period_slice al periodo ->
  secciones de inspección sobre el in-sample recortado.

NO automatiza, NO decide gate. Disciplina de blind set: examina CONTENIDO
(htf_bias, sesiones); si el índice recortado toca 2024, aborta esas secciones.
"""
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, ".")   # ejecutar desde la raíz del repo
from periods import period_slice
from versions import PIPELINE_VERSION, DATASET_VERSION

# ══════════════════════════════════════════════════════════════════
#  CONFIG — AJUSTAR AQUÍ
# ══════════════════════════════════════════════════════════════════
CSV_PATH        = "data/raw/BTCUSDT_1h_2022.csv"   # layout D-004 (data/raw/)
ASSET           = "BTCUSDT"
EXPECTED_PERIOD = 2022                              # in-sample

# ── PUNTO DE AJUSTE 1: formato del CSV crudo (producido por market_data) ──
CSV_HAS_HEADER  = True
TIME_COL        = "open_time"
OPEN_COL, HIGH_COL, LOW_COL, CLOSE_COL, VOLUME_COL = \
    "open", "high", "low", "close", "volume"
TIME_UNIT       = "ms"          # futuros USD-M 2022–2024: ms (confirmar en manifest)

# ── VERSIONES CANÓNICAS (D-1) ──────────────────────────────────────────
# PIPELINE_VERSION / DATASET_VERSION se importan de versions.py (fuente única
# compartida con gate-runner y EXP-07). No se definen aquí — evita divergencia.

MIN_ROWS_POST_SLICE = 6000
SESSION_COL_CANDIDATES = ["session", "sesion", "trading_session"]
# ══════════════════════════════════════════════════════════════════


try:
    from dc_v1 import build_dc_v1, validate_dc_v1
except ImportError:
    from dc_v1.pipeline import build_dc_v1     # type: ignore
    from dc_v1.validator import validate_dc_v1  # type: ignore


# ─────────────────────── helpers de reporte ───────────────────────
_findings = []

def hr(title):
    print("\n" + "═" * 68 + "\n  " + title + "\n" + "═" * 68)

def tag(level, msg):
    print(f"  [{level:<4}] {msg}")
    if level in ("WARN", "FAIL"):
        _findings.append((level, msg))

def abort(msg):
    tag("FAIL", msg)
    print_summary()
    sys.exit(1)


def load_raw_csv(path):
    """CSV crudo (12 col, market_data) -> DataFrame OHLCV con DatetimeIndex UTC.

    build_dc_v1 espera "OHLCV 1H con DatetimeIndex (open-time)"; entregamos eso.
    """
    df = pd.read_csv(path, header=0 if CSV_HAS_HEADER else None)
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


def run_validation(df):
    """Normaliza convenciones de retorno de validate_dc_v1 -> (ok, errs, interp)."""
    try:
        result = validate_dc_v1(df)
    except Exception as e:
        return False, [f"{type(e).__name__}: {e}"], True
    if result is None:
        return True, [], True
    if isinstance(result, bool):
        return result, ([] if result else ["validate_dc_v1 devolvió False"]), True
    if isinstance(result, (list, tuple)):
        return (len(result) == 0), list(result), True
    if isinstance(result, dict):
        errs = result.get("errors") or result.get("errores") or []
        return bool(result.get("ok", len(errs) == 0)), list(errs), True
    errs = getattr(result, "errors", None)
    if errs is not None:
        return (len(errs) == 0), list(errs), True
    ok_attr = getattr(result, "ok", None)
    if ok_attr is not None:
        return bool(ok_attr), [], True
    return True, [f"retorno no interpretable ({type(result).__name__})"], False


def print_summary():
    hr("RESUMEN")
    fails = [m for lvl, m in _findings if lvl == "FAIL"]
    warns = [m for lvl, m in _findings if lvl == "WARN"]
    if not fails and not warns:
        tag("OK", "Sin FAIL ni WARN. Dataset listo para inspección humana final.")
    else:
        for m in fails:
            print(f"  FAIL → {m}")
        for m in warns:
            print(f"  WARN → {m}")
    print(f"\n  Total: {len(fails)} FAIL, {len(warns)} WARN\n")


# ══════════════════════════════════════════════════════════════════
def main():
    hr(f"DC-v1 — Inspección de dataset único: {ASSET} 1H (periodo {EXPECTED_PERIOD})")

    print(f"  CSV: {CSV_PATH}")
    print(f"  pipeline_version={PIPELINE_VERSION!r}  dataset_version={DATASET_VERSION!r}")

    # ── 1. Carga cruda ──
    hr("1. Carga del CSV crudo")
    try:
        raw = load_raw_csv(CSV_PATH)
    except FileNotFoundError:
        abort(f"No se encontró el CSV en '{CSV_PATH}'. ¿Corriste el fetcher?")
    except Exception as e:
        abort(f"Fallo cargando el CSV: {type(e).__name__}: {e}")
    tag("OK", f"CSV cargado: {len(raw):,} barras crudas (buffer incluido)")
    tag("INFO", f"Rango crudo: {raw.index.min()} → {raw.index.max()}")

    # ── 2. build_dc_v1 (firma real de 4 argumentos) ──
    hr("2. build_dc_v1()")
    try:
        df_full = build_dc_v1(
            raw, asset=ASSET,
            dataset_version=DATASET_VERSION,
            pipeline_version=PIPELINE_VERSION,
        )
    except Exception as e:
        abort(f"build_dc_v1 lanzó: {type(e).__name__}: {e}")
    tag("OK", f"build_dc_v1 completó: {len(df_full):,} filas (post-warmup, con buffer)")
    tag("INFO", f"Rango post-build: {df_full.index.min()} → {df_full.index.max()}")
    tag("INFO", f"Columnas ({len(df_full.columns)}): {list(df_full.columns)}")

    # ── 3. validate_dc_v1 (sobre la salida COMPLETA — es el contrato) ──
    hr("3. validate_dc_v1()  [sobre salida de build, buffer incluido]")
    ok, errs, interpreted = run_validation(df_full)
    if not interpreted:
        tag("WARN", f"Retorno del validador no interpretable: {errs}")
    elif ok and not errs:
        tag("OK", "validate_dc_v1: cero errores")
    else:
        tag("FAIL", f"validate_dc_v1 reportó {len(errs)} error(es):")
        for e in errs:
            print(f"         - {e}")

    # ── 4. attrs / pipeline_version ──
    hr("4. df.attrs")
    if not df_full.attrs:
        tag("WARN", "df.attrs vacío. Se esperaba al menos pipeline_version.")
    else:
        pv = df_full.attrs.get("pipeline_version")
        if pv is None:
            tag("FAIL", "Falta 'pipeline_version' en df.attrs.")
        elif pv != PIPELINE_VERSION:
            tag("FAIL", f"pipeline_version en attrs ({pv!r}) ≠ el pasado "
                        f"({PIPELINE_VERSION!r}). Inconsistencia de sellado.")
        else:
            tag("OK", f"pipeline_version = {pv!r} (coincide con el pasado)")
        for k, v in df_full.attrs.items():
            if k == "pipeline_version":
                continue
            vs = repr(v)
            tag("INFO", f"attrs[{k!r}] = {vs[:200]}{'…' if len(vs) > 200 else ''}")

    # ── 5. Recorte al periodo (I-1: punto único de verdad) ──
    hr(f"5. period_slice → in-sample {EXPECTED_PERIOD}")
    try:
        df = period_slice(df_full, EXPECTED_PERIOD)
    except Exception as e:
        abort(f"period_slice lanzó: {type(e).__name__}: {e}")
    if len(df) == 0:
        abort(f"period_slice devolvió 0 filas para {EXPECTED_PERIOD}. "
              f"¿EXPECTED_PERIOD correcto? ¿open_time del CSV en unidad {TIME_UNIT}?")
    tag("OK", f"Recortado a {EXPECTED_PERIOD}: {len(df):,} filas")
    tag("INFO", f"Rango in-sample: {df.index.min()} → {df.index.max()}")
    if len(df) < MIN_ROWS_POST_SLICE:
        tag("WARN", f"Filas ({len(df):,}) < umbral ({MIN_ROWS_POST_SLICE:,}). "
                    f"¿Suficiente para 4–12 trades/mes?")
    else:
        tag("OK", f"Filas ≥ umbral ({MIN_ROWS_POST_SLICE:,})")

    # Warmup vs buffer: ¿el periodo arranca EXACTO en el 1-ene?
    first_expected = pd.Timestamp(f"{EXPECTED_PERIOD}-01-01", tz="UTC")
    if df.index.min() == first_expected:
        tag("OK", "El in-sample arranca exacto en 01-01 00:00 "
                  "(buffer absorbió el warmup).")
    elif df.index.min() > first_expected:
        lost = (df.index.min() - first_expected).total_seconds() / 86400
        tag("WARN", f"El in-sample arranca en {df.index.min()} "
                    f"(~{lost:.0f} días tarde): warmup > buffer. "
                    f"Sube BUFFER_MONTHS en market_data.config o revisa el trim.")

    # ── 6. Gaps (sobre el in-sample recortado) ──
    hr("6. Gaps en el in-sample")
    idx = df.index
    expected = pd.date_range(idx.min(), idx.max(), freq="1h")
    missing = expected.difference(idx)
    tag("INFO", f"Barras faltantes (detección independiente): {len(missing):,}")
    if len(missing) > 0:
        tag("INFO", f"Muestra: {[str(t) for t in missing[:5]]}")
    gap_keys = [k for k in df_full.attrs if "gap" in k.lower()]
    if gap_keys:
        for k in gap_keys:
            try:
                n = len(df_full.attrs[k])
            except TypeError:
                n = "?"
            tag("OK", f"attrs[{k!r}] documenta gaps (n={n}).")
    elif len(missing) > 0:
        tag("WARN", "Faltantes presentes pero attrs no documenta gaps.")

    # ── 7. htf_bias  [CONTENIDO — guard de blind set] ──
    hr("7. Distribución de htf_bias")
    years = sorted(set(idx.year.tolist()))
    if 2024 in years:
        tag("FAIL", "El índice contiene 2024 (BLIND SET). ABORTANDO contenido.")
    elif "htf_bias" not in df.columns:
        tag("WARN", "No existe columna 'htf_bias'.")
    else:
        b = df["htf_bias"]
        tag("INFO", f"dtype = {b.dtype}")
        if b.isna().any():
            tag("FAIL", f"htf_bias con {int(b.isna().sum())} NaN.")
        domain = set(pd.unique(b.dropna()))
        if not domain.issubset({-1, 0, 1}):
            tag("FAIL", f"Dominio fuera de {{-1,0,1}}: {domain}")
        else:
            tag("OK", f"Dominio ⊆ {{-1,0,1}} (observado: {sorted(domain)})")
        total = len(b)
        for val, cnt in b.value_counts(dropna=False).sort_index().items():
            tag("INFO", f"  bias={val:>2}: {cnt:>7,}  ({cnt/total:6.2%})")
        if (b == 0).mean() > 0.90:
            tag("WARN", f"htf_bias == 0 en {(b == 0).mean():.1%}. ¿Esperado?")

    # ── 8. Sesiones  [CONTENIDO — guard de blind set] ──
    hr("8. Sesiones")
    if 2024 in years:
        tag("FAIL", "Blind set 2024: sección de sesiones OMITIDA.")
    else:
        scol = next((c for c in SESSION_COL_CANDIDATES if c in df.columns), None)
        if scol is None:
            tag("WARN", f"Sin columna de sesión entre {SESSION_COL_CANDIDATES}. "
                        f"Columnas: {list(df.columns)}")
        else:
            s = df[scol]
            tag("OK", f"Columna de sesión: {scol!r} (dtype {s.dtype})")
            if s.isna().any():
                tag("WARN", f"{int(s.isna().sum())} barras sin sesión (NaN).")
            total = len(s)
            for cat, cnt in s.value_counts(dropna=False).items():
                tag("INFO", f"  {str(cat):<12}: {cnt:>7,}  ({cnt/total:6.2%})")
            tag("INFO", f"Categorías: {sorted(map(str, s.value_counts().index))}")

    # ── 9. Integridad estructural (in-sample) ──
    hr("9. Integridad estructural")
    tag("OK" if idx.is_monotonic_increasing else "FAIL",
        f"Índice monótono creciente: {idx.is_monotonic_increasing}")
    dups = int(idx.duplicated().sum())
    tag("OK" if dups == 0 else "FAIL", f"Timestamps duplicados: {dups}")
    tzinfo = getattr(idx, "tz", None)
    tag("OK" if str(tzinfo) == "UTC" else "WARN", f"tz del índice: {tzinfo}")
    nan_cols = df.columns[df.isna().any()].tolist()
    tag("WARN" if nan_cols else "OK",
        f"Columnas con NaN: {nan_cols}" if nan_cols else "Sin NaN post-recorte.")

    print_summary()


if __name__ == "__main__":
    main()