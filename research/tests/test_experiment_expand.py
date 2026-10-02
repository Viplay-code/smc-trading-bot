"""Tests del expansor declarativo ExperimentSpec -> contratos ejecutables."""
from __future__ import annotations

import pytest

import research
from research import runner
from research.experiment import ExperimentSpec, ExperimentSpecError, expand_experiment_spec


def _parameters(**overrides) -> dict:
    values = {
        "atr_mult": [1.5],
        "atr_period": [14],
        "max_hold": [20],
        "risk": [0.005],
        "cost_per_trade": [0.0009],
    }
    values.update(overrides)
    return values


def _spec(**overrides) -> ExperimentSpec:
    values = {
        "name": "experiment_expand_test",
        "assets": ["BTCUSDT"],
        "years": {"train": 2022},
        "bias": ["A_ema200_neutral"],
        "triggers": ["T1_ema_cross"],
        "entries": ["C_market_close"],
        "managements": ["V3-A"],
        "sessions": ["dcv1_activo_15h"],
        "parameters": _parameters(),
        "independent_variable": "trigger",
    }
    if "parameters" in overrides:
        overrides["parameters"] = _parameters(**overrides["parameters"])
    values.update(overrides)
    return ExperimentSpec(**values)


def test_una_dimension_cualitativa_se_expande():
    contracts = expand_experiment_spec(_spec(triggers=["T1_ema_cross", "A_sweep_bos"]))
    assert [contract["trigger"]["name"] for contract in contracts] == ["T1_ema_cross", "A_sweep_bos"]


def test_dos_dimensiones_cualitativas_forman_producto():
    contracts = expand_experiment_spec(
        _spec(triggers=["T1_ema_cross", "A_sweep_bos"], managements=["V3-A", "V3-B"])
    )
    assert [(c["trigger"]["name"], c["management"]["name"]) for c in contracts] == [
        ("T1_ema_cross", "V3-A"), ("T1_ema_cross", "V3-B"),
        ("A_sweep_bos", "V3-A"), ("A_sweep_bos", "V3-B"),
    ]


def test_multiples_dimensiones_y_producto_cartesiano():
    contracts = expand_experiment_spec(
        _spec(
            assets=["BTCUSDT", "ETHUSDT"], years={"validate": 2023, "train": 2022},
            triggers=["T1_ema_cross", "A_sweep_bos"], managements=["V3-A", "V3-B"],
            parameters={"atr_mult": [1.2, 1.5]},
        )
    )
    assert len(contracts) == 2 * 2 * 2 * 2 * 2


def test_orden_es_determinista():
    spec = _spec(
        assets=["ETHUSDT", "BTCUSDT"], years={"validate": 2023, "train": 2022},
        triggers=["T1_ema_cross", "A_sweep_bos"], parameters={"atr_mult": [1.2, 1.5]},
    )
    first = expand_experiment_spec(spec)
    second = expand_experiment_spec(spec)
    assert first == second
    assert [(c["assets"][0], next(iter(c["years"]))) for c in first[:4]] == [
        ("ETHUSDT", "train"), ("ETHUSDT", "validate"),
        ("BTCUSDT", "train"), ("BTCUSDT", "validate"),
    ]


def test_assets_por_years_preserva_roles_y_anios():
    contracts = expand_experiment_spec(
        _spec(assets=["BTCUSDT", "ETHUSDT"], years={"validate": 2023, "train": 2022})
    )
    assert [(c["assets"][0], c["years"]) for c in contracts] == [
        ("BTCUSDT", {"train": 2022}), ("BTCUSDT", {"validate": 2023}),
        ("ETHUSDT", {"train": 2022}), ("ETHUSDT", {"validate": 2023}),
    ]


def test_parametros_escalares_se_materializan_en_contratos():
    contracts = expand_experiment_spec(
        _spec(parameters={
            "atr_mult": [1.2, 1.5], "atr_period": [14], "max_hold": [10, 20],
            "risk": [0.005], "cost_per_trade": [0.0009],
        })
    )
    assert [(c["atr_mult"], c["atr_period"], c["max_hold"], c["risk"], c["cost_per_trade"])
            for c in contracts] == [
        (1.2, 14, 10, 0.005, 0.0009), (1.2, 14, 20, 0.005, 0.0009),
        (1.5, 14, 10, 0.005, 0.0009), (1.5, 14, 20, 0.005, 0.0009),
    ]
    assert all("parameter_grid" not in contract for contract in contracts)


def test_contratos_generados_pasan_validate_contract():
    contracts = expand_experiment_spec(
        _spec(assets=["BTCUSDT", "ETHUSDT"], years={"train": 2022, "validate": 2023})
    )
    for contract in contracts:
        runner.validate_contract(contract)


