"""
research/tests/test_expand_universe.py — Automatización experimental,
Componente 4 (`expand_universe`, expansión del universo experimental,
2026-09-04).

`expand_universe` expande ÚNICAMENTE `assets`/`years` de un template en su
producto cartesiano, produciendo contratos completos e independientes,
copiando todo lo demás (incluido `name`) verbatim — sin generar nombres,
sin calcular hashes, sin ejecutar `run()`, sin I/O, sin ninguna lógica de
fases train/validate/blind.

Explícitamente NO prueba composición con `parameter_grid` (fuera de
alcance de este componente).

Ejecutar:
    python -m research.tests.test_expand_universe  (o con pytest)
"""
from __future__ import annotations

import copy
import sys

sys.path.insert(0, ".")
import research
from research import expand_universe, MAX_UNIVERSE_CELLS
from research import runner


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}


def _template(assets=None, years=None, **overrides) -> dict:
    """Template base — misma forma que un contrato válido de
    research/tests/, salvo que assets/years pueden tener longitud != 1."""
    t = {
        "name": "expand_universe_check", "contract_version": "1",
        "assets": list(assets) if assets is not None else ["BTCUSDT"],
        "years": dict(years) if years is not None else {"train": 2022},
        "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}},
        "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": "V3-A", "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": dict(_CANONICAL_GATES), "independent_variable": "management.name",
        "blind_authorized": False,
    }
    t.update(overrides)
    return t


# --------------------------------------------------------------------------- #
# 1. Caso trivial 1x1                                                        #
# --------------------------------------------------------------------------- #
def test_un_activo_un_role_year():
    t = _template(assets=["BTCUSDT"], years={"train": 2022})
    out = expand_universe(t)
    ok = (
        len(out) == 1
        and out[0]["assets"] == ["BTCUSDT"]
        and out[0]["years"] == {"train": 2022}
        and out[0]["name"] == t["name"]
        and out[0] == {**t, "assets": ["BTCUSDT"], "years": {"train": 2022}}
    )
    return _p("expand_universe con 1 activo x 1 role/year produce exactamente 1 "
              "contrato equivalente al template (assets/years normalizados, resto idéntico)", ok)


# --------------------------------------------------------------------------- #
# 2-3. Cardinalidad                                                          #
# --------------------------------------------------------------------------- #
def test_cardinalidad_2x2():
    t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
    out = expand_universe(t)
    ok = len(out) == 4
    return _p(f"expand_universe con 2 activos x 2 roles produce 4 contratos (obtenido: {len(out)})", ok)


def test_cardinalidad_3x3():
    t = _template(
        assets=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        years={"train": 2022, "validate": 2023, "blind": 2024},
        blind_authorized=True,
    )
    out = expand_universe(t)
    ok = len(out) == 9
    return _p(f"expand_universe con 3 activos x 3 roles produce 9 contratos (obtenido: {len(out)})", ok)


# --------------------------------------------------------------------------- #
# 4-5. Orden determinista                                                    #
# --------------------------------------------------------------------------- #
def test_orden_de_assets_preservado():
    t = _template(assets=["SOLUSDT", "BTCUSDT", "ETHUSDT"], years={"train": 2022})
    out = expand_universe(t)
    ok = [c["assets"][0] for c in out] == ["SOLUSDT", "BTCUSDT", "ETHUSDT"]
    return _p("expand_universe conserva el orden LITERAL de assets declarado en el "
              "template (no lo reordena)", ok)


def test_orden_alfabetico_de_roles():
    t = _template(assets=["BTCUSDT"], years={"validate": 2023, "train": 2022, "blind": 2024},
                  blind_authorized=True)
    out = expand_universe(t)
    ok = [list(c["years"].keys())[0] for c in out] == ["blind", "train", "validate"]
    return _p("expand_universe recorre los roles de years en orden ALFABÉTICO "
              "(no en el orden de inserción del dict)", ok)


# --------------------------------------------------------------------------- #
# 6-7. No mutación / independencia de copias                                 #
# --------------------------------------------------------------------------- #
def test_no_muta_el_template():
    t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
    snapshot = copy.deepcopy(t)
    expand_universe(t)
    ok = t == snapshot
    return _p("expand_universe no muta el template de entrada", ok)


