"""
research/tests/test_metrics_gate_consolidation.py — Fase 1 de la
infraestructura de `research/runner.py` (2026-09-02): validación de que
consolidar `gate_check` en `research/metrics.py` NO cambió umbrales ni
semántica, y validación del esquema canónico nuevo (`research/schema.py`).

Cuatro categorías:
  1. GATE — equivalencia exacta contra la fórmula literal anterior
     (reconstruida acá de forma independiente, no importada), incluyendo
     casos límite (pf/max_dd/exp_r/freq exactamente en el umbral).
  2. IDENTIDAD — `research.gate_check` es EL MISMO objeto que
     `scripts.bias_campaign.gate_check`, y que el que usan las ~25
     campañas legacy (`gate_check = bias_camp.gate_check`).
  3. ESQUEMA — `ExperimentResult`/`TradeRecord` son deterministas, y los
     campos ausentes en el `dict`/`metrics` de origen quedan `None`, nunca
     fabricados.
  4. LEGACY — una muestra representativa de scripts de campaña sigue
     important y ejecutando `gate_check` sin excepciones tras la
     consolidación.

Ejecutar:
    python -m research.tests.test_metrics_gate_consolidation  (o con pytest)
"""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")
import research
import research.metrics as metrics_mod
import research.schema as schema_mod
import scripts.bias_campaign as bias_camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


# --------------------------------------------------------------------------- #
# 1. GATE — equivalencia exacta contra la fórmula literal anterior           #
# --------------------------------------------------------------------------- #
def _gate_check_literal_anterior(m: dict | None) -> bool:
    """Reconstrucción INDEPENDIENTE (no importada) de la fórmula que vivía
    en scripts/bias_campaign.py antes de esta consolidación — copiada tal
    cual del código fuente ya committeado (commit previo a esta Fase 1),
    para comparar contra research.metrics.gate_check sin depender de que
    ambas compartan implementación."""
    if m is None:
        return False
    return bool(
        m["pf"] >= 1.50
        and m["max_dd"] >= -10
        and m["exp_r"] > 0
        and 6 <= m["freq"] <= 12
    )


def test_umbrales_oficiales_no_cambiaron():
    ok = (
        research.PF_MIN == 1.50
        and research.MAX_DD_MIN == -10.0
        and research.EXP_R_MIN == 0.0
        and research.FREQ_MIN_PER_MONTH == 6
        and research.FREQ_MAX_PER_MONTH == 12
    )
    return _p(f"Umbrales oficiales sin cambios: PF>={research.PF_MIN}, "
              f"MaxDD>={research.MAX_DD_MIN}%, ExpR>{research.EXP_R_MIN}, "
              f"freq en [{research.FREQ_MIN_PER_MONTH},{research.FREQ_MAX_PER_MONTH}]", ok)


def test_gate_check_none_devuelve_false():
    ok = metrics_mod.gate_check(None) is False
    return _p("gate_check(None) es False (no lanza)", ok)


def test_gate_check_equivalencia_exacta_casos_limite():
    """Batería de casos, incluyendo exactamente en cada umbral (>=, >, <=),
    comparando research.metrics.gate_check contra la fórmula literal
    reconstruida de forma independiente."""
    casos = [
        {"pf": 1.50, "max_dd": -10.0, "exp_r": 0.001, "freq": 6},    # límite inferior exacto, debe pasar
        {"pf": 1.50, "max_dd": -10.0, "exp_r": 0.001, "freq": 12},   # límite superior exacto, debe pasar
        {"pf": 1.4999, "max_dd": -10.0, "exp_r": 0.001, "freq": 8},  # pf justo debajo -> falla
        {"pf": 1.50, "max_dd": -10.0001, "exp_r": 0.001, "freq": 8}, # max_dd justo debajo -> falla
        {"pf": 1.50, "max_dd": -10.0, "exp_r": 0.0, "freq": 8},      # exp_r exactamente 0 -> falla (estricto >)
        {"pf": 1.50, "max_dd": -10.0, "exp_r": 0.001, "freq": 5.999},# freq justo debajo del piso -> falla
        {"pf": 1.50, "max_dd": -10.0, "exp_r": 0.001, "freq": 12.001},# freq justo sobre el techo -> falla
        {"pf": 2.0, "max_dd": -5.0, "exp_r": 0.1, "freq": 9.0},      # caso claramente OK
        {"pf": 0.8, "max_dd": -15.0, "exp_r": -0.1, "freq": 20.0},   # caso claramente FAIL (todos los gates)
    ]
    ok = True
    for m in casos:
        a = metrics_mod.gate_check(m)
        b = _gate_check_literal_anterior(m)
        if a != b:
            ok = False
            print(f"    mismatch en {m}: research.metrics.gate_check={a} vs literal_anterior={b}")
    return _p(f"research.metrics.gate_check coincide exacto con la fórmula anterior en "
              f"{len(casos)} casos, incluidos los 6 límites exactos (>=, >, <=)", ok)


