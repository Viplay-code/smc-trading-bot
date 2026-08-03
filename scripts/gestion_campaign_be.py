#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gestion_campaign_be.py — Campaña de validación empírica Gestión
(H2.3): nivel de breakeven (`be`, en R), bajo Bias=A/Trigger=T1_ema_cross/
Entry=C_market_close/atr_mult=1.5/activation=2.0R/distance=1.0R fijos, sobre
la infraestructura de scripts/bias_campaign.py y scripts/trigger_campaign.py.

Contexto: cierra la familia H2 (BE/trailing desacoplados) tras H2.1
(`distance`, cerrada 2026-07-31, commit 9e05c96) y H2.2 (`activation`,
cerrada 2026-08-03, commit c0add0a) — ninguna de las dos encontró una
combinación que supere los 4 gates de FRAMEWORK.md, ambas bajo el mismo
gate de frecuencia perdido de antemano en `control_8h`. H2.1 encontró una
asociación de PF real (más consistente en ETHUSDT/SOLUSDT, mixta en
BTCUSDT) al ajustar `distance`; H2.2 encontró una asociación monótona y
consistente entre `activation` más alto y WR más bajo/avg_win más alto,
sin dirección de PF estable entre años. Esta campaña aísla `be` como
tercera y última variable de la familia (diseño acordado 2026-08-03).

Objetivo — primario y secundario, mismo split que H2.2:
  - PRIMARIO: caracterizar el efecto aislado de `be` sobre WR/avg_loss/
    avg_win/PF, manteniendo todo lo demás fijo. A diferencia de `distance`
    (captura de picos grandes) y `activation` (cuándo empieza esa
    captura), `be` actúa sobre una población y un mecanismo distintos:
    solo mueve el stop a `entry` cuando el avance favorable alcanza
    `be_lvl` (`backtest.py:192-198`) y NUNCA cierra la operación — afecta
    específicamente a operaciones que alcanzan algo de avance y luego
    retroceden hasta la entrada antes de continuar o revertir, no al
    tamaño de los grandes ganadores. Se cumple sin importar si algún
    candidato llega a pasar los 4 gates.
  - SECUNDARIO: comprobar si, pese a la limitación conocida de frecuencia
    bajo `control_8h`, algún candidato de `be` alcanza los 4 gates de
    FRAMEWORK.md en 2022 Y 2023 para algún activo. Expectativa a priori
    baja por el mismo argumento estructural que en H2.1/H2.2 (`be`
    tampoco afecta las entradas, ver Nota de acoplamiento).

Hipótesis (H2.3) a falsificar: existe un valor de `be` distinto del actual
V3-A (1.0R) que, sin modificar ningún otro parámetro (`activation`=2.0R y
`distance`=1.0R fijos en su ancla V3-A — NO los hallazgos de H2.1/H2.2,
misma regla de no-promoción ya aplicada de H2.1 a H2.2), permite que al
menos una combinación (activo, be) supere los 4 gates de FRAMEWORK.md en
2022 Y 2023 para ese activo. Se considera falsificada si, barriendo el
rango candidato completo (incluidas extensiones por contingencia), ninguna
combinación sobrevive ambos años en ningún activo.

Rango candidato base: {0.5, 1.0 (ancla=V3-A/control), 1.5}. Igual que
`activation` (H2.2) y a diferencia de `distance` (H2.1): `be` tiene la
misma tensión de dos efectos en competencia en AMBOS lados, no una
predicción monótona de un solo lado. Bajar `be` protege antes contra
reversión (mejora `avg_loss`/WR de perdedoras) pero también arriesga sacar
por breakeven operaciones que iban a continuar a favor (empeora `avg_win`
de lo que hubiera sido ganador); subir `be` es la tensión inversa. Grilla
simétrica, paso uniforme de 0.5R, mismo criterio de contingencia en ambos
lados (ranking por PF en solitario, no un chequeo de confusión de 4
métricas — esa distinción es propia del lado monótono de `distance` en
H2.1, no aplica acá).

