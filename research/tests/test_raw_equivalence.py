"""
research/tests/test_raw_equivalence.py — Fase 5 (segundo mecanismo de
Gestión, 2026-09-02): equivalencia de `MANAGEMENT_LAYERS["Raw"]` contra
la evidencia histórica de Espacio 6.

Dos comparaciones DISTINTAS, documentadas explícitamente para no
confundirlas:

  1. Equivalencia AGREGADA (6/6 celdas): `runner.run()` vs. la fila YA
     PUBLICADA en `gestion_espacio6_raw_results.csv` — mismo patrón que
     `test_runner_equivalence.py` usa para V3-A contra
     `gestion_campaign_session_results.csv`.

  2. Equivalencia de TRADE RECORD: NO existe un CSV de trade-record
     histórico persistido de Raw (verificado en la auditoría de Fase 5 —
     el script legacy calculaba `trades` solo en memoria, nunca lo
     exportó). La comparación acá es:

         runner.run(..., include_trades=True) -> TradeRecord canónico
     vs.
         backtest.run_config(...) con EXIT_CFG_RAW -> TradeRecord fresco,
         re-derivado por la ruta 100% legacy, EN EL MISMO PROCESO

     — no contra un artefacto histórico persistido (no existe), sino
     entre dos ejecuciones deterministas del mismo mecanismo por rutas
     de código distintas (runner vs. legacy), sobre el mismo dataset.

Ejecutar:
    python -m research.tests.test_raw_equivalence  (o con pytest)
"""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")
import backtest
import research
from research import runner
from research.schema import TradeRecord

_REF_PATH = "gestion_espacio6_raw_results.csv"
_COMPARE_FIELDS = ("n_entries", "n_trades", "pf", "wr", "exp_r", "total_r", "max_dd", "freq")

_CANONICAL_GATES = {
    "pf_min": research.PF_MIN, "max_dd_min": research.MAX_DD_MIN,
    "exp_r_min": research.EXP_R_MIN, "freq_min": research.FREQ_MIN_PER_MONTH,
    "freq_max": research.FREQ_MAX_PER_MONTH,
}


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _build_contract(asset: str, year: int, role: str = "train") -> dict:
    return {
        "name": f"raw_equivalence_{asset}_{year}", "contract_version": "1", "assets": [asset],
        "years": {role: year}, "bias": {"name": "A_ema200_neutral", "params": {}},
        "trigger": {"name": "T1_ema_cross", "params": {}}, "entry": {"name": "C_market_close", "params": {}},
        "session": "dcv1_activo_15h", "management": {"name": "Raw", "params": {}},
        "risk": 0.005, "cost_per_trade": 0.0009, "max_hold": 20, "atr_mult": 1.5,
        "gates": dict(_CANONICAL_GATES), "independent_variable": "management.name",
        "blind_authorized": False,
    }


def _load_reference_row(asset: str, year: int) -> pd.Series:
    df = pd.read_csv(_REF_PATH)
    match = df[(df["asset"] == asset) & (df["year"] == year)]
    if match.empty:
        raise AssertionError(f"No se encontró fila de referencia para {asset}/{year} en {_REF_PATH}.")
    return match.iloc[0]


def _assert_equivalencia_agregada_exacta(asset: str, year: int) -> None:
    contract = _build_contract(asset, year)
    result = runner.run(contract)
    ref = _load_reference_row(asset, year)

    mismatches = []
    for field_name in _COMPARE_FIELDS:
        got = getattr(result, field_name)
        expected = ref[field_name]
        if float(got) != float(expected):
            mismatches.append(f"{field_name}: runner={got!r} vs referencia legacy={expected!r}")
    if mismatches:
        raise AssertionError(
            f"Equivalencia Raw runner vs legacy FALLÓ para {asset}/{year}:\n  " + "\n  ".join(mismatches)
        )


# --------------------------------------------------------------------------- #
# 1. Equivalencia agregada, 6/6 celdas de gestion_espacio6_raw_results.csv   #
# --------------------------------------------------------------------------- #
def _make_test(asset: str, year: int):
    def _test():
        ok = True
        try:
            _assert_equivalencia_agregada_exacta(asset, year)
        except AssertionError as e:
            ok = False
            print(f"    {e}")
        return _p(f"research.runner.run(management=Raw) reproduce EXACTO (sin redondeo) la "
                  f"fila legacy {asset}/{year} de {_REF_PATH}: n_entries/n_trades/pf/wr/"
                  f"exp_r/total_r/max_dd/freq", ok)
    _test.__name__ = f"test_raw_equivalencia_exacta_{asset.lower()}_{year}"
    return _test


