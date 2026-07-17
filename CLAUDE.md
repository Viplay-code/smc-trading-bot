# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Assumptions

Never assume repository structure.

Verify it first.

Never invent:

- project structure
- modules
- constants
- file names
- project conventions

Always verify them in the repository first.

If something cannot be verified, explicitly state that it is unknown.

## What this repo is

An SMC (Smart Money Concepts) crypto futures trading bot for Binance, currently in the
research/validation phase (no live capital yet). There are two layers of code at very
different levels of rigor — know which one you're touching:

1. **Legacy/exploratory scripts** at the repo root (`bot.py`, `backtest.py`,
   `analisis_mfe_mae.py`) — a first-pass liquidity-sweep + BOS + pullback strategy with
   inline EMA/ATR math, used to explore the idea and drive the live paper-trading loop.
2. **DC-v1 (`dc_v1/`)** — a formally governed data pipeline ("Data Contract v1") that
   produces the canonical "Research Engine Input" DataFrame used for rigorous
   backtesting/validation. This is the direction the project is moving toward; new
   research logic should consume `dc_v1` output rather than reimplementing indicators.

Read `FRAMEWORK.md` first for the validation methodology, and
`DC-v1_Precisiones_Implementacion.md` before touching anything in `dc_v1/`.

## Commands

```bash
pip install -r requirements.txt        # pandas, numpy, python-binance
```

`dc_v1/indicators.py` imports `talib` (the TA-Lib Python binding), which is **not** in
`requirements.txt` and is not installed in this environment. Anything importing `dc_v1`
transitively requires it — install the TA-Lib C library first, then `pip install TA-Lib`.
The inspection scripts in `scripts/` were deliberately written to use `ast` parsing
instead of importing `dc_v1`, specifically to work without TA-Lib available.

```bash
# DC-v1 test suite (custom runner, also pytest-discoverable — functions are test_*)
python -m dc_v1.tests.test_dc_v1
pytest dc_v1/tests/test_dc_v1.py -v

# Backtest the legacy strategy (downloads public Binance data, no API key needed)
python backtest.py

# Live/paper trading loop (requires BINANCE_API_KEY / BINANCE_API_SECRET env vars)
python bot.py

# Inspect the DC-v1 contract without importing dc_v1 (no TA-Lib needed)
python scripts/inspect_dc_v1_contract.py

# Inspect one real dataset end-to-end (requires TA-Lib + a raw CSV under data/raw/)
python scripts/inspect_single_dataset.py
```

There is no lint/format tooling configured in this repo.

## Architecture

### Legacy strategy (`bot.py`, `backtest.py`)

Liquidity Sweep → BOS (break of structure) → 50% pullback entry, filtered by EMA200 on
the 4H timeframe, traded only during London (07-11 UTC) and New York (13-17 UTC)
sessions, one position per asset at a time.

- `bot.py`: live loop against `python-binance`'s `Client` (testnet by default,
  `paper_trade=True` simulates fills without sending orders). State machine per iteration:
  check open position → check pending pullback setup → look for a new sweep+BOS setup.
  Config is a single `@dataclass Config` with all strategy constants.
- `backtest.py`: implements the "V3" bar-by-bar exit management (break-even, then ATR-
  distance trailing stop, then timeout-at-market), simulated conservatively — each bar
  first tests the *existing* stop against the adverse extreme (`low`/`high`) before any
  favorable-move update can move the stop, so intrabar movement never protects itself
  within the same bar. Two exit variants (V3-A, V3-B) are run side-by-side per asset/
  period for comparison; `passes()` encodes the same accept/reject gate as `FRAMEWORK.md`.

### DC-v1 pipeline (`dc_v1/`)

A strict, order-dependent build process producing one contract-conformant DataFrame per
asset, governed by the numbered precisions (P-1..P-8) in
`DC-v1_Precisiones_Implementacion.md`. The point of DC-v1 is to make a class of bugs that
*don't throw* (lookahead, double-lag, silent NaN→0 coercion) structurally impossible or
loud. When modifying this pipeline, the precisions doc is the spec — don't "fix" a stage
without checking whether it's encoding a deliberate anti-lookahead invariant.