Piso de la extensión inferior (0.25) — justificado explícitamente
2026-08-03, no reutilizado por inercia: `risk_pts >= atr_mult·ATR14`
siempre, por construcción de `min()/max()` en el sizing del SL
(`trigger_campaign.py:186-189`, idéntico en `backtest.py:131-134`) — así
que `be`=0.25R ya exige >= 0.375×ATR14 de avance favorable, bien por
debajo de un ATR(14) típico pero no una fracción ínfima de ruido de una
sola vela. Bajar más convertiría la pregunta de "cuánta confirmación
exigir" en "proteger casi de inmediato sin importar la confirmación" — una
pregunta distinta a la variable `be`. Mismo piso ya validado con datos
reales en H2.1 para `distance` sin señal de colapso degenerado (`n_trades`
idéntico al resto de la grilla en 5/6 combos donde se disparó esa
extensión, ver `gestion_campaign_trailing_distance_results.csv`).

Tope duro de la extensión superior (2.0) — límite ESTRUCTURAL, no de
resolución: `be` no debe superar el ancla de `activation` (2.0R) sin
invertir el orden conceptual breakeven→trailing. Verificado con evidencia
de código 2026-08-03 (no solo razonamiento) que `be`==`activation`==2.0R
NO genera ninguna ambigüedad: `max_fav_pts` es monótona no decreciente
(`backtest.py:187-188`), así que ambos umbrales, si son iguales, se cruzan
siempre en la MISMA barra; dentro de esa barra el orden de ejecución es
secuencial y fijo (BE en el paso 3, activación en el paso 4, ratchet de
trailing en el paso 5, `backtest.py:192-211`) y el trailing SIEMPRE
sobreescribe el stop de BE en la misma barra — confirmado ejecutando
`simulate_v3` real sobre una trayectoria construida para discriminarlo
(salida en la barra de pullback a precio exacto del nivel de trailing,
110.0, no del nivel de BE, 100). Por eso la extensión superior puede
llegar hasta 2.0 sin ambigüedad, pero NO más allá — si 2.0 también
resultara extremo-mejor, eso NO dispara una extensión adicional (violaría
el límite conceptual); se reporta como hallazgo de borde, no se persigue.

Reglas de contingencia PRE-ESPECIFICADAS (mismo patrón que H2.2 — una sola
función parametrizada por el extremo a chequear, mismo criterio en ambos
lados, disparan como máximo una vez por lado, sin cascada):
  1. Extensión hacia abajo: si be=0.5 (extremo inferior de la grilla base)
     tiene el mejor-o-empatado PF entre los 3 puntos base para un
     (activo, año), dispara una corrida adicional en be=0.25 para ESE
     (activo, año).
  2. Extensión hacia arriba: si be=1.5 (extremo superior) tiene el
     mejor-o-empatado PF entre los 3 puntos base para un (activo, año),
     dispara una corrida adicional en be=2.0 para ESE (activo, año) — tope
     duro, ver arriba.

Fijo durante toda la campaña: Bias=A, Trigger=T1_ema_cross (no
A_sweep_bos), Entry=C_market_close, `atr_mult`=1.5 (ancla de H1, ya
cerrada), `atr_period`=14, `activation`=2.0R (ancla V3-A — NO el hallazgo
de H2.2), `distance`=1.0R (ancla V3-A — NO el hallazgo de H2.1),
`max_hold`=20, sesión Londres+NY (control_8h — misma sesión que H2.1/H2.2,
preserva comparabilidad dentro de la familia H2), `risk`=0.005, una
posición a la vez, datasets dc_v1 canónicos, disciplina P-3, modelo de
costos, gates literales de FRAMEWORK.md.

Nota de acoplamiento: igual que `distance`/`activation`, `be` solo se usa
dentro de `backtest.simulate_v3`, después de que `find_entries_for_trigger`
ya generó las entradas — invarianza estructural, no hay ninguna ruta de
código que las conecte. Las entradas se calculan UNA sola vez por
(activo, año) y se reutilizan para cada valor de `be`.