def test_contratos_generados_se_ejecutan_directamente_con_run_many():
    contracts = expand_experiment_spec(_spec())
    assert runner.run_many(contracts) == [runner.run(contract) for contract in contracts]


def test_expansion_no_ejecuta_el_runner():
    original_run = runner.run

    def fail_if_called(*args, **kwargs):
        raise AssertionError("expand_experiment_spec no debe ejecutar runner.run")

    runner.run = fail_if_called
    try:
        assert len(expand_experiment_spec(_spec())) == 1
    finally:
        runner.run = original_run


def test_mismo_spec_produce_mismos_contratos_y_hashes():
    spec = _spec(parameters={"cost_per_trade": [0.0005, 0.0009]})
    first = expand_experiment_spec(spec)
    second = expand_experiment_spec(spec)
    assert [research.compute_contract_hash(c) for c in first] == [
        research.compute_contract_hash(c) for c in second
    ]


def test_dimensiones_cualitativas_duplicadas_rechazan_sobreexpansion():
    with pytest.raises(ExperimentSpecError, match="assets.*duplicados"):
        expand_experiment_spec(_spec(assets=["BTCUSDT", "BTCUSDT"]))
    with pytest.raises(ExperimentSpecError, match="triggers.*duplicados"):
        expand_experiment_spec(_spec(triggers=["T1_ema_cross", "T1_ema_cross"]))


def test_parametros_e_independent_variable_son_explicitos():
    common = {
        "name": "explicit_fields",
        "assets": ["BTCUSDT"],
        "years": {"train": 2022},
        "bias": ["A_ema200_neutral"],
        "triggers": ["T1_ema_cross"],
        "entries": ["C_market_close"],
        "managements": ["V3-A"],
        "sessions": ["control_8h"],
    }
    with pytest.raises(ExperimentSpecError, match="parámetros escalares"):
        expand_experiment_spec(ExperimentSpec(
            **common, parameters={"atr_mult": [1.5]}, independent_variable="trigger"
        ))
    with pytest.raises(TypeError):
        ExperimentSpec(**common, parameters=_parameters())


def test_independent_variable_se_conserva_sin_afectar_la_expansion():
    first = expand_experiment_spec(_spec(independent_variable="trigger"))[0]
    second = expand_experiment_spec(_spec(independent_variable="session"))[0]
    comparable_first = {k: v for k, v in first.items() if k != "independent_variable"}
    comparable_second = {k: v for k, v in second.items() if k != "independent_variable"}
    assert comparable_first == comparable_second
    assert research.compute_contract_hash(first) != research.compute_contract_hash(second)


def test_contratos_de_salida_no_comparten_mutables_con_otra_expansion():
    spec = _spec()
    first = expand_experiment_spec(spec)
    first[0]["bias"]["params"]["mutated"] = True
    second = expand_experiment_spec(spec)
    assert "mutated" not in second[0]["bias"]["params"]


def test_rechaza_cardinalidad_de_parameter_grid():
    with pytest.raises(ExperimentSpecError, match="MAX_GRID_CELLS"):
        expand_experiment_spec(_spec(parameters={"atr_mult": list(range(runner.MAX_GRID_CELLS + 1))}))


def test_rechaza_cardinalidad_de_universo():
    with pytest.raises(ExperimentSpecError, match="MAX_UNIVERSE_CELLS"):
        expand_experiment_spec(
            _spec(
                assets=["A1", "A2", "A3", "A4"],
                years={"a": 2020, "b": 2021, "c": 2022, "d": 2023},
            )
        )


def test_especificacion_invalida_rechaza_sin_inventar_roles():
    with pytest.raises(ExperimentSpecError, match="period_role"):
        expand_experiment_spec(_spec(years=[2022, 2023]))
    with pytest.raises(ExperimentSpecError, match="no admite"):
        expand_experiment_spec(_spec(parameters={"unsupported": [1]}))


def test_matriz_pequena_equivale_a_trigger_campaign_migrada():
    from scripts import trigger_campaign

    spec = _spec(
        name="trigger_campaign",
        triggers=["T1_ema_cross", "A_sweep_bos"], managements=["V3-A", "V3-B"],
        sessions=["control_8h"],
    )
    actual = expand_experiment_spec(spec)
    expected = trigger_campaign.build_universe(
        ("BTCUSDT",), {"train": 2022},
        triggers=("T1_ema_cross", "A_sweep_bos"), managements=("V3-A", "V3-B"),
    )
    # La campaña histórica deja atr_period implícito en el default de
    # backtest.Config; ExperimentSpec lo materializa para poder expandirlo.
    for contract in expected:
        contract["atr_period"] = 14
    assert actual == expected