test_raw_equivalencia_exacta_btcusdt_2022 = _make_test("BTCUSDT", 2022)
test_raw_equivalencia_exacta_btcusdt_2023 = _make_test("BTCUSDT", 2023)
test_raw_equivalencia_exacta_ethusdt_2022 = _make_test("ETHUSDT", 2022)
test_raw_equivalencia_exacta_ethusdt_2023 = _make_test("ETHUSDT", 2023)
test_raw_equivalencia_exacta_solusdt_2022 = _make_test("SOLUSDT", 2022)
test_raw_equivalencia_exacta_solusdt_2023 = _make_test("SOLUSDT", 2023)


# --------------------------------------------------------------------------- #
# 2. TradeRecord: runner canónico vs. ruta legacy fresca (mismo proceso)    #
# --------------------------------------------------------------------------- #
def test_raw_trade_record_runner_vs_legacy_fresco():
    """NO compara contra un artefacto histórico (no existe, ver docstring
    del módulo) — compara dos ejecuciones deterministas EN ESTE MISMO
    PROCESO: runner.run(include_trades=True) vs. backtest.run_config(...)
    con EXIT_CFG_RAW invocado directamente (ruta 100% legacy)."""
    asset, year = "ETHUSDT", 2023
    contract = _build_contract(asset, year)
    result, trade_records = runner.run(contract, include_trades=True)

    # Ruta legacy fresca, SIN pasar por el runner en absoluto:
    df_full = research.load_asset_year(asset, year)
    cfg = backtest.Config(atr_mult=1.5, atr_period=14, max_hold=20, risk=0.005,
                           sessions=runner.SESSION_WINDOWS["dcv1_activo_15h"])
    frame = research.to_backtest_frame(df_full, df_full["bias_A"], cfg)
    entries = backtest.find_entries(frame, cfg)
    orig_cost = backtest.COST_PER_TRADE
    backtest.COST_PER_TRADE = 0.0009
    try:
        trades_legacy = backtest.run_config(frame, entries, research.EXIT_CONFIGS["Raw"], cfg)
    finally:
        backtest.COST_PER_TRADE = orig_cost

    entry_by_time = {frame.index[e["entry_idx"]]: e for e in entries}
    legacy_records = [
        TradeRecord.from_raw(row.to_dict(), mechanism="Raw",
                              entry_price=(entry_by_time.get(row["entry_time"]) or {}).get("entry"))
        for _, row in trades_legacy.iterrows()
    ]

    ok = (
        len(trade_records) == len(legacy_records) == result.n_trades
        and trade_records == legacy_records
    )
    if not ok:
        print(f"    runner n_trades={len(trade_records)}, legacy n_trades={len(legacy_records)}")
        for i, (a, b) in enumerate(zip(trade_records, legacy_records)):
            if a != b:
                print(f"    trade {i} difiere: runner={a} legacy={b}")
                break

    return _p(f"TradeRecords de Raw ({asset}/{year}, {len(trade_records)} trades): "
              f"runner.run(include_trades=True) vs. ruta legacy fresca (backtest.run_config "
              f"+ research.EXIT_CONFIGS['Raw']) — IDÉNTICOS campo por campo, en el mismo proceso", ok)


def test_raw_trade_records_sin_exit_price_sin_fabricar():
    """exit_price NO lo produce simulate_v3 (ni para V3-A ni para Raw) —
    debe quedar None, nunca fabricado, también para Raw."""
    contract = _build_contract("BTCUSDT", 2022)
    _, trade_records = runner.run(contract, include_trades=True)
    ok = len(trade_records) > 0 and all(tr.exit_price is None for tr in trade_records)
    return _p(f"Los {len(trade_records)} TradeRecords de Raw tienen exit_price=None "
              f"(no producido por simulate_v3, no fabricado)", ok)


def test_raw_trade_records_entry_price_derivado():
    """entry_price SÍ está disponible (derivado del join contra entries)
    para Raw, igual que para V3-A."""
    contract = _build_contract("BTCUSDT", 2022)
    _, trade_records = runner.run(contract, include_trades=True)
    ok = len(trade_records) > 0 and all(tr.entry_price is not None for tr in trade_records)
    return _p(f"Los {len(trade_records)} TradeRecords de Raw tienen entry_price poblado "
              f"(derivado determinísticamente vía join contra entries)", ok)


ALL_TESTS = [
    test_raw_equivalencia_exacta_btcusdt_2022,
    test_raw_equivalencia_exacta_btcusdt_2023,
    test_raw_equivalencia_exacta_ethusdt_2022,
    test_raw_equivalencia_exacta_ethusdt_2023,
    test_raw_equivalencia_exacta_solusdt_2022,
    test_raw_equivalencia_exacta_solusdt_2023,
    test_raw_trade_record_runner_vs_legacy_fresco,
    test_raw_trade_records_sin_exit_price_sin_fabricar,
    test_raw_trade_records_entry_price_derivado,
]


def main():
    print("research/tests/test_raw_equivalence — Fase 5: equivalencia de MANAGEMENT_LAYERS['Raw']\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