def test_copias_independientes_entre_si():
    t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022})
    out = expand_universe(t)
    # Mutar un campo anidado de un resultado no debe afectar al otro ni al template.
    out[0]["bias"]["params"]["nuevo"] = "valor_mutado"
    ok = (
        "nuevo" not in out[1]["bias"]["params"]
        and "nuevo" not in t["bias"]["params"]
        and out[0] is not out[1]
        and out[0]["bias"] is not out[1]["bias"]
    )
    return _p("Los contratos generados son copias PROFUNDAS e independientes entre sí "
              "y del template (mutar uno no afecta a los demás)", ok)


# --------------------------------------------------------------------------- #
# 8. Campos verbatim, incluido name                                          #
# --------------------------------------------------------------------------- #
def test_campos_distintos_de_assets_years_son_verbatim():
    t = _template(
        assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023},
        hypothesis="una hipotesis cualquiera", space="Espacio X",
    )
    out = expand_universe(t)
    campos = ("name", "contract_version", "bias", "trigger", "entry", "session",
              "management", "risk", "cost_per_trade", "max_hold", "atr_mult",
              "gates", "independent_variable", "blind_authorized",
              "hypothesis", "space")
    ok = all(all(c[campo] == t[campo] for campo in campos) for c in out)
    return _p("Todo campo distinto de assets/years (incluido name, hypothesis, space, "
              "gates, etc.) aparece IDÉNTICO, sin transformación, en cada contrato generado", ok)


# --------------------------------------------------------------------------- #
# 9-10. assets/years ausentes o vacíos                                       #
# --------------------------------------------------------------------------- #
def test_assets_ausente_rechaza():
    t = _template()
    del t["assets"]
    ok = True
    try:
        expand_universe(t)
        ok = False
    except ValueError:
        pass
    return _p("expand_universe con 'assets' ausente -> ValueError", ok)


def test_assets_vacio_rechaza():
    t = _template(assets=[])
    ok = True
    try:
        expand_universe(t)
        ok = False
    except ValueError:
        pass
    return _p("expand_universe con 'assets' vacío -> ValueError", ok)


def test_years_ausente_rechaza():
    t = _template()
    del t["years"]
    ok = True
    try:
        expand_universe(t)
        ok = False
    except ValueError:
        pass
    return _p("expand_universe con 'years' ausente -> ValueError", ok)


def test_years_vacio_rechaza():
    t = _template(years={})
    ok = True
    try:
        expand_universe(t)
        ok = False
    except ValueError:
        pass
    return _p("expand_universe con 'years' vacío -> ValueError", ok)


# --------------------------------------------------------------------------- #
# 11. Exceso de MAX_UNIVERSE_CELLS                                           #
# --------------------------------------------------------------------------- #
def test_excede_max_universe_cells_rechaza():
    # 4 activos x 4 roles = 16 > MAX_UNIVERSE_CELLS (12).
    t = _template(
        assets=["A1", "A2", "A3", "A4"],
        years={"r1": 2020, "r2": 2021, "r3": 2022, "r4": 2023},
    )
    ok = 4 * 4 > MAX_UNIVERSE_CELLS
    try:
        expand_universe(t)
        ok = False
    except ValueError:
        pass
    return _p(f"expand_universe con cardinalidad 16 > MAX_UNIVERSE_CELLS={MAX_UNIVERSE_CELLS} "
              f"-> ValueError, antes de generar ningún contrato", ok)


def test_no_reutiliza_max_grid_cells():
    """MAX_UNIVERSE_CELLS es una constante separada de
    research.runner.MAX_GRID_CELLS — no la misma."""
    ok = MAX_UNIVERSE_CELLS == 12 and MAX_UNIVERSE_CELLS != runner.MAX_GRID_CELLS
    return _p(f"MAX_UNIVERSE_CELLS ({MAX_UNIVERSE_CELLS}) es una constante separada de "
              f"runner.MAX_GRID_CELLS ({runner.MAX_GRID_CELLS}), no una reutilización", ok)


# --------------------------------------------------------------------------- #
# 12. Todo contrato generado pasa validate_contract                          #
# --------------------------------------------------------------------------- #
def test_contratos_generados_pasan_validate_contract():
    t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
    out = expand_universe(t)
    ok = True
    for c in out:
        try:
            runner.validate_contract(c)
        except runner.ContractError as e:
            ok = False
            print(f"    contrato generado rechazado: {e}")
    return _p("Todos los contratos generados por expand_universe pasan "
              "validate_contract() sin excepción", ok)