Limitaciones interpretativas (mismas que H2.2, aplicadas a `be`):
  - El gate de frecuencia bajo `control_8h` está perdido de antemano para
    TODAS las filas de esta campaña — las entradas son idénticas a las de
    H2.1/H2.2. `gate_pass=False` en todas las filas es esperado y NO es
    informativo sobre `be` en sí; la lectura relevante es el patrón de
    WR/avg_loss/avg_win/PF a través de los valores de `be` (objetivo
    primario), no el gate binario (objetivo secundario).
  - Los resultados de H2.3 NO autorizan la adopción de un nuevo valor de
    `be` para el sistema integrado. Cualquier selección entre candidatos
    no dominados queda diferida a la futura Fase de Integración, bajo la
    regla de eliminación-no-promoción ya acordada (un candidato se
    descarta si está objetivamente dominado en las 4 métricas por otro;
    nunca se promueve un candidato a "control"/"ganador" sin haber pasado
    los 4 gates). Con el cierre de H2.3 se completa la caracterización
    individual de los tres parámetros de la familia H2 — la posible
    interacción conjunta entre `be`/`activation`/`distance` (cada campaña
    varió uno congelando los otros dos en su ancla ORIGINAL, no en los
    hallazgos de las campañas previas) queda fuera de alcance de las tres
    campañas individuales, explícita para la Fase de Integración.

Reutilización de infraestructura (sin modificar ninguno de los archivos
reutilizados, ni `backtest.py`): de scripts/bias_campaign.py —
`to_backtest_frame`, `gate_check`, `summarize_decision`. De
scripts/trigger_campaign.py — `load_asset_year`, `find_entries_for_trigger`.
`summarize_decision` agrupa por (asset, candidate, exit_config) — acá
`exit_config` es una columna constante (`EXIT_CONFIG_LABEL`), igual que en
H2.1/H2.2.

Requiere `data/raw/` poblado. BLOQUEADO en este sandbox (HTTP 451,
data/raw/ vacío) — validado acá solo estructuralmente, ver
research/tests/test_gestion_campaign_be.py.

Uso (desde la raíz del repo, con data/raw/ poblado):
    python scripts/gestion_campaign_be.py              # Fase 1+2: 2022 in-sample, 2023 validación
    python scripts/gestion_campaign_be.py --blind        # Fase 3: 2024 ciego (invocación separada, manual)
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
ACTIVATION_ANCHOR = 2.0  # V3-A, congelado — NO el hallazgo de H2.2
DISTANCE_ANCHOR = 1.0    # V3-A, congelado — NO el hallazgo de H2.1
ATR_MULT_ANCHOR = 1.5    # ancla de H1 (ya cerrada), congelado

BE_VALUES_BASE = (0.5, 1.0, 1.5)  # 1.0 = ancla V3-A, punto medio de la grilla base
BE_EXT_LOWER = 0.25
BE_EXT_UPPER = 2.0  # tope duro == ACTIVATION_ANCHOR, ver docstring del módulo

CANDIDATES = tuple(
    str(v) for v in BE_VALUES_BASE + (BE_EXT_LOWER, BE_EXT_UPPER)
)
EXIT_CONFIG_LABEL = "H2.3 anchor (activation=2.0R/distance=1.0R, be variable)"

BIAS_CANDIDATE = "A"
TRIGGER_CANDIDATE = "T1_ema_cross"

IN_SAMPLE_YEAR = bias_camp.IN_SAMPLE_YEAR
VALIDATION_YEAR = bias_camp.VALIDATION_YEAR
BLIND_YEAR = bias_camp.BLIND_YEAR
gate_check = bias_camp.gate_check
summarize_decision = bias_camp.summarize_decision


def _label(be: float) -> str:
    return str(be)


def _exit_cfg(be: float) -> dict:
    return {"be": be, "activation": ACTIVATION_ANCHOR, "distance": DISTANCE_ANCHOR}


