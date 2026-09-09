#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_session.py — Campaña de validación empírica
Gestión: ventana de sesión (`SESSION_WINDOWS`), bajo Trigger=T1_ema_cross
fijo. MIGRADO a la infraestructura canónica C1-C8 (2026-09-09), tras
demostrar equivalencia exacta 36/36 (ver auditoría de migración) contra la
versión legacy (que corría sobre `scripts/bias_campaign.py`/
`scripts/trigger_campaign.py` + `backtest.run_config`/`backtest.metrics`
directamente).

Hipótesis (H1) a falsificar: existe una ventana de sesión más amplia que la
actual (07-11+13-17, 8h) que, sin modificar ningún otro parámetro, permite
que al menos una combinación (activo, ventana, exit_config) supere los 4
gates de FRAMEWORK.md en 2022 Y 2023 para ese activo — cerrando la brecha de
frecuencia que la campaña de `atr_mult` (2026-07-28) confirmó con datos
reales: 0/48 filas con freq≥6, y prácticamente invariante entre valores de
atr_mult (medias 4.92-5.03) — evidencia de que Gestión (lo que ocurre
DESPUÉS de abrir un trade) no puede mover ese gate por construcción.

Candidatos (acordados 2026-07-29, ninguno inventado):
  - control_8h: [(7,11),(13,17)] — la ventana de producción actual, ancla
    obligatoria de comparación.
  - dcv1_activo_15h: [(7,22)] — unión de las 3 categorías "de mercado
    activo" que `dc_v1.pipeline::_classify_session` ya calcula y valida
    (`london` 07-13, `overlap` 13-16, `ny` 16-22; excluye solo `off`).
  - sin_filtro_24h: [(0,24)] — techo matemático del espacio de parámetros;
    no existe una ventana más ancha, así que si acá tampoco se alcanza
    freq≥6 la hipótesis de sesión queda falsificada por completo, no por
    falta de rango.
Las 3 ventanas están anidadas por construcción: control_8h ⊂
dcv1_activo_15h ⊂ sin_filtro_24h.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no
A_sweep_bos), Entry=C_market_close, `atr_mult`=1.5 (el valor de
especificación original — la campaña de Gestión/atr_mult no produjo un
ganador que congelar, así que se revierte al valor de referencia en vez de
elegir uno arbitrariamente entre los 4 probados), `atr_period`=14,
`be`/`activation`/`distance` (V3-A y V3-B en paralelo, no es la variable
bajo prueba), `max_hold`=20, `risk`=0.005, una-posición-a-la-vez, datasets
dc_v1 canónicos, disciplina P-3, modelo de costos, gates literales.

ALCANCE EXPERIMENTAL — Raw EXCLUIDO deliberadamente (auditoría de alcance,
2026-09-09): `research.EXIT_CONFIGS`/`research.runner.MANAGEMENT_LAYERS`
contienen una tercera entrada, `"Raw"`, desde Fase 5 (commit `e1f2367`,
2026-09-03) — agregada MÁS DE UN MES DESPUÉS de que esta campaña (2026-07-29)
fuera diseñada y su artifact histórico (36 filas) publicado, para una
investigación completamente distinta (Espacio 6, aislar el componente TP
mediante `scripts/gestion_espacio6_raw_campaign.py`). El propio commit que
introdujo Raw documenta explícitamente: "no cambia ningún valor ya
publicado" — reconociendo el artifact histórico de 36 filas como referencia
intacta, no como algo a extender. Por eso `MANAGEMENTS` abajo es una tupla
EXPLÍCITA (`"V3-A"`, `"V3-B"`), nunca `research.runner.MANAGEMENT_LAYERS.
keys()`/`research.EXIT_CONFIGS.keys()` — recorrer el registro genéricamente
introduciría a Raw sin autorización y cambiaría el universo de 36 a 54
celdas silenciosamente. Ver `test_raw_explicitamente_excluido_del_universo`
en `research/tests/test_gestion_campaign_session.py` (guardia de regresión).