Pipeline stages (`pipeline.py`, orchestrated by `build_dc_v1()`), each independently
testable:
1. `prepare_raw` — normalize columns/dtypes, enforce tz-aware UTC monotonic unique index,
   dedup (keep last) on Binance pagination-boundary duplicate klines, OHLC sanity asserts.
2. `add_1h_derivatives` — `ema50`/`atr14` computed on the **continuous** raw series
   (never per-period-sliced — see P-3, this is what preserves blind-set warmup).
3. `add_htf` — resamples to 4H (`label='left', closed='left'`), computes EMA200 on 4H
   closes, `shift(1)`s the 4H frame so each slot carries the *previous completed* 4H bar,
   then `merge_asof(direction='backward')` onto the 1H index. This exact sequence is what
   avoids both lookahead (using an in-formation 4H bar) and a hidden extra 4H of lag.
4. `trim_warmup` — trims to the first row where all obligatory columns are valid; the
   binding column is always `htf_ema200_prev` (200×4H ≈ 800×1H bars), not `ema50`/`atr14`.
5. `add_session` — DST-free, UTC-hour-only session classification (`london`/`overlap`/
   `ny`/`off`) with a fixed `CategoricalDtype` so all datasets share identical categories.
6. `add_htf_bias` — derives `{-1, 0, +1}` (int8) via `np.sign`, never `np.where` (which
   would silently map NaN comparisons to `0` and corrupt the bias — see `indicators.py`).
7. `stamp_attrs` — (re-)stamps `contract_version`/`dataset_version`/`pipeline_version`/
   `asset` into `df.attrs`; must be re-applied after `add_htf`'s merge, which drops attrs.

`indicators.py` is the **single source of truth** for `ema`, `atr`, and `derive_htf_bias`
— both `pipeline.py` and `validator.py` import from here; the formulas must never be
transcribed a second time anywhere else. EMA/ATR are pinned to TA-Lib (recursive EMA
seeded with SMA, Wilder-smoothed ATR) specifically so the 3×3 asset×period grid is
numerically deterministic across environments.

`validator.py` (`validate_dc_v1`) is the contract check at the *consumption* point (not
just at construction) — collects all violations and reports them together rather than
failing on the first. Checks: attrs present, index shape, exact dtypes per column
(including `session`'s fixed categories and `htf_bias`'s int8), no NaN in obligatory
columns, OHLC sanity, and that `htf_bias` matches a fresh call to `derive_htf_bias` on the
same data (guards against the two ever drifting apart).

### Supporting modules

- `periods.py` — the single place that slices a DC-v1 output to a research period
  (`[Y-01-01, (Y+1)-01-01)`, half-open on open-time). Every consumer must use
  `period_slice()` rather than re-deriving the cutoff, since DC-v1 output carries warmup
  buffer that would otherwise let adjacent periods leak into each other (e.g. December
  bleeding across the in-sample/validation boundary).
- `versions.py` — single source for `PIPELINE_VERSION`/`DATASET_VERSION` so the "same
  pipeline_version across all 9 datasets" gate holds by construction. It imports
  `FETCHER_VERSION` from `market_data`'s public entry point (`market_data/__init__.py`),
  not from the `market_data.config` submodule directly.

## Validation methodology (see `FRAMEWORK.md`)

Three-period discipline is load-bearing, not a suggestion:

- **2022** in-sample (parameter selection), **2023** validation (variant selection),
  **2024** blind test (final go/no-go) — parameters are chosen using 2022 data only, and
  2024 is not to be inspected until a winning variant is already locked in. `dc_v1`'s
  continuous-then-slice computation (P-3) and `periods.py`'s half-open slicing exist
  specifically to protect this from being violated silently.
- A strategy variant is only valid if it clears ALL of: Profit Factor ≥ 1.50, max
  drawdown ≤ -10%, positive expectancy after costs, and 6-12 trades/month/asset. Among
  variants clearing all four, rank by Profit Factor — a higher-PF variant that fails any
  gate is disqualified outright, no exceptions.
- Cost model: 0.09% per trade (0.04% Binance Futures maker commission round-trip + 0.05%
  slippage), applied to every simulated trade before computing metrics.
