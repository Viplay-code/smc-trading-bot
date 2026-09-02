"""research/metrics.py — Núcleo numérico compartido de métricas (Fase C1,
TARGET_ARCHITECTURE.md §4.1, adelantada por la Iniciativa D del backlog
post-Fase-B).

Extrae el cálculo que `backtest.py::metrics` y `analisis_mfe_mae.py::metrics`
duplicaban de forma casi idéntica (verificado numéricamente igual sobre los
6 campos que ambos calculan: pf/wr/exp_r/total_r/max_dd/be). Cada consumidor
sigue con su propia interfaz — este módulo NO impone guard de muestra chica
ni agrega campos que un consumidor no tenía (`freq`/`reasons`/etc. de
`backtest.py` siguen siendo responsabilidad del wrapper que los necesita,
porque dependen de columnas — `entry_time`/`reason` — que no todos los
llamadores tienen).

Gate de aceptación (Fase 1 de la infraestructura de `research/runner.py`,
2026-09-02) — CONSOLIDADO ACÁ desde `scripts/bias_campaign.py::gate_check`,
donde vivía como la única definición real del programa (cada una de las
~25 campañas ya cerradas lo importaba por alias, `gate_check =
bias_camp.gate_check`, nunca lo reimplementó). Migración de UBICACIÓN
únicamente — ni los umbrales ni la semántica cambian ni un bit respecto de
la versión que vivía en `bias_campaign.py` (ver test de equivalencia en
`research/tests/test_metrics_gate_consolidation.py`). `scripts/
bias_campaign.py` re-exporta `gate_check`/`FREQ_MIN_PER_MONTH`/
`FREQ_MAX_PER_MONTH` desde acá (mismo objeto de función, no una copia) para
que las ~25 campañas legacy sigan funcionando sin ningún cambio de código
propio — ver el wrapper de compatibilidad documentado ahí.

`backtest.py::passes()` (freq>=4, sin techo de 12/mes) sigue existiendo,
sin cambios, como el gate que usa `bot.py` en vivo — es intencionalmente
DISTINTO de `gate_check` (el de investigación, con el techo de frecuencia
de `FRAMEWORK.md`) y esta consolidación no los unifica ni lo intenta.
"""
from __future__ import annotations

import pandas as pd

# --------------------------------------------------------------------------- #
# Gates de FRAMEWORK.md — únicos umbrales oficiales del programa de           #
# investigación. NO confundir con backtest.py::passes() (piso freq>=4, sin    #
# techo — el gate operativo de bot.py, deliberadamente distinto).             #
# --------------------------------------------------------------------------- #
PF_MIN = 1.50
MAX_DD_MIN = -10.0
EXP_R_MIN = 0.0
FREQ_MIN_PER_MONTH = 6
FREQ_MAX_PER_MONTH = 12


def compute_core_metrics(pnl: pd.Series, risk: float, initial_equity: float = 500.0) -> dict:
    """PF, WR, ExpR, TotalR, MaxDD y conteo de break-even a partir de una
    serie de PnL en R. Sin guard de tamaño de muestra ni manejo especial de
    entrada vacía — cada llamador decide eso antes de invocar (ver
    `backtest.py::metrics`, que sí guarda, vs. `analisis_mfe_mae.py::metrics`,
    que no)."""
    pnl = pd.Series(pnl)
    total = len(pnl)
    wins = (pnl > 0).sum()
    losses = (pnl < 0).sum()
    be = (pnl == 0).sum()
    wr = round(wins / total * 100, 1)
    gp = pnl[pnl > 0].sum()
    gl = pnl[pnl < 0].abs().sum()
    pf = round(gp / gl, 3) if gl > 0 else float("inf")
    exp_r = round(pnl.mean(), 3)
    total_r = round(pnl.sum(), 2)

    eq = [initial_equity]
    for r in pnl:
        eq.append(eq[-1] * (1 + risk * r))
    eq_s = pd.Series(eq)
    max_dd = round(((eq_s - eq_s.cummax()) / eq_s.cummax()).min() * 100, 2)

    return {"pf": pf, "exp_r": exp_r, "wr": wr, "total_r": total_r,
            "max_dd": max_dd, "be": be}


def gate_check(m: dict | None) -> bool:
    """Gates de FRAMEWORK.md, literales — NO backtest.py::passes() (su piso
    freq>=4 no aplica el techo de 12/mes que sí exige FRAMEWORK.md).

    Migrado desde `scripts/bias_campaign.py` (Fase 1 de la infraestructura
    de `research/runner.py`) SIN CAMBIAR ni el umbral ni la semántica — es
    literalmente la misma expresión booleana, solo movida de archivo. Sigue
    aceptando el mismo `dict` de métricas que produce `backtest.py::metrics`/
    `compute_core_metrics` (claves `pf`/`max_dd`/`exp_r`/`freq`), y sigue
    devolviendo `False` (no lanza) ante `m is None` — mismo contrato que
    antes, para no romper ningún llamador legacy que dependa de ese
    comportamiento con muestras insuficientes (`backtest.metrics()` devuelve
    `None` si `n_trades<5`)."""
    if m is None:
        return False
    return bool(
        m["pf"] >= PF_MIN
        and m["max_dd"] >= MAX_DD_MIN
        and m["exp_r"] > EXP_R_MIN
        and FREQ_MIN_PER_MONTH <= m["freq"] <= FREQ_MAX_PER_MONTH
    )
