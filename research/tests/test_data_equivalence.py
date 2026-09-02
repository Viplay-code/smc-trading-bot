"""
research/tests/test_data_equivalence.py — Fase 3 (endurecimiento del
runner, 2026-09-02): demuestra que `research.data.load_asset_year`
(implementación NUEVA y AISLADA, ver docstring de research/data.py) es
comportacionalmente idéntica a `scripts.trigger_campaign.load_asset_year`
— no se asume la equivalencia, se compara campo por campo.

También verifica que `resample_4h`/`to_backtest_frame` (MOVIDAS, no
reimplementadas) siguen siendo, tras el re-export desde
`scripts/bias_campaign.py`, literalmente el mismo objeto de función.

Ejecutar:
    python -m research.tests.test_data_equivalence  (o con pytest)
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
import research
import scripts.bias_campaign as bias_camp
import scripts.trigger_campaign as trigger_camp


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _assert_load_asset_year_equivalente(asset: str, year: int) -> None:
    nuevo = research.load_asset_year(asset, year)
    legacy = trigger_camp.load_asset_year(asset, year)

    mismatches = []
    if not nuevo.index.equals(legacy.index):
        mismatches.append("índice (timestamps) difiere")
    for col in ("open", "high", "low", "close", "atr14"):
        if col not in nuevo.columns or col not in legacy.columns:
            mismatches.append(f"columna {col!r} ausente en alguno de los dos")
            continue
        if not nuevo[col].equals(legacy[col]):
            mismatches.append(f"columna {col!r} difiere")
    if "bias_A" not in nuevo.columns:
        mismatches.append("research.load_asset_year no produjo columna bias_A")
    elif "bias_A" not in legacy.columns:
        mismatches.append("scripts.trigger_campaign.load_asset_year no produjo columna bias_A")
    elif not nuevo["bias_A"].equals(legacy["bias_A"]):
        mismatches.append("columna bias_A difiere")

    if mismatches:
        raise AssertionError(
            f"research.load_asset_year({asset!r}, {year!r}) NO es equivalente a "
            f"scripts.trigger_campaign.load_asset_year:\n  " + "\n  ".join(mismatches)
        )


def test_equivalencia_btcusdt_2022():
    ok = True
    try:
        _assert_load_asset_year_equivalente("BTCUSDT", 2022)
    except AssertionError as e:
        ok = False
        print(f"    {e}")
    return _p("research.load_asset_year('BTCUSDT', 2022) == "
              "scripts.trigger_campaign.load_asset_year (índice, OHLC, atr14, bias_A)", ok)


def test_equivalencia_ethusdt_2023():
    ok = True
    try:
        _assert_load_asset_year_equivalente("ETHUSDT", 2023)
    except AssertionError as e:
        ok = False
        print(f"    {e}")
    return _p("research.load_asset_year('ETHUSDT', 2023) == "
              "scripts.trigger_campaign.load_asset_year (índice, OHLC, atr14, bias_A)", ok)


def test_resample_4h_es_el_mismo_objeto_tras_el_wrapper():
    ok = bias_camp.resample_4h is research.resample_4h
    return _p("scripts.bias_campaign.resample_4h ES research.resample_4h (mismo objeto, "
              "movida no duplicada)", ok)


def test_to_backtest_frame_es_el_mismo_objeto_tras_el_wrapper():
    ok = bias_camp.to_backtest_frame is research.to_backtest_frame
    return _p("scripts.bias_campaign.to_backtest_frame ES research.to_backtest_frame "
              "(mismo objeto, movida no duplicada)", ok)


def test_apply_bias_a_no_toco_la_rama_a_de_bias_campaign():
    """apply_bias_A es una función NUEVA y AISLADA (no un wrapper) —
    confirma que scripts.bias_campaign.apply_bias sigue siendo una
    función propia, no un re-export, precisamente porque no se tocó."""
    ok = bias_camp.apply_bias is not research.apply_bias_A
    return _p("scripts.bias_campaign.apply_bias NO fue reemplazada por un wrapper — "
              "sigue siendo su propia implementación, sin tocar (decisión deliberada, "
              "ver docstring de research/data.py)", ok)


ALL_TESTS = [
    test_equivalencia_btcusdt_2022,
    test_equivalencia_ethusdt_2023,
    test_resample_4h_es_el_mismo_objeto_tras_el_wrapper,
    test_to_backtest_frame_es_el_mismo_objeto_tras_el_wrapper,
    test_apply_bias_a_no_toco_la_rama_a_de_bias_campaign,
]


def main():
    print("research/tests/test_data_equivalence — Fase 3: research/data.py vs. scripts/ legacy\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