Verificación de acoplamiento (2026-07-29) — MÁS FUERTE que la de
`atr_mult`, porque acá se pudo probar por dos vías independientes. Ambas
corren desde `_build_windows_and_verify`, punto único de verificación
compartido por `run_campaign`/`run_blind_test` (vía `run_sanity_checks`) —
una violación en CUALQUIERA de las dos rutas de ejecución real lanza
`AssertionError` sin capturar, antes de calcular ninguna métrica, y termina
la corrida. PRESERVADO SIN CAMBIOS DE SIGNIFICADO por la migración (sección
7 de la migración) — sigue corriendo sobre las mismas primitivas legacy
(`scripts.trigger_campaign`/`scripts.bias_campaign`) porque son lógica
específica de ESTA investigación (acoplamiento sessions<->Trigger), ajena a
lo que C1-C8 expone (`ExperimentResult` no captura conteos de eventos
crudos ni conteos de entradas pre-filtro):

1. `sessions` no está en la firma de `trigger_T1_ema_cross` en ningún
   punto — la detección del cruce corre sobre la serie completa, ajena a
   sesión. El conteo de eventos CRUDOS debe ser IDÉNTICO (no solo
   monótono) entre las 3 ventanas — `assert_raw_events_session_invariant`
   lo verifica en cada corrida real.
2. `n_entries` (post filtro de bias/sesión, calculado por
   `find_entries_for_trigger`) SÍ depende de `in_session`, pero es
   monótono no decreciente por una razón demostrable: como las 3 ventanas
   están anidadas, todo evento que pasa el filtro con la ventana angosta
   también pasa con las más anchas (el chequeo de bias/dirección es
   idéntico en las 3, ajeno a `sessions`) — el conjunto de eventos
   aceptados de la ventana angosta es subconjunto exacto del de la
   ventana ancha. `assert_n_entries_monotonic` lo verifica en cada corrida
   real.

