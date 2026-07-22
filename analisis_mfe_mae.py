"""
Optimizacion de la distancia de trailing — basada en datos MFE/MAE
Barre distintas distancias de trailing y activaciones para justificar
objetivamente el parametro, en vez de fijarlo por intuicion.

Limitacion: el CSV tiene MFE final, no la trayectoria. La aproximacion
(trailing cierra en MFE - distancia) se aplica IGUAL a todas las variantes,
por lo que la comparacion RELATIVA entre distancias es valida.
"""

import pandas as pd
import numpy as np
from itertools import product

import research

CSV_PATH = "t1_trades_multiasset.csv"


def simulate_trailing(row, be_trigger, trail_activation, trail_distance):
    """
    Simula una salida con:
      - Break-even cuando MFE >= be_trigger (SL pasa a 0R)
      - Trailing activado cuando MFE >= trail_activation
      - Trailing cierra en MFE - trail_distance
    
    Devuelve el pnl_r resultante.
    """
    mfe = row["mfe_r"]
    outcome = row["outcome"]

    # Nunca alcanza break-even
    if mfe < be_trigger:
        return row["pnl_r"]  # resultado original (-1R o segun caso)

    # Alcanza BE pero no activa trailing
    if mfe < trail_activation:
        if outcome == "tp":
            return 2.5
        else:
            return 0.0  # break-even

    # Trailing activado (mfe >= trail_activation)
    trailing_exit = mfe - trail_distance

    if outcome == "tp":
        # Si MFE <= 2.5, el TP fijo (2.5R) se habria activado primero
        if mfe <= 2.5:
            return 2.5
        else:
            # MFE supero 2.5R: el trailing pudo capturar mas
            return max(trailing_exit, 2.5)
    else:
        # Termino en SL pero habia alcanzado trail_activation
        # El trailing lo habria cerrado en MFE - distancia
        return max(trailing_exit, 0.0)


def metrics(pnl_series, risk=0.005, initial=500.0):
    # Núcleo compartido con backtest.py (Iniciativa D) — mismo cálculo, sin
    # guard de muestra chica ni manejo especial de entrada vacía, igual que
    # antes de esta consolidación.
    return research.compute_core_metrics(pnl_series, risk, initial)


