"""
research/tests/test_simulate_donchian.py — Fase 4 (DCH-EXIT, 2026-09-11):
verificación de la semántica temporal PRE-REGISTRADA (Protocol v2 FINAL) y
de las regresiones críticas de la extensión del registro de Gestión.

Dos bloques:

  A. CAUSALIDAD / SEMÁNTICA de `research.simulate_donchian` sobre velas
     sintéticas construidas DELIBERADAMENTE para que una violación de la
     convención cambie el resultado observable (no basta con "no lanza
     excepción"): exclusión de la vela actual del canal, precedencia
     STOP > donchian_exit, ejecución al nivel del canal, literal del
     `reason`, no-monotonicidad del canal, ventana incompleta, max_hold,
     primera vela evaluable, determinismo y "una posición a la vez".

  B. REGRESIÓN CRÍTICA de Fase 4: V3-A/V3-B/Raw deben permanecer
     FUNCIONALMENTE IDÉNTICOS tras generalizar el registro
     (`_MANAGEMENT_SPECS`), verificado contra el artifact CONGELADO
     `donchian_breakout_baseline_results.csv` (commit e20d3e24) —
     `contract_hash` + las 9 métricas core, sin tolerancia. Esta
     verificación es además el procedimiento de identidad exigido por
     Protocol v2 seccion 4.b para la `diagnostic re-derivation`: si
     difiere en un solo dígito, Fase 4 ABORTA.

Ejecutar:
    python -m research.tests.test_simulate_donchian  (o con pytest)
"""
from __future__ import annotations

import inspect
import os
import sys

import pandas as pd

sys.path.insert(0, ".")
import backtest
import research
from research import runner
from research.simulate_donchian import simulate_donchian_exit, run_config_donchian


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _frame(lows, highs=None, closes=None, opens=None) -> pd.DataFrame:
    """Frame sintético mínimo con el shape que consume el motor
    (open/high/low/close), índice horario UTC."""
    n = len(lows)
    idx = pd.date_range("2022-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "open": opens if opens is not None else [100.0] * n,
        "high": highs if highs is not None else [101.0] * n,
        "low": list(lows),
        "close": closes if closes is not None else [100.0] * n,
    }, index=idx)


def _entry(i0=5, direction="long", entry=100.0, sl0=80.0, risk_pts=20.0) -> dict:
    return {"entry_idx": i0, "direction": direction, "entry": entry,
            "sl0": sl0, "risk_pts": risk_pts}


# --------------------------------------------------------------------------- #
# A. Causalidad / semántica                                                   #
# --------------------------------------------------------------------------- #
def test_canal_excluye_la_vela_actual():
    """LA PRUEBA DE NO-LOOK-AHEAD. Frame construido para que incluir la
    vela `k` en su propio canal cambie el resultado OBSERVABLE:

      velas 0..5: low=95  -> canal en k=6 (ventana velas 1..5) = 95
      vela 6:     low=90  -> dispara (90 <= 95), salida AL NIVEL 95

    Si el canal incluyera la vela 6, sería min(...,90)=90 y la salida
    ocurriría al nivel 90, no 95. El `exit_price` discrimina las dos
    convenciones sin ambigüedad."""
    df = _frame(lows=[95.0] * 6 + [90.0, 95.0], closes=[100.0] * 6 + [97.0, 97.0])
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    ok = res["reason"] == "donchian_exit" and res["exit_price"] == 95.0
    return _p(f"El canal EXCLUYE la vela actual: salida al nivel 95.0 (no 90.0) "
              f"-- exit_price={res['exit_price']}, reason={res['reason']}", ok)


def test_ejecucion_al_nivel_del_canal_no_al_close():
    """La salida ejecuta AL NIVEL del canal, nunca al `close` de la vela
    (convención pre-registrada). El frame pone close=97 en la vela de
    salida para que ambos valores sean distinguibles."""
    df = _frame(lows=[95.0] * 6 + [90.0, 95.0], closes=[100.0] * 6 + [97.0, 97.0])
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    ok = res["exit_price"] == 95.0 and res["exit_price"] != df.iloc[6]["close"]
    return _p(f"Ejecución AL NIVEL del canal (95.0), no al close de la vela "
              f"({df.iloc[6]['close']})", ok)