IMPORTANTE — lo que NO se afirma: `n_trades` (post "una posición a la
vez", calculado por `backtest.run_config` dentro de `research.runner.run`)
NO hereda esa garantía. La regla de concurrencia es un proceso "greedy
causal" sobre entradas cuya duración de operación es variable y depende de
los datos (`simulate_v3` sale cuando el precio toca el stop, no en un punto
fijo) — una entrada nueva, habilitada solo por ampliar la ventana, puede
tener una duración larga que bloquee DOS O MÁS entradas que antes se
ejecutaban por separado, y `n_trades` puede bajar aunque `n_entries` suba
(contraejemplo numérico verificado 2026-07-29, ver conversación de diseño).
Por eso `note_concurrency_effects` reporta, como información y no como
error, cualquier (activo, año, management) donde `n_trades` no acompañe el
crecimiento garantizado de `n_entries` — es evidencia real sobre cuándo la
concurrencia se vuelve una restricción activa, no un bug. PRESERVADA, ahora
operando sobre el DataFrame derivado de `ExperimentResult` en vez del dict
legacy.

Mapping legacy -> canónico (migración 2026-09-09):
    asset        -> asset
    year         -> period
    candidate    -> session
    exit_config  -> management
    n_entries    -> n_entries
    n_trades     -> n_trades
    pf/wr/exp_r/total_r/max_dd/freq/gate_pass -> ídem (ExperimentResult)
Columnas diagnósticas legacy SIN equivalente canónico (`entries_per_month`,
`fill_rate`, `avg_win`, `avg_loss`, `be`, `reason_stop`, `reason_timeout`) —
NO migradas: ya clasificadas como puramente diagnósticas, ajenas a
métricas/gates/decisión (auditoría comparativa legacy vs C1-C8, 2026-09-08).

Reutilización de infraestructura: `research.expand_universe` (C4),
`research.runner.run_many` (C3), `research.summarize_decision` (C5),
`research.write_experiment_results_csv`/`write_decision_csv` (C6). Los
sanity-checks científicos siguen reutilizando `scripts.bias_campaign`/
`scripts.trigger_campaign` (sin modificarlos) porque calculan una
propiedad (invarianza/monotonicidad de eventos crudos pre-filtro) que
`ExperimentResult` no expone y que es exclusiva de esta investigación.

Artifacts: la ejecución normal de este script (`main()`) escribe a
`gestion_campaign_session_canonical_results.csv`/
`gestion_campaign_session_canonical_decision.csv` — artifacts SEPARADOS del
baseline histórico (`gestion_campaign_session_results.csv`/`_decision.csv`),
que nunca se sobrescriben por este script.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_gestion_campaign_session.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_session.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_session.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import research
from research import runner
from research.expand import expand_universe
from research.decision import summarize_decision as canonical_summarize_decision
from research.persistence import (
    write_experiment_results_csv, write_decision_csv, to_experiment_rows,
)
import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Alcance experimental de esta campaña (ver docstring del módulo)            #
# --------------------------------------------------------------------------- #
NESTED_ORDER = ("control_8h", "dcv1_activo_15h", "sin_filtro_24h")
SESSION_WINDOWS = {
    "control_8h": [(7, 11), (13, 17)],
    "dcv1_activo_15h": [(7, 22)],
    "sin_filtro_24h": [(0, 24)],
}
CANDIDATES = NESTED_ORDER

MANAGEMENTS = ("V3-A", "V3-B")
"""Tupla EXPLÍCITA, NUNCA `research.runner.MANAGEMENT_LAYERS.keys()` ni
`research.EXIT_CONFIGS.keys()` — ver docstring del módulo (Raw excluido
deliberadamente del alcance de ESTA campaña)."""

BIAS_CANDIDATE_LEGACY = "A"
"""Etiqueta legacy usada por `scripts.bias_campaign`/`scripts.trigger_campaign`
(hardcodeada dentro de esas funciones, ver `trigger_camp.load_asset_year`) —
DISTINTA del nombre de registro canónico `BIAS_CANDIDATE` usado en el
contrato C2 (`research.BIAS_LAYERS`); ambas se refieren al mismo candidato
Bias."""
BIAS_CANDIDATE = "A_ema200_neutral"
TRIGGER_CANDIDATE = "T1_ema_cross"
ENTRY_CANDIDATE = "C_market_close"
ATR_MULT_FIXED = 1.5  # valor de especificación original, sin ganador que congelar tras atr_mult
ATR_PERIOD = 14
RISK = 0.005
COST_PER_TRADE = 0.0009
MAX_HOLD = 20

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}


def _cfg_for(label: str) -> "backtest.Config":
    """Config legacy usada EXCLUSIVAMENTE por los sanity-checks de
    acoplamiento sessions<->Trigger (sección 7 de la migración) — la
    ejecución real de resultados ya NO pasa por `backtest.Config`
    directamente, ver `build_universe`/`research.runner.run_many`."""
    return backtest.Config(atr_mult=ATR_MULT_FIXED, sessions=SESSION_WINDOWS[label])


# --------------------------------------------------------------------------- #
# Verificación de acoplamiento sessions <-> Trigger (sanity-checks           #
# empíricos) — SIN CAMBIOS DE SIGNIFICADO respecto de la versión legacy,     #
# ver docstring del módulo.                                                  #
# --------------------------------------------------------------------------- #
def assert_raw_events_session_invariant(raw_counts: dict[str, int], asset: str, year: int) -> None:
    """`sessions` no está en la firma de trigger_T1_ema_cross — los eventos
    crudos deben ser IDÉNTICOS entre las 3 ventanas, no solo monótonos."""
    distinct = set(raw_counts.values())
    if len(distinct) != 1:
        raise AssertionError(
            f"`sessions` afectó el conteo de eventos crudos de {TRIGGER_CANDIDATE} para "
            f"{asset}/{year} ({raw_counts}) — contradice que `sessions` no forma parte de "
            f"la firma de trigger_T1_ema_cross. Investigar antes de tratar esta campaña "
            f"como un experimento puro de ventana horaria."
        )


