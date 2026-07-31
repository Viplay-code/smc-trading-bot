#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_activation.py — Campaña de validación empírica
Gestión (H2.2): umbral de activación del trailing (`activation`, en R), bajo
Bias=A/Trigger=T1_ema_cross/Entry=C_market_close/atr_mult=1.5/be=1.0R/
distance=1.0R fijos, sobre la infraestructura de scripts/bias_campaign.py y
scripts/trigger_campaign.py.

Contexto: sigue a H2.1 (scripts/gestion_campaign_trailing_distance.py,
cerrada 2026-07-31, commit 9e05c96), que aisló `distance` como primera
variable de la familia H2 y no encontró ningún valor que supere los 4 gates
de FRAMEWORK.md — resultado esperado y contaminado por el gate de
frecuencia bajo `control_8h` (ver Limitaciones interpretativas), pero con un
patrón de PF real y consistente entre años para ETHUSDT/SOLUSDT (más
ajustado mejora PF) y mixto para BTCUSDT. Esta campaña aísla `activation`
como segunda variable de la familia H2 (diseño acordado 2026-07-31).

Objetivo — primario y secundario, distinguidos explícitamente (ajuste
2026-07-31):
  - PRIMARIO: caracterizar el efecto aislado de `activation` sobre PF,
    exp_r, avg_win/avg_loss y max_dd, manteniendo todo lo demás fijo — igual
    que H2.1 hizo para `distance`. Este objetivo se cumple sin importar si
    algún candidato llega a pasar los 4 gates.
  - SECUNDARIO: comprobar si, pese a la limitación conocida de frecuencia
    bajo `control_8h`, algún candidato de `activation` alcanza los 4 gates
    de FRAMEWORK.md en 2022 Y 2023 para algún activo. Dado que ningún otro
    parámetro de la familia H2 movió nunca el gate de frecuencia (`atr_mult`,
    `distance`), este objetivo tiene expectativa a priori baja de cumplirse
    — se mantiene igual porque falsificar formalmente la hipótesis exige
    barrer el rango candidato completo, no asumir el resultado de antemano.

Hipótesis (H2.2) a falsificar: existe un valor de `activation` distinto del
actual V3-A (2.0R) que, sin modificar ningún otro parámetro (`be`=1.0R y
`distance`=1.0R fijos en su valor de ancla V3-A — NO el valor de `distance`
que H2.1 encontró prometedor pero nunca confirmado por gates; adoptarlo acá
sería promover un candidato no validado, la misma regla de no-promoción ya
aplicada a `atr_mult` y a sesión), permite que al menos una combinación
(activo, activation) supere los 4 gates de FRAMEWORK.md en 2022 Y 2023 para
ese activo. Se considera falsificada si, barriendo el rango candidato
completo (incluidas extensiones por contingencia), ninguna combinación
sobrevive ambos años en ningún activo.

Por qué `activation` es la segunda variable de la familia H2 a aislar (orden
acordado 2026-07-31): una vez activo el trailing, `distance` (H2.1)
determina cuánto se devuelve del pico favorable — la palanca más directa
sobre la brecha que midió el diagnóstico MFE/MAE (avg_win realizado vs techo
de MFE, medido sobre trades GANADORES). `activation` determina CUÁNDO
empieza a operar ese mismo mecanismo — sigue actuando sobre la misma
población de trades (los que desarrollan un movimiento favorable grande) y
el mismo mecanismo (trailing), un paso más indirecto que `distance` pero
todavía dentro de la misma historia. `be` (H2.3) es cualitativamente
distinto: no toca la captura de pico en absoluto, solo reclasifica
operaciones marginales que nunca llegan a ser grandes ganadoras — una
población y una dimensión distintas, mecánicamente más lejos de la brecha
diagnosticada por MFE/MAE. Por eso `be` queda para después.