# --------------------------------------------------------------------------- #
# 13. No ejecuta nada / sin I/O                                              #
# --------------------------------------------------------------------------- #
def test_no_ejecuta_run_ni_hace_io():
    calls = []
    orig_run = runner.run

    def _spy(contract, include_trades=False):
        calls.append(contract)
        return orig_run(contract, include_trades)

    runner.run = _spy
    try:
        t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
        expand_universe(t)
        ok = len(calls) == 0
    finally:
        runner.run = orig_run
    return _p("expand_universe no invoca run() ni ejecuta nada — pura manipulación de dicts", ok)


# --------------------------------------------------------------------------- #
# 14. Composición con run_many                                               #
# --------------------------------------------------------------------------- #
def test_composicion_run_many_expand_universe():
    t = _template(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
    contracts = expand_universe(t)

    esperado = [runner.run(dict(c)) for c in contracts]
    obtenido = runner.run_many(expand_universe(t))  # nueva expansión, misma especificación

    ok = (
        obtenido == esperado
        and [(r.asset, r.period, r.period_role) for r in obtenido]
        == [("BTCUSDT", 2022, "train"), ("BTCUSDT", 2023, "validate"),
            ("ETHUSDT", 2022, "train"), ("ETHUSDT", 2023, "validate")]
    )
    return _p("run_many(expand_universe(template)) equivale a ejecutar individualmente "
              "cada celda esperada, sin ningún adaptador adicional", ok)


# --------------------------------------------------------------------------- #
# 15. blind + blind_authorized=True — sin lógica especial de fases           #
# --------------------------------------------------------------------------- #
def test_blind_se_expande_sin_logica_especial_de_fases():
    """Confirma explícitamente que expand_universe NO introduce ninguna
    lógica de fases: un template con rol 'blind' junto a 'train' se
    expande igual que cualquier otro rol — el único guardrail sigue
    siendo blind_authorized, ya validado por validate_contract."""
    t = _template(
        assets=["BTCUSDT"], years={"train": 2022, "blind": 2024},
        blind_authorized=True,
    )
    out = expand_universe(t)
    ok = len(out) == 2
    roles = sorted(list(c["years"].keys())[0] for c in out)
    ok = ok and roles == ["blind", "train"]
    for c in out:
        try:
            runner.validate_contract(c)
        except runner.ContractError as e:
            ok = False
            print(f"    {e}")
    return _p("Template con rol 'blind' + blind_authorized=True genera la celda "
              "normalmente (2 celdas, sin bloqueo ni tratamiento especial) — sin "
              "ninguna lógica de fases introducida", ok)


# --------------------------------------------------------------------------- #
# 16. Determinismo                                                            #
# --------------------------------------------------------------------------- #
def test_determinismo():
    t = _template(assets=["ETHUSDT", "BTCUSDT"], years={"validate": 2023, "train": 2022})
    out1 = expand_universe(t)
    out2 = expand_universe(t)
    ok = out1 == out2
    return _p("Mismo template ejecutado dos veces produce listas idénticas (determinismo)", ok)


ALL_TESTS = [
    test_un_activo_un_role_year,
    test_cardinalidad_2x2,
    test_cardinalidad_3x3,
    test_orden_de_assets_preservado,
    test_orden_alfabetico_de_roles,
    test_no_muta_el_template,
    test_copias_independientes_entre_si,
    test_campos_distintos_de_assets_years_son_verbatim,
    test_assets_ausente_rechaza,
    test_assets_vacio_rechaza,
    test_years_ausente_rechaza,
    test_years_vacio_rechaza,
    test_excede_max_universe_cells_rechaza,
    test_no_reutiliza_max_grid_cells,
    test_contratos_generados_pasan_validate_contract,
    test_no_ejecuta_run_ni_hace_io,
    test_composicion_run_many_expand_universe,
    test_blind_se_expande_sin_logica_especial_de_fases,
    test_determinismo,
]


def main():
    print("research/tests/test_expand_universe — Componente 4 (expansión del universo "
          "experimental)\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