def assert_n_entries_monotonic(n_entries_by_window: dict[str, int], asset: str, year: int) -> None:
    """control_8h ⊆ dcv1_activo_15h ⊆ sin_filtro_24h como conjuntos de horas
    habilitadas -> n_entries debe ser monótonamente no decreciente en ese
    orden (demostración formal: ver docstring del módulo). NO se afirma lo
    mismo de n_trades (ver docstring) — esa garantía se rompe por diseño
    con la regla de una-posición-a-la-vez + duración de operación variable,
    y por eso no se verifica acá."""
    counts = [n_entries_by_window[label] for label in NESTED_ORDER]
    if not (counts[0] <= counts[1] <= counts[2]):
        raise AssertionError(
            f"n_entries no es monótono para {asset}/{year} entre ventanas anidadas "
            f"{NESTED_ORDER}: {dict(zip(NESTED_ORDER, counts))} — contradice la "
            f"demostración formal de que in_session es una máscara monótona sobre "
            f"eventos ya detectados. Investigar antes de continuar."
        )


def _build_windows_and_verify(df_full: pd.DataFrame, asset: str, year: int) -> None:
    """Corre AMBOS sanity-checks para un (activo, año) dado — punto único de
    verificación reutilizado por `run_sanity_checks`, para
    `run_campaign`/`run_blind_test` (2022/2023/2024). PRESERVADA sin
    cambios de significado; ya no devuelve frames/entries (la ejecución
    real de resultados ahora pasa por `research.runner.run_many`, no por
    estas primitivas), solo ejecuta la verificación y lanza
    `AssertionError` sin capturar si algo falla."""
    raw_counts: dict[str, int] = {}
    entries_by_window: dict[str, int] = {}
    for label in NESTED_ORDER:
        cfg = _cfg_for(label)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        raw_counts[label] = len(trigger_camp._raw_events(frame, TRIGGER_CANDIDATE, cfg))
        entries_by_window[label] = len(trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE))

    assert_raw_events_session_invariant(raw_counts, asset, year)
    assert_n_entries_monotonic(entries_by_window, asset, year)


def run_sanity_checks(assets: tuple[str, ...], years: tuple[int, ...]) -> None:
    """Corre los 2 sanity-checks científicos para cada (asset, year) de la
    campaña, ANTES de construir cualquier contrato canónico — mismo punto
    único de verificación que la versión legacy, reutilizado sin cambios de
    significado. Las 3 ventanas se verifican siempre, incluso en --blind
    donde luego solo se ejecuta una (la congelada), porque los
    sanity-checks son comparativos (necesitan las 3 para verificar
    invarianza/monotonicidad) y cada año es un dataset real distinto — vale
    la pena re-verificar la propiedad ahí también (mismo razonamiento que
    la versión legacy)."""
    for year in years:
        for asset in assets:
            df_full = trigger_camp.load_asset_year(asset, year)
            _build_windows_and_verify(df_full, asset, year)