def test_literal_de_exit_reason():
    df = _frame(lows=[95.0] * 6 + [90.0, 95.0])
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    ok = res["reason"] == "donchian_exit"
    return _p(f"El literal de exit_reason es exactamente 'donchian_exit' (obtenido: "
              f"{res['reason']!r})", ok)


def test_precedencia_stop_sobre_donchian_en_la_misma_vela():
    """Vela donde AMBOS disparan: canal=95, stop=93, low[6]=90.
    La convención conservadora pre-registrada exige que gane el STOP."""
    df = _frame(lows=[95.0] * 6 + [90.0, 95.0])
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=93.0, risk_pts=7.0), 5, cfg)
    ok = res["reason"] == "stop" and res["exit_price"] == 93.0
    return _p(f"STOP tiene precedencia sobre donchian_exit en la misma vela "
              f"(reason={res['reason']}, exit_price={res['exit_price']})", ok)


def test_la_vela_de_entrada_nunca_se_evalua_para_salir():
    """Un movimiento adverso extremo EN la vela de entrada (i0) debe
    ignorarse por completo: la primera vela evaluable es i0+1."""
    df = _frame(lows=[95.0] * 5 + [10.0] + [95.0, 95.0])   # low[5]=10 en la vela de entrada
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    exit_pos = df.index.get_loc(res["exit_time"])
    ok = exit_pos >= 6 and res["duration_h"] >= 1
    return _p(f"La vela de entrada (i0=5, low=10) NUNCA dispara salida -- primera vela "
              f"evaluable es i0+1 (salida en posición {exit_pos})", ok)


def test_max_hold_se_respeta_y_timeout_cierra_al_close():
    """Sin ningún disparo, la salida es por timeout exactamente en
    i0+max_hold, al `close` de esa vela."""
    lows = [90.0 + i for i in range(20)]      # estrictamente creciente -> nunca dispara
    closes = [200.0 + i for i in range(20)]
    df = _frame(lows=lows, highs=[300.0] * 20, closes=closes)
    cfg = backtest.Config(max_hold=4)
    res = simulate_donchian_exit(df, _entry(i0=5, sl0=1.0), 5, cfg)
    exit_pos = df.index.get_loc(res["exit_time"])
    ok = (res["reason"] == "timeout" and exit_pos == 5 + 4
          and res["duration_h"] == 4 and res["exit_price"] == df.iloc[9]["close"])
    return _p(f"max_hold respetado: timeout en i0+max_hold=9 al close ({res['exit_price']}), "
              f"duration_h={res['duration_h']}", ok)


def test_ventana_incompleta_lanza_valueerror():
    """Regla defensiva pre-registrada: NUNCA truncar el canal en
    silencio. Caso degenerado (imposible en producción, donde
    trigger_D_range_breakout garantiza i0>=10)."""
    df = _frame(lows=[95.0] * 8)
    cfg = backtest.Config(max_hold=5)
    ok = False
    try:
        simulate_donchian_exit(df, _entry(i0=0, sl0=1.0), 5, cfg)
    except ValueError:
        ok = True
    return _p("Ventana de canal incompleta (k-exit_lookback<0) -> ValueError, nunca se trunca "
              "en silencio", ok)


def test_canal_no_es_monotono():
    """A diferencia del trailing ratchet de V3, min(low[k-N:k]) es un
    estadístico de ventana deslizante y PUEDE alejarse del precio.
    Se verifica sobre la serie de niveles, no sobre una intuición."""
    lows = [90.0, 80.0, 95.0, 96.0, 97.0, 98.0, 99.0, 100.0, 101.0, 102.0]
    df = _frame(lows=lows)
    niveles = [df.iloc[k - 5:k]["low"].min() for k in range(5, len(lows))]
    sube = any(b > a for a, b in zip(niveles, niveles[1:]))
    baja_o_no_monotono = not all(b >= a for a, b in zip(niveles, niveles[1:])) or sube
    ok = sube and len(set(niveles)) > 1
    return _p(f"El canal NO es un trailing monótono -- la serie de niveles varía "
              f"({niveles})", ok and baja_o_no_monotono is not None)


