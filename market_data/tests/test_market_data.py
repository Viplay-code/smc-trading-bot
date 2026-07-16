"""market_data — Tests offline (Fase A). Ejecutar:
python -m market_data.tests.test_market_data (o con pytest).

Sin red real: un cliente falso (MagicMock) sustituye a binance.client.Client
en todos los casos; storage/downloader se prueban contra un directorio
temporal, nunca contra data/raw/ real.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as ReqConnectionError

from market_data import (
    FETCHER_VERSION,
    download_all,
    download_asset,
    fetch_klines,
    manifest_path,
    raw_path,
    read_manifest,
    write_manifest,
    write_raw_csv,
    year_window,
    years_in_range,
)
from market_data.config import KLINE_COLUMNS

# Fila cruda "tal cual Binance" — mezcla de int/str, usada en varios tests.
SAMPLE_ROW = [
    1640995200000, "46000.00", "46500.00", "45900.00", "46200.00", "120.5",
    1640998799999, "5555555.5", 1000, "60.0", "2777777.7", "0",
]


def _p(name: str, ok: bool) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _fake_api_exception(status_code: int, retry_after: float | None = None) -> BinanceAPIException:
    """Construye un BinanceAPIException con la forma real que arma la
    librería (status_code + response.headers), sin golpear la red."""
    response = MagicMock()
    response.status_code = status_code
    response.text = '{"code": -1, "msg": "err"}'
    response.headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return BinanceAPIException(response, status_code, response.text)


# --------------------------------------------------------------------------- #
# config — years_in_range / year_window                                       #
# --------------------------------------------------------------------------- #
def test_years_in_range_derives_from_dates():
    ok = years_in_range("2022-01-01", "2025-01-01") == [2022, 2023, 2024]
    assert ok, "años derivados incorrectos"
    return _p("years_in_range deriva años del rango, nada hardcodeado", ok)


def test_years_in_range_rejects_bad_order():
    try:
        years_in_range("2025-01-01", "2022-01-01")
        ok = False
    except ValueError:
        ok = True
    assert ok, "debió fallar con end_date <= start_date"
    return _p("years_in_range falla fuerte si end_date <= start_date", ok)


def test_year_window_applies_buffer_days():
    start, end = year_window(2022, buffer_days=90, start_date="2022-01-01", end_date="2025-01-01")
    ok = start == "2021-10-03" and end == "2023-01-01"
    assert ok, f"ventana inesperada: {(start, end)}"
    return _p("year_window aplica el buffer y corta en el próximo año", ok)


def test_year_window_clips_last_year_to_end_date():
    _, end = year_window(2024, buffer_days=90, start_date="2022-01-01", end_date="2025-01-01")
    ok = end == "2025-01-01"
    assert ok, f"fin inesperado: {end}"
    return _p("year_window recorta el último año a END_DATE", ok)


def test_year_window_rejects_year_out_of_range():
    try:
        year_window(2020, start_date="2022-01-01", end_date="2025-01-01")
        ok = False
    except ValueError:
        ok = True
    assert ok, "debió fallar fail-fast para un año fuera de rango"
    return _p("year_window rechaza fail-fast un año fuera del rango configurado", ok)


# --------------------------------------------------------------------------- #
# client — fetch_klines / retry / rate-limit                                  #
# --------------------------------------------------------------------------- #
def test_fetch_klines_calls_client_with_expected_args():
    client = MagicMock()
    client.futures_historical_klines.return_value = [SAMPLE_ROW]
    rows = fetch_klines(client, "BTCUSDT", "1h", "2022-01-01", "2022-01-02")
    ok = rows == [SAMPLE_ROW]
    client.futures_historical_klines.assert_called_once_with(
        "BTCUSDT", "1h", "2022-01-01", "2022-01-02"
    )
    assert ok, "fetch_klines no retornó las filas del cliente"
    return _p("fetch_klines llama al cliente con los argumentos esperados", ok)


def test_fetch_klines_honors_retry_after_on_429():
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise _fake_api_exception(429, retry_after=7)
        return [SAMPLE_ROW]

    client = MagicMock()
    client.futures_historical_klines.side_effect = side_effect
    sleeps: list[float] = []
    rows = fetch_klines(client, "BTCUSDT", "1h", "2022-01-01", "2022-01-02",
                        sleep_fn=sleeps.append)
    ok = rows == [SAMPLE_ROW] and sleeps == [7.0]
    assert ok, f"esperaba sleeps=[7.0], obtuve {sleeps}"
    return _p("429 con Retry-After: respeta el header (no backoff exponencial)", ok)


def test_fetch_klines_backoff_on_transient_network_error():
    calls = {"n": 0}

    def side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ReqConnectionError("boom")
        return [SAMPLE_ROW]

    client = MagicMock()
    client.futures_historical_klines.side_effect = side_effect
    sleeps: list[float] = []
    rows = fetch_klines(client, "ETHUSDT", "1h", "2022-01-01", "2022-01-02",
                        sleep_fn=sleeps.append, backoff_base=1.0, backoff_max=10.0)
    ok = rows == [SAMPLE_ROW] and sleeps == [1.0, 2.0]
    assert ok, f"esperaba backoff [1.0, 2.0], obtuve {sleeps}"
    return _p("error de red transitorio: backoff exponencial acotado", ok)


def test_fetch_klines_no_retry_on_non_transient_error():
    client = MagicMock()
    client.futures_historical_klines.side_effect = _fake_api_exception(400)
    sleeps: list[float] = []
    try:
        fetch_klines(client, "SOLUSDT", "1h", "2022-01-01", "2022-01-02", sleep_fn=sleeps.append)
        ok = False
    except BinanceAPIException:
        ok = client.futures_historical_klines.call_count == 1 and sleeps == []
    assert ok, "un 400 no debe reintentarse"
    return _p("400 no transitorio: falla de inmediato, sin reintentar", ok)


def test_fetch_klines_raises_after_max_retries():
    client = MagicMock()
    client.futures_historical_klines.side_effect = _fake_api_exception(500)
    sleeps: list[float] = []
    try:
        fetch_klines(client, "BTCUSDT", "1h", "2022-01-01", "2022-01-02",
                     sleep_fn=sleeps.append, max_retries=3, backoff_base=0.1, backoff_max=1.0)
        ok = False
    except BinanceAPIException:
        ok = client.futures_historical_klines.call_count == 3 and len(sleeps) == 2
    assert ok, "debió agotar exactamente max_retries intentos"
    return _p("500 persistente: agota max_retries y propaga la excepción", ok)


# --------------------------------------------------------------------------- #
# storage — paths / CSV / manifest                                            #
# --------------------------------------------------------------------------- #
def test_raw_path_and_manifest_path_naming_convention():
    with tempfile.TemporaryDirectory() as tmp:
        p = raw_path("BTCUSDT", "1h", 2022, raw_dir=tmp)
        m = manifest_path("BTCUSDT", "1h", 2022, raw_dir=tmp)
        ok = (p == Path(tmp) / "BTCUSDT_1h_2022.csv"
             and m == Path(tmp) / "BTCUSDT_1h_2022.manifest.json")
    assert ok, f"rutas inesperadas: {p}, {m}"
    return _p("convención de ruta data/raw/{symbol}_{interval}_{year}", ok)


def test_write_raw_csv_preserves_all_12_columns_no_coercion():
    with tempfile.TemporaryDirectory() as tmp:
        p = raw_path("BTCUSDT", "1h", 2022, raw_dir=tmp)
        n = write_raw_csv([SAMPLE_ROW], p)
        lines = p.read_text(encoding="utf-8").splitlines()
        header = lines[0].split(",")
        row = lines[1].split(",")
        ok = (n == 1 and header == list(KLINE_COLUMNS)
             and row == [str(v) for v in SAMPLE_ROW])
    assert ok, f"CSV inesperado: header={header}, row={row}"
    return _p("write_raw_csv escribe las 12 columnas nativas sin coerción", ok)


def test_write_raw_csv_does_not_dedup_or_validate():
    dup_row = list(SAMPLE_ROW)  # duplicado exacto, a propósito
    impossible_row = [  # OHLC imposible (high < low), a propósito
        1640998800000, "46200.00", "1.00", "99999.00", "46300.00", "80.0",
        1641002399999, "3000000.0", 500, "40.0", "1500000.0", "0",
    ]
    rows = [SAMPLE_ROW, dup_row, impossible_row]
    with tempfile.TemporaryDirectory() as tmp:
        p = raw_path("BTCUSDT", "1h", 2022, raw_dir=tmp)
        n = write_raw_csv(rows, p)
        lines = p.read_text(encoding="utf-8").splitlines()
        ok = n == 3 and len(lines) == 4  # header + 3 filas, ninguna filtrada
    assert ok, "storage no debe filtrar duplicados ni OHLC imposible (es de dc_v1)"
    return _p("storage no dedupica ni valida sanity (límite frente a dc_v1)", ok)


def test_manifest_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        m = manifest_path("BTCUSDT", "1h", 2022, raw_dir=tmp)
        write_manifest(m, symbol="BTCUSDT", interval="1h", year=2022,
                       start="2021-10-03", end="2023-01-01", row_count=3,
                       fetcher_version=FETCHER_VERSION,
                       fetched_at="2026-01-01T00:00:00+00:00")
        data = read_manifest(m)
        ok = (data["symbol"] == "BTCUSDT" and data["row_count"] == 3
             and data["fetcher_version"] == FETCHER_VERSION
             and data["fetched_at"] == "2026-01-01T00:00:00+00:00")
    assert ok, f"manifest inesperado: {data}"
    return _p("manifest hace round-trip completo (write_manifest + read_manifest)", ok)


# --------------------------------------------------------------------------- #
# downloader — orquestación                                                   #
# --------------------------------------------------------------------------- #
def test_download_asset_orchestrates_fetch_write_manifest():
    client = MagicMock()
    client.futures_historical_klines.return_value = [SAMPLE_ROW]
    with tempfile.TemporaryDirectory() as tmp:
        path = download_asset(client, "BTCUSDT", 2022, raw_dir=tmp)
        manifest = read_manifest(manifest_path("BTCUSDT", "1h", 2022, raw_dir=tmp))
        ok = (path.exists() and manifest["row_count"] == 1
             and manifest["start"] == "2021-10-03" and manifest["end"] == "2023-01-01")
    assert ok, f"download_asset no produjo el CSV/manifest esperado: {manifest}"
    return _p("download_asset orquesta fetch + CSV + manifest coherentes", ok)


def test_download_asset_rejects_year_out_of_range():
    client = MagicMock()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            download_asset(client, "BTCUSDT", 2020, raw_dir=tmp)
            ok = False
        except ValueError:
            ok = not client.futures_historical_klines.called
    assert ok, "no debió llamar a Binance para un año fuera de rango"
    return _p("download_asset falla fail-fast antes de llamar a Binance", ok)


def test_download_all_uses_years_in_range_by_default():
    client = MagicMock()
    client.futures_historical_klines.return_value = [SAMPLE_ROW]
    with tempfile.TemporaryDirectory() as tmp:
        paths = download_all(client, assets=("BTCUSDT",), raw_dir=tmp,
                             pace_sleep_fn=lambda _s: None)
        years = sorted(int(p.stem.split("_")[-1]) for p in paths)
    ok = years == [2022, 2023, 2024]
    assert ok, f"años inesperados: {years}"
    return _p("download_all deriva los años de years_in_range() por defecto", ok)


def test_download_all_year_major_order():
    calls: list[str] = []

    def side_effect(symbol, _interval, _start, _end):
        calls.append(symbol)
        return [SAMPLE_ROW]

    client = MagicMock()
    client.futures_historical_klines.side_effect = side_effect
    with tempfile.TemporaryDirectory() as tmp:
        download_all(client, assets=("BTCUSDT", "ETHUSDT", "SOLUSDT"), years=[2022, 2023],
                     raw_dir=tmp, pace_sleep_fn=lambda _s: None)
    expected = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
    ok = calls == expected
    assert ok, f"orden inesperado: {calls}"
    return _p("download_all recorre en orden año-mayor (período completo primero)", ok)


def test_download_all_paces_between_downloads_not_after_last():
    client = MagicMock()
    client.futures_historical_klines.return_value = [SAMPLE_ROW]
    paces: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        download_all(client, assets=("BTCUSDT", "ETHUSDT"), years=[2022], raw_dir=tmp,
                     pace_sleep_fn=paces.append, request_sleep_seconds=0.5)
    ok = paces == [0.5]  # 2 jobs -> 1 sola pausa, nunca tras la última
    assert ok, f"pacing inesperado: {paces}"
    return _p("download_all pausa entre descargas, nunca tras la última", ok)


# --------------------------------------------------------------------------- #
# __init__ — punto de entrada público                                         #
# --------------------------------------------------------------------------- #
def test_fetcher_version_importable_from_public_entrypoint():
    ok = isinstance(FETCHER_VERSION, str) and len(FETCHER_VERSION) > 0
    assert ok, "FETCHER_VERSION debe ser un string no vacío importable desde market_data"
    return _p("FETCHER_VERSION importable desde market_data (no desde .config)", ok)


ALL_TESTS = [
    test_years_in_range_derives_from_dates,
    test_years_in_range_rejects_bad_order,
    test_year_window_applies_buffer_days,
    test_year_window_clips_last_year_to_end_date,
    test_year_window_rejects_year_out_of_range,
    test_fetch_klines_calls_client_with_expected_args,
    test_fetch_klines_honors_retry_after_on_429,
    test_fetch_klines_backoff_on_transient_network_error,
    test_fetch_klines_no_retry_on_non_transient_error,
    test_fetch_klines_raises_after_max_retries,
    test_raw_path_and_manifest_path_naming_convention,
    test_write_raw_csv_preserves_all_12_columns_no_coercion,
    test_write_raw_csv_does_not_dedup_or_validate,
    test_manifest_round_trip,
    test_download_asset_orchestrates_fetch_write_manifest,
    test_download_asset_rejects_year_out_of_range,
    test_download_all_uses_years_in_range_by_default,
    test_download_all_year_major_order,
    test_download_all_paces_between_downloads_not_after_last,
    test_fetcher_version_importable_from_public_entrypoint,
]


def main():
    print("market_data — suite de verificación offline\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