# --------------------------------------------------------------------------- #
# Regla de contingencia (pre-especificada 2026-08-03) — una sola función      #
# parametrizada por el extremo a chequear, mismo criterio en ambos lados      #
# (mismo patrón que H2.2, `be` tiene la misma tensión de dos efectos en       #
# competencia en ambas direcciones, a diferencia del lado monótono de         #
# `distance` en H2.1).                                                        #
# --------------------------------------------------------------------------- #
def _is_extreme_best(metrics_by_be: dict[float, dict | None], extreme: float) -> bool:
    """True si `extreme` (uno de los dos extremos de la grilla base) tiene el
    mejor-o-empatado PF de todo el barrido base — ranking por PF en
    solitario, misma métrica de selección entre variantes que ya usa
    FRAMEWORK.md."""
    valid = {b: m for b, m in metrics_by_be.items() if m is not None}
    if extreme not in valid or len(valid) < 2:
        return False
    pf_extreme = valid[extreme]["pf"]
    return all(pf_extreme >= m["pf"] for b, m in valid.items() if b != extreme)


# --------------------------------------------------------------------------- #
# Orquestación                                                                #
# --------------------------------------------------------------------------- #
def _run_be(frame: pd.DataFrame, cfg: "backtest.Config", entries: list[dict],
            be: float) -> tuple[pd.DataFrame, dict | None]:
    trades = backtest.run_config(frame, entries, _exit_cfg(be), cfg)
    m = backtest.metrics(trades, cfg)
    return trades, m


def _row(asset: str, year: int, be: float, entries: list[dict],
          trades: pd.DataFrame, m: dict | None, triggered_by: str | None) -> dict:
    return {
        "asset": asset, "year": year, "candidate": _label(be),
        "exit_config": EXIT_CONFIG_LABEL,
        "n_entries": len(entries), "n_trades": len(trades),
        "metrics": m, "gate_pass": gate_check(m), "triggered_by": triggered_by,
    }