Rango candidato base: {1.5, 2.0 (ancla=V3-A/control), 2.5}. A diferencia de
`distance`, acá NO hay un argumento de monotonicidad demostrable que
justifique tratar un lado como un simple chequeo de confusión de un solo
punto: bajar `activation` adelanta cuándo el stop empieza a ratchetear hacia
arriba (más protección, más pronto), pero eso no garantiza un resultado de
PnL mejor — un stop que se activa antes también puede salir antes de una
continuación favorable, la misma tensión de dos efectos en competencia que
`distance` tiene por debajo de su ancla. Como esa tensión existe
potencialmente en AMBAS direcciones para `activation` (no en una sola), la
grilla base es simétrica con paso uniforme (0.5R), y las dos reglas de
contingencia (abajo) usan el MISMO criterio en ambos lados — a diferencia de
H2.1, donde el lado superior usaba un chequeo de confusión (justificado por
la monotonicidad probada de `distance`) y el inferior un chequeo de extremo
de rango. Límite inferior estructural: `activation` no debería bajar de
`be`=1.0R (el control fijo) sin invertir el orden conceptual
breakeven→trailing hacia un régimen distinto — el límite de una sola
extensión por regla (ver abajo) respeta ese piso sin necesitar una regla
aparte.

Reglas de contingencia PRE-ESPECIFICADAS (no exploratorias — se evalúan
automáticamente dentro de run_asset_year, por (activo, año), antes de cerrar
cualquier conclusión; disparan como máximo una vez por lado, sin cascada):
  1. Extensión hacia abajo: si activation=1.5 (extremo inferior de la grilla
     base) tiene el mejor-o-empatado PF entre los 3 puntos base para un
     (activo, año), dispara una corrida adicional en activation=1.25 para
     ESE (activo, año).
  2. Extensión hacia arriba: si activation=2.5 (extremo superior) tiene el
     mejor-o-empatado PF entre los 3 puntos base para un (activo, año),
     dispara una corrida adicional en activation=3.0 para ESE (activo, año).
  Ambas reglas usan el mismo criterio (ranking por PF en solitario, misma
  métrica de selección entre variantes que ya usa FRAMEWORK.md) por la razón
  de simetría explicada arriba — se implementan con una sola función
  parametrizada por el extremo a chequear, no dos funciones distintas como
  en H2.1.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no A_sweep_bos),
Entry=C_market_close, `atr_mult`=1.5 (ancla de H1, ya cerrada), `atr_period`
=14, `be`=1.0R (ancla V3-A — H2.3 todavía no corrió, no hay evidencia para
moverlo), `distance`=1.0R (ancla V3-A, NO el hallazgo de H2.1 — ver
Limitaciones interpretativas), `max_hold`=20, sesión Londres+NY (control_8h
— misma sesión que H2.1, preserva comparabilidad dentro de la familia H2;
NO se cambia a dcv1_activo_15h por la misma razón ya discutida y descartada
para H2.1: mezclar un cambio de sesión con un cambio de Gestión en la misma
corrida impediría atribuir cualquier mejora a una sola causa), `risk`=0.005,
una-posición-a-la-vez, datasets dc_v1 canónicos, disciplina P-3, modelo de
costos, gates literales de FRAMEWORK.md.

Nota de acoplamiento: igual que `distance`, `activation` solo se usa dentro
de `backtest.simulate_v3`, después de que `find_entries_for_trigger` ya
generó las entradas — invarianza estructural, no hay ninguna ruta de código
que las conecte. Las entradas se calculan UNA sola vez por (activo, año) y
se reutilizan para cada valor de `activation`.

Limitaciones interpretativas (ajuste 2026-07-31, sección nueva):
  - El gate de frecuencia bajo `control_8h` está perdido de antemano para
    TODAS las filas de esta campaña, por la misma razón que en H2.1 — las
    entradas son idénticas a las de H2.1 (mismo Bias/Trigger/Entry/sesión).
    `gate_pass=False` en todas las filas es esperado y NO es informativo
    sobre `activation` en sí; la lectura relevante es el patrón de PF/exp_r/
    avg_win/avg_loss a través de los valores de `activation` (objetivo
    primario), no el gate binario (objetivo secundario).
  - Los resultados de H2.2 NO autorizan la adopción de un nuevo valor de
    `activation` para el sistema integrado. Cualquier selección de
    candidatos entre los que esta campaña identifique como no dominados
    queda diferida a la futura Fase de Integración, bajo la regla de
    eliminación-no-promoción ya acordada (un candidato se descarta si está
    objetivamente dominado en las 4 métricas por otro; nunca se promueve un
    candidato a "control" o "ganador" sin haber pasado los 4 gates). Esta
    campaña, como H2.1, produce evidencia de entrada para esa regla — no
    una decisión final sobre `activation`.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
