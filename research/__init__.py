"""research — Motor de señales unificado (Fase C3, TARGET_ARCHITECTURE.md §4.1).

Punto de entrada público único (regla de dependencias §2 de
TARGET_ARCHITECTURE.md): otros componentes importan solo desde acá, nunca desde
`research.layers` directamente.
"""
from .layers import (
    BiasFn,
    TriggerFn,
    EntryFn,
    TriggerEvent,
    EntrySignal,
    BIAS_LAYERS,
    TRIGGER_LAYERS,
    ENTRY_LAYERS,
    bias_A2_ema200_neutral_1h_held,
)
from .metrics import (
    compute_core_metrics,
    gate_check,
    PF_MIN,
    MAX_DD_MIN,
    EXP_R_MIN,
    FREQ_MIN_PER_MONTH,
    FREQ_MAX_PER_MONTH,
)
from .schema import ExperimentResult, TradeRecord, compute_contract_hash
from .data import load_asset_year, resample_4h, to_backtest_frame, apply_bias_A
from .simulate import simulate_v3, EXIT_CONFIGS
from .entries import find_entries, ENTRY_META_REQUIREMENTS
from .expand import expand_universe, MAX_UNIVERSE_CELLS

__all__ = [
    "BiasFn",
    "TriggerFn",
    "EntryFn",
    "TriggerEvent",
    "EntrySignal",
    "BIAS_LAYERS",
    "TRIGGER_LAYERS",
    "ENTRY_LAYERS",
    "compute_core_metrics",
    "bias_A2_ema200_neutral_1h_held",
    "gate_check",
    "PF_MIN",
    "MAX_DD_MIN",
    "EXP_R_MIN",
    "FREQ_MIN_PER_MONTH",
    "FREQ_MAX_PER_MONTH",
    "ExperimentResult",
    "TradeRecord",
    "compute_contract_hash",
    "load_asset_year",
    "resample_4h",
    "to_backtest_frame",
    "apply_bias_A",
    "simulate_v3",
    "EXIT_CONFIGS",
    "find_entries",
    "ENTRY_META_REQUIREMENTS",
    "expand_universe",
    "MAX_UNIVERSE_CELLS",
]