# --------------------------------------------------------------------------- #
# Universo canónico (C4) + ejecución canónica (C3)                          #
# --------------------------------------------------------------------------- #
def build_universe(
    assets: tuple[str, ...], years: dict[str, int],
    sessions: tuple[str, ...] = NESTED_ORDER, managements: tuple[str, ...] = MANAGEMENTS,
) -> list[dict]:
    """Universo canónico: un template por (session, management), expandido
    vía `research.expand_universe` (C4, assets x years) — `expand_universe`
    no expande `session`/`management`, así que esas 2 dimensiones se
    recorren acá explícitamente, con listas EXPLÍCITAS (`sessions`,
    `managements`), nunca leyendo un registro genérico (ver docstring del
    módulo, alcance experimental)."""
    contracts: list[dict] = []
    for session in sessions:
        for mgmt in managements:
            template = {
                "name": "gestion_campaign_session",
                "contract_version": "1",
                "assets": list(assets),
                "years": dict(years),
                "bias": {"name": BIAS_CANDIDATE, "params": {}},
                "trigger": {"name": TRIGGER_CANDIDATE, "params": {}},
                "entry": {"name": ENTRY_CANDIDATE, "params": {}},
                "session": session,
                "management": {"name": mgmt, "params": {}},
                "risk": RISK,
                "cost_per_trade": COST_PER_TRADE,
                "max_hold": MAX_HOLD,
                "atr_mult": ATR_MULT_FIXED,
                "gates": dict(_CANONICAL_GATES),
                "independent_variable": "session",
                "blind_authorized": "blind" in years,
            }
            contracts.extend(expand_universe(template))
    return contracts


def run_campaign(assets: tuple[str, ...] = ASSETS) -> tuple[list[dict], list]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test.
    Universo completo: 3 sessions x 2 managements x 3 assets x 2 years =
    36 contratos/resultados."""
    run_sanity_checks(assets, (IN_SAMPLE_YEAR, VALIDATION_YEAR))
    contracts = build_universe(assets, {"train": IN_SAMPLE_YEAR, "validate": VALIDATION_YEAR})
    for c in contracts:
        runner.validate_contract(c)  # ContractError se propagaría sin capturar
    results = runner.run_many(contracts)
    return contracts, results


def run_blind_test(assets: tuple[str, ...] = ASSETS, candidate: str | None = None) -> tuple[list[dict], list]:
    """Fase 3 (2024, ciego). Requiere `candidate` (una ventana de sesión, ej.
    "dcv1_activo_15h") ya congelada tras decidir con 2022+2023. Corre los
    sanity-checks sobre las 3 ventanas igual que run_campaign (mismo
    razonamiento: 2024 es un dataset real distinto, vale re-verificar ahí
    también), pero el universo ejecutado se restringe a la única ventana
    congelada (ambos managements, todos los activos)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere una ventana ya congelada {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    run_sanity_checks(assets, (BLIND_YEAR,))
    contracts = build_universe(assets, {"blind": BLIND_YEAR}, sessions=(candidate,))
    for c in contracts:
        runner.validate_contract(c)
    results = runner.run_many(contracts)
    return contracts, results


# --------------------------------------------------------------------------- #
# Reporte — derivado DIRECTAMENTE de ExperimentResult (C3), ninguna métrica #
# se recalcula acá (ver mapping legacy->canónico en el docstring)           #
# --------------------------------------------------------------------------- #
def results_to_frame(results: list) -> pd.DataFrame:
    """`list[ExperimentResult]` -> DataFrame de reporte, vía
    `research.to_experiment_rows` (C6, transformación pura ya existente) —
    ninguna columna se fabrica ni se recalcula acá."""
    return pd.DataFrame(to_experiment_rows(results))


def note_concurrency_effects(df: pd.DataFrame) -> None:
    """Informativo, NO un error: reporta cuándo n_trades no acompaña el
    crecimiento (garantizado) de n_entries entre ventanas anidadas — efecto
    esperado de una-posición-a-la-vez + duración de operación variable (ver
    docstring del módulo), no un bug de la campaña. PRESERVADA, operando
    sobre las columnas canónicas (`session`/`management`/`period` en vez de
    `candidate`/`exit_config`/`year`)."""
    flagged = []
    for (asset, period, management), g in df.groupby(["asset", "period", "management"]):
        g = g.set_index("session").reindex(NESTED_ORDER)
        trades = g["n_trades"]
        if trades.isna().any():
            continue
        if not (trades.iloc[0] <= trades.iloc[1] <= trades.iloc[2]):
            flagged.append((asset, period, management, dict(zip(NESTED_ORDER, trades.tolist()))))

    if flagged:
        print(f"\n{'-'*100}\n  Nota (no es un error): n_trades no acompañó el crecimiento garantizado de "
              f"n_entries en estos casos — consistente con una-posición-a-la-vez + duración de "
              f"operación variable, no con un fallo de la campaña:\n{'-'*100}")
        for asset, period, management, trades in flagged:
            print(f"  {asset} {period} {management}: {trades}")


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN — ventana de sesión bajo Trigger=T1_ema_cross, "
          f"Bias=A, Entry=C_market_close y atr_mult=1.5 fijos (canónico C1-C8)\n{'='*100}")
    cols = ["asset", "period", "period_role", "session", "management", "n_entries", "n_trades",
            "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass"]
    print(df[cols].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año):\n{'-'*100}")
    passing = df[df["gate_pass"] == True]  # noqa: E712 (gate_pass puede ser None)
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — ninguna ventana de sesión probada "
              "demuestra evidencia suficiente todavía.")
    else:
        print(passing[cols].to_string(index=False))

    note_concurrency_effects(df)