`summarize_decision` agrupa por (asset, candidate, exit_config) — acá
`exit_config` es una columna constante (`EXIT_CONFIG_LABEL`), igual que en
H2.1, para reutilizar esa función sin modificarla.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_gestion_campaign_activation.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_activation.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_activation.py --blind       # Fase 3: 2024 ciego (invocación separada, manual)
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import argparse

import pandas as pd

import backtest
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp
from market_data import ASSETS

# --------------------------------------------------------------------------- #
# Config de la campaña                                                        #
# --------------------------------------------------------------------------- #
BE_ANCHOR = 1.0          # V3-A, congelado — no es la variable bajo prueba
DISTANCE_ANCHOR = 1.0    # V3-A, congelado — NO el hallazgo de H2.1 (ver Limitaciones)
ATR_MULT_ANCHOR = 1.5    # ancla de H1 (ya cerrada), congelado

ACTIVATION_VALUES_BASE = (1.5, 2.0, 2.5)  # 2.0 = ancla V3-A, punto medio de la grilla base
ACTIVATION_EXT_LOWER = 1.25
ACTIVATION_EXT_UPPER = 3.0

CANDIDATES = tuple(
    str(v) for v in ACTIVATION_VALUES_BASE + (ACTIVATION_EXT_LOWER, ACTIVATION_EXT_UPPER)
)
EXIT_CONFIG_LABEL = "H2.2 anchor (be=1.0R/distance=1.0R, activation variable)"

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision


def _label(activation: float) -> str:
    return str(activation)


def _exit_cfg(activation: float) -> dict:
    return {"be": BE_ANCHOR, "activation": activation, "distance": DISTANCE_ANCHOR}


# --------------------------------------------------------------------------- #
# Regla de contingencia (pre-especificada 2026-07-31) — una sola función      #
# parametrizada por el extremo a chequear: a diferencia de H2.1, acá los dos  #
# lados usan el MISMO criterio (no hay argumento de monotonicidad que         #
# justifique tratar uno como chequeo de confusión), así que no hace falta     #
# duplicar la lógica en dos funciones distintas.                              #
# --------------------------------------------------------------------------- #
def _is_extreme_best(metrics_by_activation: dict[float, dict | None], extreme: float) -> bool:
    """True si `extreme` (uno de los dos extremos de la grilla base) tiene el
    mejor-o-empatado PF de todo el barrido base — ranking por PF en
    solitario, misma métrica de selección entre variantes que ya usa
    FRAMEWORK.md."""
    valid = {a: m for a, m in metrics_by_activation.items() if m is not None}
    if extreme not in valid or len(valid) < 2:
        return False
    pf_extreme = valid[extreme]["pf"]
    return all(pf_extreme >= m["pf"] for a, m in valid.items() if a != extreme)


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _run_activation(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
                     activation: float) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, _exit_cfg(activation), cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, activation: float, entries: list[dict],
          trades: pd.DataFrame, m: dict | None, triggered_by: str | None) -> dict:
    return {
        "asset": asset, "year": year, "candidate": _label(activation),
        "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "triggered_by": triggered_by,
    }


def run_asset_year(asset: str, year: int) -> list[dict]:
    """Corre el rango base de `activation` para un (activo, año), sobre el
    MISMO frame y las MISMAS entradas (invarianza estructural, ver docstring
    del módulo). Evalúa las dos reglas de contingencia sobre el resultado
    base y, si alguna dispara, corre el valor de extensión correspondiente
    para este mismo (activo, año)."""
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)

    rows = []
    metrics_by_activation: dict[float, dict | None] = {}
    for activation in ACTIVATION_VALUES_BASE:
        trades, m = _run_activation(frame, cfg, entries, activation)
        metrics_by_activation[activation] = m
        rows.append(_row(asset, year, activation, entries, trades, m, triggered_by=None))

    if _is_extreme_best(metrics_by_activation, ACTIVATION_VALUES_BASE[0]):
        trades, m = _run_activation(frame, cfg, entries, ACTIVATION_EXT_LOWER)
        rows.append(_row(asset, year, ACTIVATION_EXT_LOWER, entries, trades, m,
                          triggered_by="lower_contingency"))

    if _is_extreme_best(metrics_by_activation, ACTIVATION_VALUES_BASE[-1]):
        trades, m = _run_activation(frame, cfg, entries, ACTIVATION_EXT_UPPER)
        rows.append(_row(asset, year, ACTIVATION_EXT_UPPER, entries, trades, m,
                          triggered_by="upper_contingency"))

    return rows