# --------------------------------------------------------------------------- #
# 2. IDENTIDAD — mismo objeto de función en toda la cadena de re-exports     #
# --------------------------------------------------------------------------- #
def test_identidad_cadena_completa():
    ok = (
        research.gate_check is metrics_mod.gate_check
        and bias_camp.gate_check is research.gate_check
        and bias_camp.FREQ_MIN_PER_MONTH == research.FREQ_MIN_PER_MONTH
        and bias_camp.FREQ_MAX_PER_MONTH == research.FREQ_MAX_PER_MONTH
    )
    return _p("research.gate_check is research.metrics.gate_check is "
              "scripts.bias_campaign.gate_check — un único objeto, sin copias", ok)


def test_campanas_legacy_representativas_mantienen_identidad():
    """Muestra representativa (no las ~25, pero cubre las 3 familias de
    import: directo bias_camp.gate_check, y las 2 que además re-exportan
    FREQ_MIN_PER_MONTH/FREQ_MAX_PER_MONTH) — todas deben seguir apuntando
    al mismo objeto tras la consolidación."""
    import scripts.entry_campaign_t1 as m1
    import scripts.trigger_campaign as m2
    import scripts.gestion_campaign_session as m3
    import scripts.gestion_espacio6_raw_campaign as m4
    ok = (
        m1.gate_check is research.gate_check
        and m2.gate_check is research.gate_check
        and m3.gate_check is research.gate_check
        and m4.gate_check is research.gate_check
        and m1.FREQ_MIN_PER_MONTH == 6
        and m2.FREQ_MIN_PER_MONTH == 6
    )
    return _p("4 campañas legacy representativas (entry_campaign_t1, trigger_campaign, "
              "gestion_campaign_session, gestion_espacio6_raw_campaign) mantienen "
              "gate_check idéntico al consolidado", ok)


# --------------------------------------------------------------------------- #
# 3. ESQUEMA — determinismo y ausencia sin fabricación                      #
# --------------------------------------------------------------------------- #
def test_experiment_result_determinista():
    kwargs = dict(
        experiment_name="test_exp", asset="BTCUSDT", period=2022, period_role="train",
        bias="A", trigger="T1_ema_cross", entry="C_market_close", session="dcv1_activo_15h",
        management="V3-A", n_entries=100, n_trades=95,
        metrics={"pf": 1.2, "wr": 30.0, "exp_r": 0.05, "total_r": 5.0, "max_dd": -8.0, "freq": 8.0},
        gate_pass=False,
    )
    r1 = schema_mod.ExperimentResult.from_metrics(**kwargs)
    r2 = schema_mod.ExperimentResult.from_metrics(**kwargs)
    ok = r1 == r2 and r1.pf == 1.2 and r1.asset == "BTCUSDT"
    return _p("ExperimentResult.from_metrics es determinista (misma entrada -> misma fila, "
              "dataclass frozen con igualdad por valor)", ok)


def test_experiment_result_sin_metrics_no_fabrica_valores():
    r = schema_mod.ExperimentResult.from_metrics(
        experiment_name="test_exp", asset="ETHUSDT", period=2022, period_role="train",
        bias="A", trigger="T1_ema_cross", entry="C_market_close", session="dcv1_activo_15h",
        management="V3-A", n_entries=3, n_trades=2, metrics=None,   # muestra insuficiente
    )
    ok = (r.pf is None and r.wr is None and r.exp_r is None
          and r.total_r is None and r.max_dd is None and r.freq is None
          and r.gate_pass is None and r.contract_hash is None)
    return _p("ExperimentResult.from_metrics con metrics=None deja pf/wr/exp_r/total_r/"
              "max_dd/freq genuinamente en None — no en 0 ni en ningún centinela", ok)


def test_trade_record_determinista():
    raw = {"entry_time": pd.Timestamp("2022-01-01", tz="UTC"),
           "exit_time": pd.Timestamp("2022-01-02", tz="UTC"),
           "direction": "long", "reason": "stop", "pnl_r": -1.02, "duration_h": 24}
    t1 = schema_mod.TradeRecord.from_raw(raw, mechanism="V3-A")
    t2 = schema_mod.TradeRecord.from_raw(raw, mechanism="V3-A")
    ok = t1 == t2 and t1.pnl_r == -1.02
    return _p("TradeRecord.from_raw es determinista (misma entrada -> mismo trade record)", ok)


def test_trade_record_campo_ausente_queda_none_no_fabricado():
    """simulate_v3 (a diferencia de simulate_tp_fixed/simulate_v3_tp) NO
    produce exit_price — el dict crudo no tiene esa clave. from_raw debe
    dejar exit_price=None, nunca inventar un valor (ej. igual a pnl_r*algo
    o a exit_time)."""
    raw_sin_exit_price = {"entry_time": pd.Timestamp("2022-01-01", tz="UTC"),
                           "exit_time": pd.Timestamp("2022-01-02", tz="UTC"),
                           "direction": "long", "reason": "timeout", "pnl_r": 0.5,
                           "duration_h": 24}
    t = schema_mod.TradeRecord.from_raw(raw_sin_exit_price)
    ok = t.exit_price is None and t.entry_price is None and t.mechanism is None
    return _p("TradeRecord.from_raw sobre un dict SIN 'exit_price' (formato real de "
              "simulate_v3) deja exit_price/entry_price/mechanism en None — sin fabricar", ok)