def run_asset_year(asset: str, year: int) -> list[dict]:
    """Corre el rango base de `be` para un (activo, año), sobre el MISMO
    frame y las MISMAS entradas (invarianza estructural, ver docstring del
    módulo). Evalúa las dos reglas de contingencia sobre el resultado base
    y, si alguna dispara, corre el valor de extensión correspondiente para
    este mismo (activo, año)."""
    df_full = trigger_camp.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
    frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)

    rows = []
    metrics_by_be: dict[float, dict | None] = {}
    for be in BE_VALUES_BASE:
        trades, m = _run_be(frame, cfg, entries, be)
        metrics_by_be[be] = m
        rows.append(_row(asset, year, be, entries, trades, m, triggered_by=None))

    if _is_extreme_best(metrics_by_be, BE_VALUES_BASE[0]):
        trades, m = _run_be(frame, cfg, entries, BE_EXT_LOWER)
        rows.append(_row(asset, year, BE_EXT_LOWER, entries, trades, m,
                          triggered_by="lower_contingency"))

    if _is_extreme_best(metrics_by_be, BE_VALUES_BASE[-1]):
        trades, m = _run_be(frame, cfg, entries, BE_EXT_UPPER)
        rows.append(_row(asset, year, BE_EXT_UPPER, entries, trades, m,
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
    """Fase 3 (2024, ciego). Requiere `candidate` (un valor de be, como
    string, ej. "0.5") ya congelado tras decidir con 2022+2023. No evalúa
    reglas de contingencia acá (exclusivas de la fase 2022+2023)."""
    if candidate not in CANDIDATES:
        raise ValueError(
            f"run_blind_test requiere un be ya congelado {CANDIDATES} "
            "tras decidir con 2022+2023 — no se corre 2024 a ciegas de una "
            "decisión previa."
        )
    be = float(candidate)
    results: list[dict] = []
    for asset in assets:
        df_full = trigger_camp.load_asset_year(asset, BLIND_YEAR)
        cfg = backtest.Config(atr_mult=ATR_MULT_ANCHOR)
        frame = bias_camp.to_backtest_frame(df_full, df_full["bias_A"], cfg)
        entries = trigger_camp.find_entries_for_trigger(frame, cfg, TRIGGER_CANDIDATE)
        trades, m = _run_be(frame, cfg, entries, be)
        results.append(_row(asset, BLIND_YEAR, be, entries, trades, m, triggered_by=None))
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
    print(f"\n{'='*100}\n  CAMPAÑA GESTIÓN H2.3 — nivel de breakeven bajo Bias=A/Trigger=T1_ema_cross/"
          f"Entry=C_market_close/atr_mult=1.5/activation=2.0R/distance=1.0R fijos\n{'='*100}")
    cols = ["asset", "year", "candidate", "n_entries", "n_trades",
            "entries_per_month", "fill_rate", "pf", "wr", "exp_r", "avg_win", "avg_loss",
            "total_r", "max_dd", "freq", "be", "reason_stop", "reason_timeout",
            "gate_pass", "triggered_by"]
    print(df[cols].to_string(index=False))

    triggered = df[df["triggered_by"].notna()]
    print(f"\n{'-'*100}\n  Extensiones por regla de contingencia disparadas:\n{'-'*100}")
    if triggered.empty:
        print("  Ninguna — el rango base {0.5, 1.0, 1.5} no disparó ninguna de las "
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
              "El objetivo primario (patrón de WR/avg_loss/avg_win/PF por be) se lee en "
              "la tabla completa de arriba, no en esta sección.")
    else:
        print(passing[cols].to_string(index=False))


def print_decision(decision: pd.DataFrame) -> None:
    """Mismo formato que las campañas anteriores (reutiliza summarize_decision
    sin modificarlo). Recordatorio explícito: esta decisión NO autoriza
    adoptar un nuevo `be` para el sistema integrado — eso queda diferido a
    la Fase de Integración bajo la regla de eliminación-no-promoción (ver
    Limitaciones interpretativas en el docstring del módulo)."""
    print(f"\n{'='*100}\n  DECISIÓN — sobrevivientes (ambos años, por activo) y ranking por PF 2023\n{'='*100}")
    if decision.empty:
        print("  Sin combinaciones para evaluar.")
        return
    print(decision.to_string(index=False))

    for asset, g in decision.groupby("asset"):
        survivors = g[g["survives_both_years"]]
        if survivors.empty:
            print(f"\n  {asset}: ningún be en {CANDIDATES} demuestra evidencia suficiente "
                  f"para cumplir los gates de FRAMEWORK.md en 2022+2023 bajo "
                  f"activation={ACTIVATION_ANCHOR}R/distance={DISTANCE_ANCHOR}R fijos — "
                  f"independientemente de cuál haya tenido mejor PF relativo. H2.3 queda "
                  f"sin evidencia suficiente para este activo con este rango. Esto NO "
                  f"autoriza adoptar ningún valor de be para el sistema integrado — esa "
                  f"decisión queda diferida a la Fase de Integración.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", action="store_true",
                         help="Corre la Fase 3 (2024, ciego) — requiere --candidate")
    parser.add_argument("--candidate", choices=CANDIDATES, default=None,
                         help="be ya congelado para --blind")
    args = parser.parse_args()

    if args.blind:
        if args.candidate is None:
            parser.error("--blind requiere --candidate (el be ya congelado)")
        results = run_blind_test(candidate=args.candidate)
    else:
        results = run_campaign()

    df = results_to_frame(results)
    print_report(df)
    out_path = "gestion_campaign_be_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nResultados exportados a {out_path} ({len(df)} filas)")

    if not args.blind:
        decision = summarize_decision(df)
        print_decision(decision)
        decision_path = "gestion_campaign_be_decision.csv"
        decision.to_csv(decision_path, index=False)
        print(f"Decisión exportada a {decision_path} ({len(decision)} filas)")


if __name__ == "__main__":
    main()
