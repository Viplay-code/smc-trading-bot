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
)

__all__ = [
    "BiasFn",
    "TriggerFn",
    "EntryFn",
    "TriggerEvent",
    "EntrySignal",
    "BIAS_LAYERS",
    "TRIGGER_LAYERS",
    "ENTRY_LAYERS",
]