def test_trade_record_campo_presente_se_preserva():
    raw_con_exit_price = {"entry_time": pd.Timestamp("2022-01-01", tz="UTC"),
                           "exit_time": pd.Timestamp("2022-01-02", tz="UTC"),
                           "direction": "short", "reason": "tp", "pnl_r": 2.47,
                           "duration_h": 10, "exit_price": 27321.5}
    t = schema_mod.TradeRecord.from_raw(raw_con_exit_price, mechanism="Espacio6-E1")
    ok = t.exit_price == 27321.5 and t.mechanism == "Espacio6-E1"
    return _p("TradeRecord.from_raw sobre un dict CON 'exit_price' (formato de "
              "simulate_tp_fixed/simulate_v3_tp) lo preserva exacto", ok)


def test_contract_hash_determinista_e_invariante_al_orden_de_claves():
    c1 = {"bias": "A", "trigger": "T1_ema_cross", "years": [2022, 2023]}
    c2 = {"years": [2022, 2023], "trigger": "T1_ema_cross", "bias": "A"}   # mismo contenido, otro orden
    c3 = {"bias": "A", "trigger": "T1_ema_cross", "years": [2022, 2024]}   # contenido distinto
    h1 = schema_mod.compute_contract_hash(c1)
    h2 = schema_mod.compute_contract_hash(c2)
    h3 = schema_mod.compute_contract_hash(c3)
    ok = h1 == h2 and h1 != h3 and isinstance(h1, str) and len(h1) == 16
    return _p(f"compute_contract_hash es determinista e invariante al orden de claves "
              f"({h1}), y distingue contratos con contenido distinto ({h3})", ok)


# --------------------------------------------------------------------------- #
# 4. LEGACY — scripts de campaña siguen funcionando tras la consolidación   #
# --------------------------------------------------------------------------- #
def test_muestra_amplia_de_campanas_legacy_importan_sin_excepcion():
    import importlib
    modulos = [
        "scripts.bias_campaign", "scripts.bias_b_campaign", "scripts.bias_campaign_session",
        "scripts.entry_campaign_sweep_bos", "scripts.entry_campaign_t1",
        "scripts.gestion_campaign_activation", "scripts.gestion_campaign_atr_mult",
        "scripts.gestion_campaign_atr_mult_session", "scripts.gestion_campaign_be",
        "scripts.gestion_campaign_max_hold_session", "scripts.gestion_campaign_multivariable",
        "scripts.gestion_campaign_session", "scripts.gestion_campaign_trailing_distance",
        "scripts.gestion_espacio6_experimento2_be_solo_campaign",
        "scripts.gestion_espacio6_raw_campaign", "scripts.gestion_espacio6_tp_fijo_campaign",
        "scripts.gestion_espacio6_v3a_tp_campaign", "scripts.gestion_espacio6_costo_cero_diagnostico",
        "scripts.integration_campaign_activation", "scripts.integration_campaign_be",
        "scripts.integration_campaign_distance", "scripts.trigger_c_campaign",
        "scripts.trigger_campaign", "scripts.trigger_campaign_sweep_bos_session",
        "scripts.trigger_entry_campaign_rama_b",
    ]
    fallos = []
    for name in modulos:
        try:
            mod = importlib.import_module(name)
            if not callable(getattr(mod, "gate_check", None)):
                fallos.append(f"{name}: gate_check no es callable")
            elif mod.gate_check is not research.gate_check:
                fallos.append(f"{name}: gate_check NO es el objeto consolidado")
        except Exception as e:
            fallos.append(f"{name}: {type(e).__name__}: {e}")
    ok = not fallos
    if fallos:
        for f in fallos:
            print(f"    ! {f}")
    return _p(f"Las {len(modulos)} campañas legacy (todas las que usan gate_check) importan "
              f"sin excepción y quedan con gate_check == research.gate_check", ok)


ALL_TESTS = [
    test_umbrales_oficiales_no_cambiaron,
    test_gate_check_none_devuelve_false,
    test_gate_check_equivalencia_exacta_casos_limite,
    test_identidad_cadena_completa,
    test_campanas_legacy_representativas_mantienen_identidad,
    test_experiment_result_determinista,
    test_experiment_result_sin_metrics_no_fabrica_valores,
    test_trade_record_determinista,
    test_trade_record_campo_ausente_queda_none_no_fabricado,
    test_trade_record_campo_presente_se_preserva,
    test_contract_hash_determinista_e_invariante_al_orden_de_claves,
    test_muestra_amplia_de_campanas_legacy_importan_sin_excepcion,
]


def main():
    print("research/tests/test_metrics_gate_consolidation — Fase 1 de la infraestructura "
          "de research/runner.py\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