if __name__ == "__main__":
    df = pd.read_csv(CSV_PATH)
    print(f"Trades: {len(df)}\n")

    # ── PARTE 1: Barrido de distancia de trailing ────────────────────────
    # BE fijo en 1R, trailing activado en 2R, variamos SOLO la distancia
    print("="*80)
    print("  PARTE 1 — BARRIDO DE DISTANCIA DE TRAILING")
    print("  (BE fijo=1R, activacion fija=2R, variando distancia)")
    print("="*80)
    print(f"  {'Distancia':>10} {'PF':>7} {'ExpR':>7} {'WR%':>6} {'TotalR':>8} {'MaxDD':>7}")
    print("  " + "-"*55)

    distances = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    dist_results = []
    for dist in distances:
        pnl = df.apply(lambda r: simulate_trailing(r, 1.0, 2.0, dist), axis=1)
        m = metrics(pnl)
        dist_results.append((dist, m))
        print(f"  {dist:>9}R {m['pf']:>7} {m['exp_r']:>7} {m['wr']:>6} "
              f"{m['total_r']:>8} {m['max_dd']:>7}")

    best_dist = max(dist_results, key=lambda x: x[1]["pf"])
    print(f"\n  Mejor distancia por PF: {best_dist[0]}R (PF={best_dist[1]['pf']})")

    # ── PARTE 2: Barrido de punto de activacion del trailing ─────────────
    print("\n" + "="*80)
    print("  PARTE 2 — BARRIDO DEL PUNTO DE ACTIVACION")
    print(f"  (BE fijo=1R, distancia fija={best_dist[0]}R, variando activacion)")
    print("="*80)
    print(f"  {'Activacion':>11} {'PF':>7} {'ExpR':>7} {'WR%':>6} {'TotalR':>8} {'MaxDD':>7}")
    print("  " + "-"*56)

    activations = [1.5, 2.0, 2.5, 3.0]
    act_results = []
    for act in activations:
        pnl = df.apply(lambda r: simulate_trailing(r, 1.0, act, best_dist[0]), axis=1)
        m = metrics(pnl)
        act_results.append((act, m))
        print(f"  {act:>10}R {m['pf']:>7} {m['exp_r']:>7} {m['wr']:>6} "
              f"{m['total_r']:>8} {m['max_dd']:>7}")

    best_act = max(act_results, key=lambda x: x[1]["pf"])
    print(f"\n  Mejor activacion por PF: {best_act[0]}R (PF={best_act[1]['pf']})")

    # ── PARTE 3: Barrido del trigger de break-even ───────────────────────
    print("\n" + "="*80)
    print("  PARTE 3 — BARRIDO DEL TRIGGER DE BREAK-EVEN")
    print(f"  (activacion fija={best_act[0]}R, distancia fija={best_dist[0]}R, variando BE)")
    print("="*80)
    print(f"  {'BE trigger':>11} {'PF':>7} {'ExpR':>7} {'WR%':>6} {'TotalR':>8} {'MaxDD':>7}")
    print("  " + "-"*56)

    be_triggers = [0.5, 0.75, 1.0, 1.25, 1.5]
    be_results = []
    for be in be_triggers:
        pnl = df.apply(lambda r: simulate_trailing(r, be, best_act[0], best_dist[0]), axis=1)
        m = metrics(pnl)
        be_results.append((be, m))
        print(f"  {be:>10}R {m['pf']:>7} {m['exp_r']:>7} {m['wr']:>6} "
              f"{m['total_r']:>8} {m['max_dd']:>7}")

    best_be = max(be_results, key=lambda x: x[1]["pf"])
    print(f"\n  Mejor BE trigger por PF: {best_be[0]}R (PF={best_be[1]['pf']})")

    # ── PARTE 4: Configuracion optima combinada ──────────────────────────
    print("\n" + "="*80)
    print("  PARTE 4 — CONFIGURACION OPTIMA (busqueda conjunta)")
    print("="*80)

    best_combo = None
    best_pf = 0
    all_combos = []

    for be, act, dist in product([0.75, 1.0, 1.25],
                                  [1.5, 2.0, 2.5],
                                  [0.75, 1.0, 1.25, 1.5]):
        if act <= be:  # activacion debe ser > break-even
            continue
        pnl = df.apply(lambda r: simulate_trailing(r, be, act, dist), axis=1)
        m = metrics(pnl)
        all_combos.append((be, act, dist, m))
        if m["pf"] > best_pf and m["max_dd"] >= -10:
            best_pf = m["pf"]
            best_combo = (be, act, dist, m)

    # Top 10 combinaciones
    all_combos.sort(key=lambda x: x[3]["pf"], reverse=True)
    print(f"  {'BE':>5} {'Activ':>6} {'Dist':>5} {'PF':>7} {'ExpR':>7} {'WR%':>6} "
          f"{'TotalR':>8} {'MaxDD':>7}")
    print("  " + "-"*60)
    for be, act, dist, m in all_combos[:10]:
        marca = " ←" if (be,act,dist)==(best_combo[0],best_combo[1],best_combo[2]) else ""
        print(f"  {be:>4}R {act:>5}R {dist:>4}R {m['pf']:>7} {m['exp_r']:>7} "
              f"{m['wr']:>6} {m['total_r']:>8} {m['max_dd']:>7}{marca}")

    print(f"\n  CONFIGURACION OPTIMA:")
    print(f"    Break-even trigger: {best_combo[0]}R")
    print(f"    Trailing activacion: {best_combo[1]}R")
    print(f"    Trailing distancia:  {best_combo[2]}R")
    print(f"    PF={best_combo[3]['pf']} | ExpR={best_combo[3]['exp_r']}R | "
          f"WR={best_combo[3]['wr']}% | MaxDD={best_combo[3]['max_dd']}%")

    # ── PARTE 5: Comparar optimo vs V3 original (1R/2R/1R) ───────────────
    print("\n" + "="*80)
    print("  PARTE 5 — OPTIMO vs V3 ORIGINAL")
    print("="*80)

    pnl_v3orig = df.apply(lambda r: simulate_trailing(r, 1.0, 2.0, 1.0), axis=1)
    m_v3 = metrics(pnl_v3orig)
    print(f"  V3 original (BE=1R, act=2R, dist=1R):")
    print(f"    PF={m_v3['pf']} ExpR={m_v3['exp_r']} WR={m_v3['wr']}% MaxDD={m_v3['max_dd']}%")
    print(f"\n  Optimo (BE={best_combo[0]}R, act={best_combo[1]}R, dist={best_combo[2]}R):")
    print(f"    PF={best_combo[3]['pf']} ExpR={best_combo[3]['exp_r']} "
          f"WR={best_combo[3]['wr']}% MaxDD={best_combo[3]['max_dd']}%")

    delta_pf = round(best_combo[3]['pf'] - m_v3['pf'], 3)
    print(f"\n  Diferencia de PF: {'+' if delta_pf>=0 else ''}{delta_pf}")
    if abs(delta_pf) < 0.05:
        print("  → Diferencia marginal. V3 original (1R/2R/1R) es suficientemente bueno")
        print("    y mas simple. Recomendado mantener 1R por parsimonia.")
    else:
        print(f"  → La configuracion optima mejora el PF de forma no trivial.")
        print(f"    Justificado usar los parametros optimos en la validacion barra-a-barra.")

    print("\n  NOTA: Todos los valores usan la aproximacion MFE. La validacion")
    print("  barra-a-barra confirmara los valores absolutos. La comparacion")
    print("  relativa entre parametros es valida bajo el mismo supuesto.")
    print("\nPega el output completo.")
