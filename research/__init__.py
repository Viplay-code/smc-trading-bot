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
from .metrics import compute_core_metrics

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
]