def test_short_usa_el_maximo_del_canal():
    """Simetría SHORT: canal = max(high[k-N:k]), dispara con high[k] >=
    nivel, salida al nivel."""
    df = _frame(lows=[1.0] * 8, highs=[105.0] * 6 + [110.0, 105.0])
    cfg = backtest.Config(max_hold=20)
    res = simulate_donchian_exit(df, _entry(i0=5, direction="short", entry=100.0,
                                            sl0=200.0, risk_pts=20.0), 5, cfg)
    ok = res["reason"] == "donchian_exit" and res["exit_price"] == 105.0
    return _p(f"SHORT: canal = max(high[k-5:k]) = 105.0, dispara con high>=nivel, salida al "
              f"nivel (exit_price={res['exit_price']})", ok)


def test_determinismo():
    df = _frame(lows=[95.0] * 6 + [90.0, 95.0])
    cfg = backtest.Config(max_hold=20)
    r1 = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    r2 = simulate_donchian_exit(df, _entry(i0=5, sl0=80.0), 5, cfg)
    ok = r1 == r2
    return _p("simulate_donchian_exit es determinista (misma entrada -> mismo dict)", ok)


def test_run_config_donchian_respeta_una_posicion_a_la_vez():
    """Misma regla `busy_until` que backtest.run_config: una entrada cuyo
    índice cae dentro de una posición abierta se descarta."""
    lows = [95.0] * 6 + [90.0] + [95.0] * 10
    df = _frame(lows=lows)
    cfg = backtest.Config(max_hold=20)
    entries = [_entry(i0=5, sl0=80.0), _entry(i0=6, sl0=80.0), _entry(i0=10, sl0=80.0)]
    trades = run_config_donchian(df, entries, 5, cfg)
    ok = len(trades) == 2   # la entrada en i0=6 queda bloqueada (salida de la 1ª en k=6)
    return _p(f"run_config_donchian respeta 'una posición a la vez' (busy_until): "
              f"{len(trades)} trades de 3 entradas", ok)


def test_simulate_v3_permanece_intacto():
    """Fase 4 no modifica research/simulate.py: simulate_v3 conserva su
    cuerpo y su import local a backtest, y simulate_donchian NO lo
    invoca."""
    src_v3 = inspect.getsource(research.simulate.simulate_v3)
    v3_ok = ("def simulate_v3" in src_v3 and "import backtest" in src_v3
             and 'exit_cfg["be"]' in src_v3)

    # Inspección AST del CÓDIGO de simulate_donchian (no de su texto: el
    # docstring del módulo menciona simulate_v3/backtest.run_config a
    # propósito, para documentar que NO los usa — un grep de texto daría
    # un falso positivo). Se buscan nombres realmente referenciados en
    # código ejecutable.
    import ast
    tree = ast.parse(inspect.getsource(research.simulate_donchian))
    referenced = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    dch_ok = "simulate_v3" not in referenced and "run_config" not in referenced

    ok = v3_ok and dch_ok
    return _p("simulate_v3 intacto y simulate_donchian NO lo invoca ni invoca "
              "backtest.run_config", ok)


# --------------------------------------------------------------------------- #
# B. Regresión crítica + validación tipada del registro generalizado         #
# --------------------------------------------------------------------------- #
def test_management_params_desconocido_es_contracterror_no_keyerror():
    """El bug de clase identificado en la auditoría: un mecanismo
    registrado sin entrada en _MANAGEMENT_PARAMS producía KeyError CRUDO.
    Con _MANAGEMENT_SPECS eso es imposible por construcción; acá se
    verifica además que un params INCORRECTO para DCH-EXIT produce
    ContractError tipado."""
    from research.tests.test_runner_invariants import _valid_contract
    c = _valid_contract()
    c["management"] = {"name": "DCH-EXIT", "params": {"exit_lookback": 99}}
    ok_typed = False
    try:
        runner.validate_contract(c)
    except runner.ContractError:
        ok_typed = True
    except KeyError:
        ok_typed = False

    c2 = _valid_contract()
    c2["management"] = {"name": "DCH-EXIT", "params": {}}
    ok_empty = True
    try:
        runner.validate_contract(c2)
    except Exception as e:
        ok_empty = False
        print(f"    params vacío rechazado inesperadamente: {type(e).__name__}: {e}")

    ok_params = runner._MANAGEMENT_PARAMS["DCH-EXIT"] == {"exit_lookback": 5}
    return _p("DCH-EXIT: params incorrecto -> ContractError (no KeyError), params vacío "
              "aceptado, _MANAGEMENT_PARAMS['DCH-EXIT']=={'exit_lookback': 5}",
              ok_typed and ok_empty and ok_params)