def print_decision(decisions: list) -> None:
    print(f"\n{'='*100}\n  DECISIÓN — C5 summarize_decision(candidate_fields=('session','management'), "
          f"required_roles=('train','validate'), rank_by_role='validate')\n{'='*100}")
    if not decisions:
        print("  Sin combinaciones para evaluar.")
        return
    rows = [{"asset": d.asset, "session": d.candidate[0], "management": d.candidate[1],
              "survives_required_roles": d.survives_required_roles, "rank_within_asset": d.rank_within_asset}
             for d in decisions]
    print(pd.DataFrame(rows).to_string(index=False))

    by_asset: dict[str, list] = {}
    for d in decisions:
        by_asset.setdefault(d.asset, []).append(d)
    for asset, ds in by_asset.items():
        survivors = [d for d in ds if d.survives_required_roles]
        if not survivors:
            print(f"\n  {asset}: ninguna ventana de sesión en {CANDIDATES} demuestra evidencia "
                  f"suficiente para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo Trigger="
                  f"{TRIGGER_CANDIDATE} — dado que sin_filtro_24h es el techo matemático del "
                  f"espacio de parámetros, esto descarta la ventana horaria como explicación "
                  f"completa en este activo (no por falta de rango). Si dcv1_activo_15h o "
                  f"sin_filtro_24h superaron el techo de 12 mientras control_8h seguía bajo el "
                  f"piso de 6, la rama ya declarada es descomponer en london/overlap/ny "
                  f"individuales para buscar la sub-ventana mínima suficiente, no ampliar el "
                  f"rango de nuevo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="Ventana de sesión ya congelada para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (la ventana ya congelada)")
        contracts, results = run_blind_test(candidate=args.candidate)
    else:
        contracts, results = run_campaign()

    df = results_to_frame(results)
    print_report(df)

    out_results_path = "gestion_campaign_session_canonical_results.csv"
    write_experiment_results_csv(out_results_path, results)
    print(f"\nResultados canónicos exportados a {out_results_path} ({len(results)} filas) "
          f"-- artifact SEPARADO del histórico gestion_campaign_session_results.csv (NO sobrescrito).")

    if not args.blind:
        decisions = canonical_summarize_decision(
            results, candidate_fields=("session", "management"),
            required_roles=("train", "validate"), rank_by_role="validate",
        )
        print_decision(decisions)
        out_decision_path = "gestion_campaign_session_canonical_decision.csv"
        write_decision_csv(out_decision_path, decisions, candidate_fields=("session", "management"))
        print(f"Decisión canónica exportada a {out_decision_path} ({len(decisions)} filas) "
              f"-- artifact SEPARADO del histórico gestion_campaign_session_decision.csv (NO sobrescrito).")


if __name__ == "__main__":
    main()