def run_campaign(assets: tuple[str, ...] = ASSETS,
                  years: tuple[int, ...] = (IN_SAMPLE_YEAR, VALIDATION_YEAR)) -> list[dict]:
    """Fase 1 (2022) + Fase 2 (2023). NO incluye 2024 — ver run_blind_test."""
    results: list[dict] = []
    for year in years:
        for asset in assets:
            results.extend(run_asset_year(asset, year))
    return results


def run_blind_test(assets: tuple[str, ...] = ASSETS,
                    candidate: str | None = None) -> list[dict]:
    """Fase 3 (2024, ciego). Requiere `candidate` (un valor de activation,
    como string, ej. "1.5") ya congelado tras decidir con 2022+2023. No
    evalúa reglas de contingencia acá (exclusivas de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un activation ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    activation = float(candidate)
    results: list[dict] = []
    for asset in assets:
        df_full = trigger_camp.load_asset_year(asset, BLIND_YEAR)
        cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
        trades, m = _run_activation(frame, cfg, entries, activation)
        results.append(_row(asset, BLIND_YEAR, activation, entries, trades, m, triggered_by=None))
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
            "asset": r["asset"], "year": r["year"], "candidate": r["candidate"],
            "exit_config": r["exit_config"], "n_entries": n_entries,
            "n_trades": n_trades,
            "entries_per_month": round(entries_per_month, 2) if entries_per_month is not None else None,
            "fill_rate": round(fill_rate, 3) if fill_rate is not None else None,
            "gate_pass": r["gate_pass"], "triggered_by": r["triggered_by"],
            "pf": m.get("pf"), "wr": m.get("wr"), "exp_r": m.get("exp_r"),
            "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
            "total_r": m.get("total_r"), "max_dd": m.get("max_dd"), "freq": freq,
            "be": m.get("be"), "reason_stop": reasons.get("stop", 0),
            "reason_timeout": reasons.get("timeout", 0),
        })
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN H2.2 — activación del trailing bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/be=1.0R/distance=1.0R fijos\n{'='*100}")
    cols = ["asset", "year", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout",
            "gate_pass", "triggered_by"]
    print(df[cols].to_string(index=False))

    triggered = df[df["triggered_by"].notna()]
    print(f"\n{'-'*100}\n  Extensiones por regla de contingencia disparadas:\n{'-'*100}")
    if triggered.empty:
        print("  Ninguna — el rango base {1.5, 2.0, 2.5} no disparó ninguna de las "
              "dos reglas pre-especificadas en ningún (activo, año).")
    else:
        print(triggered[["asset", "year", "candidate", "triggered_by", "pf", "max_dd",
                          "exp_r", "freq"]].to_string(index=False))

    print(f"\n{'-'*100}\n  Combinaciones que pasan los 4 gates de FRAMEWORK.md (por año) "
          f"[objetivo secundario]:\n{'-'*100}")
    passing = df[df["gate_pass"]]
    if passing.empty:
        print("  Ninguna combinación pasa los 4 gates — esperado dado el gate de frecuencia "
              "perdido de antemano bajo control_8h (ver Limitaciones interpretativas). "
              "El objetivo primario (patrón de PF/exp_r/avg_win/avg_loss por activation) "
              "se lee en la tabla completa de arriba, no en esta sección.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Mismo formato que las campañas anteriores (reutiliza summarize_decision
    sin modificarlo). Recordatorio explícito: esta decisión NO autoriza
    adoptar un nuevo `activation` para el sistema integrado — eso queda
    diferido a la Fase de Integración bajo la regla de eliminación-no-
    promoción (ver Limitaciones interpretativas en el docstring del módulo)."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ningún activation en {CANDIDATES} demuestra evidencia suficiente "
                  f"para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo be={BE_ANCHOR}R/"
                  f"distance={DISTANCE_ANCHOR}R fijos — independientemente de cuál haya tenido "
                  f"mejor PF relativo. H2.2 queda sin evidencia suficiente para este activo con "
                  f"este rango. Esto NO autoriza adoptar ningún valor de activation para el "
                  f"sistema integrado — esa decisión queda diferida a la Fase de Integración.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="activation ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el activation ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_activation_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "gestion_campaign_activation_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