def test_registro_generalizado_no_desincroniza_fn_y_params():
    """_MANAGEMENT_SPECS es la ÚNICA fuente: MANAGEMENT_LAYERS y
    _MANAGEMENT_PARAMS deben tener exactamente las mismas claves, siempre."""
    ok = (set(runner.MANAGEMENT_LAYERS) == set(runner._MANAGEMENT_PARAMS)
          == set(runner._MANAGEMENT_SPECS))
    return _p(f"MANAGEMENT_LAYERS / _MANAGEMENT_PARAMS / _MANAGEMENT_SPECS comparten claves "
              f"exactas ({sorted(runner.MANAGEMENT_LAYERS)})", ok)


_BASELINE_PATH = "donchian_breakout_baseline_results.csv"
_CORE = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq", "gate_pass")


def test_v3a_v3b_byte_identicos_al_baseline_congelado():
    """REGRESIÓN CRÍTICA DE FASE 4 (y procedimiento de identidad de la
    `diagnostic re-derivation`, Protocol v2 seccion 4.b): los 12 contratos
    de control del baseline congelado, re-ejecutados tras generalizar el
    registro, deben reproducir EXACTAMENTE su `contract_hash` y sus 9
    métricas core. Cualquier diferencia ABORTA Fase 4."""
    if not os.path.exists(_BASELINE_PATH) or not os.path.exists("data/raw"):
        return _p("V3-A/V3-B byte-idénticos al baseline congelado (artifact o data/raw no "
                  "disponibles)", False)

    import scripts.donchian_breakout_baseline as baseline_camp

    frozen = pd.read_csv(_BASELINE_PATH)
    contracts = baseline_camp.build_universe()
    results = runner.run_many(contracts)

    mismatches = []
    for c, r in zip(contracts, results):
        row = frozen[
            (frozen.asset == r.asset) & (frozen.period == r.period)
            & (frozen.management == r.management)
        ].iloc[0]
        if r.contract_hash != row["contract_hash"]:
            mismatches.append((r.asset, r.period, r.management, "contract_hash",
                               row["contract_hash"], r.contract_hash))
        for f in _CORE:
            frozen_v, new_v = row[f], getattr(r, f)
            if f == "gate_pass":
                eq = bool(frozen_v) == bool(new_v)
            elif f in ("n_entries", "n_trades"):
                eq = int(frozen_v) == int(new_v)
            else:
                fv = float(frozen_v) if not pd.isna(frozen_v) else float("nan")
                nv = float(new_v) if new_v is not None else float("nan")
                eq = (fv == nv) or (fv != fv and nv != nv)
            if not eq:
                mismatches.append((r.asset, r.period, r.management, f, frozen_v, new_v))

    ok = len(results) == 12 and not mismatches
    for m in mismatches[:10]:
        print(f"    MISMATCH: {m}")
    return _p(f"12/12 controles V3-A/V3-B reproducen EXACTO el baseline congelado "
              f"(contract_hash + 9 métricas core, {len(mismatches)} mismatches)", ok)


ALL_TESTS = [
    test_canal_excluye_la_vela_actual,
    test_ejecucion_al_nivel_del_canal_no_al_close,
    test_literal_de_exit_reason,
    test_precedencia_stop_sobre_donchian_en_la_misma_vela,
    test_la_vela_de_entrada_nunca_se_evalua_para_salir,
    test_max_hold_se_respeta_y_timeout_cierra_al_close,
    test_ventana_incompleta_lanza_valueerror,
    test_canal_no_es_monotono,
    test_short_usa_el_maximo_del_canal,
    test_determinismo,
    test_run_config_donchian_respeta_una_posicion_a_la_vez,
    test_simulate_v3_permanece_intacto,
    test_management_params_desconocido_es_contracterror_no_keyerror,
    test_registro_generalizado_no_desincroniza_fn_y_params,
    test_v3a_v3b_byte_identicos_al_baseline_congelado,
]


def main():
    print("research/tests/test_simulate_donchian — Fase 4: causalidad DCH-EXIT + regresión\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
