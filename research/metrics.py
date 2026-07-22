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
"""
from __future__ import annotations

import pandas as pd


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
