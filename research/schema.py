"""research/schema.py — Esquema canónico de resultados y de trade record
(Fase 1 de la infraestructura de `research/runner.py`, 2026-09-02).

`research/runner.py` NO EXISTE TODAVÍA — este módulo es preparación previa,
autorizada explícitamente como Fase 1, no la implementación del runner. No
lo consume ningún script legacy; es infraestructura nueva, aislada, sin
efecto sobre ningún flujo existente hasta que algo la importe deliberadamente.

Dos formas distintas, no intercambiables:

  - `ExperimentResult`: una fila = una CELDA experimental (un activo, bajo
    un período, con un contrato declarado). Es lo que hoy exporta cada
    `results_to_frame()` de cada script de campaña, con nombres de columna
    ligeramente distintos en cada uno — acá se fija un esquema único.
  - `TradeRecord`: una fila = un TRADE individual dentro de una celda. Es lo
    que hoy devuelve `backtest.simulate_v3`/sus variantes estructurales
    (`simulate_tp_fixed`, `simulate_v3_tp`) como `dict`, con campos que
    varían según el mecanismo (`exit_price` presente en algunos, ausente en
    otros).

Principio de "sin fabricación" (obligatorio en ambos): un campo que un
mecanismo de Gestión o una campaña no produce queda `None` — NUNCA se
reconstruye, estima, ni infiere acá. `TradeRecord.from_raw()` es explícito
sobre esto: usa `dict.get(campo)` (default `None`), nunca un cálculo
derivado que el `dict` de origen no tenía.

No se resuelve acá ningún registro de mecanismos de Gestión (`MANAGEMENT_
LAYERS` de la Parte 1.10 del diseño de `runner.py`) — ese trabajo queda
para una fase posterior, explícitamente fuera de esta Fase 1.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd


# --------------------------------------------------------------------------- #
# ExperimentResult — una fila por celda (activo × período bajo un contrato). #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExperimentResult:
    """Fila canónica de resultado de una celda experimental.

    Campos obligatorios: los mínimos declarados en el diseño aprobado de
    `research/runner.py` (Parte 2), sin default — un `ExperimentResult` sin
    identificar su experimento/contrato/activo/período no es válido por
    construcción del propio dataclass (TypeError si falta alguno).

    Campos opcionales (`gate_pass`, `contract_hash`): no estaban en la lista
    mínima explícita, pero se derivan naturalmente de lo que ya existe
    (`research.gate_check`) o de la infraestructura de identificación de
    contrato — quedan con default `None`, nunca fabricados si no se proveen.
    """
    experiment_name: str
    asset: str
    period: int                # año: 2022 / 2023 / 2024
    period_role: str           # "train" | "validate" | "blind" — explícito, nunca inferido por posición
    bias: str
    trigger: str
    entry: str
    session: str
    management: str
    n_entries: int
    n_trades: int
    pf: float | None
    wr: float | None
    exp_r: float | None
    total_r: float | None
    max_dd: float | None
    freq: float | None
    gate_pass: bool | None = None
    contract_hash: str | None = None

    @classmethod
    def from_metrics(
        cls, *, experiment_name: str, asset: str, period: int, period_role: str,
        bias: str, trigger: str, entry: str, session: str, management: str,
        n_entries: int, n_trades: int, metrics: dict | None,
        gate_pass: bool | None = None, contract_hash: str | None = None,
    ) -> "ExperimentResult":
        """Construye la fila desde el `dict` de métricas que ya produce
        `backtest.metrics()`/`research.compute_core_metrics()` — sin
        fabricar ningún campo: si `metrics` es `None` (muestra insuficiente,
        `n_trades<5`), pf/wr/exp_r/total_r/max_dd/freq quedan `None`
        genuinamente, no en 0 ni en ningún valor centinela."""
        m = metrics or {}
        return cls(
            experiment_name=experiment_name, asset=asset, period=period,
            period_role=period_role, bias=bias, trigger=trigger, entry=entry,
            session=session, management=management,
            n_entries=n_entries, n_trades=n_trades,
            pf=m.get("pf"), wr=m.get("wr"), exp_r=m.get("exp_r"),
            total_r=m.get("total_r"), max_dd=m.get("max_dd"), freq=m.get("freq"),
            gate_pass=gate_pass, contract_hash=contract_hash,
        )


# --------------------------------------------------------------------------- #
# TradeRecord — una fila por trade individual.                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TradeRecord:
    """Fila canónica de un trade individual.

    Campos obligatorios: los que `backtest.simulate_v3` y TODAS sus
    variantes estructurales ya verificadas (`simulate_tp_fixed` de E1,
    `simulate_v3_tp` de V3-A+TP, el propio `simulate_v3` reutilizado sin
    modificar en E2/Raw) producen sin excepción — verificado por inspección
    de las 4 funciones antes de fijar este esquema (ver auditoría de Fase 0,
    turno anterior).

    Campos opcionales (default `None`, NUNCA fabricados):
      - `exit_price`: presente en `simulate_tp_fixed`/`simulate_v3_tp`;
        AUSENTE en `simulate_v3` (no lo devuelve — verificado en código,
        `backtest.py:229-236`).
      - `entry_price`: NINGÚN mecanismo actual lo devuelve en el dict de
        trade — solo vive en la lista `entries` (`entry["entry"]`), fuera
        del trade en sí. Reconstruirlo requiere un join externo por
        `entry_time` contra `entries` (mismo patrón ya usado en los
        diagnósticos de Espacio 6) — este dataclass NO lo hace por sí solo.
      - `mechanism`: nombre del mecanismo de Gestión que produjo el trade,
        para trazabilidad si se combinan trades de varias campañas — no lo
        produce ningún `simulate_*` (es contexto externo a la simulación).
    """
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str              # "long" | "short"
    reason: str                 # "stop" | "tp" | "timeout" | ...
    pnl_r: float                # neto de costos
    duration_h: int
    exit_price: float | None = None
    entry_price: float | None = None
    mechanism: str | None = None

    @classmethod
    def from_raw(cls, raw: dict, *, mechanism: str | None = None,
                 entry_price: float | None = None) -> "TradeRecord":
        """Construye un TradeRecord desde el `dict` crudo que devuelve
        `simulate_v3`/una de sus variantes estructurales — usa `.get()`
        para los campos opcionales (default `None`), nunca calcula o
        infiere un valor que `raw` no tenía. `entry_price` se acepta como
        parámetro separado porque ningún `simulate_*` lo incluye en su
        `dict` de salida (ver docstring de la clase) — quien invoque este
        constructor y quiera poblarlo debe emparejarlo explícitamente
        desde `entries` por `entry_time`, no se hace acá de forma
        implícita."""
        return cls(
            entry_time=raw["entry_time"], exit_time=raw["exit_time"],
            direction=raw["direction"], reason=raw["reason"], pnl_r=raw["pnl_r"],
            duration_h=raw["duration_h"], exit_price=raw.get("exit_price"),
            entry_price=entry_price, mechanism=mechanism,
        )


# --------------------------------------------------------------------------- #
# contract_hash — interfaz mínima, deliberadamente genérica.                 #
#                                                                              #
# El formato exacto del contrato experimental (Parte 2 del diseño de         #
# runner.py) todavía no está implementado ni congelado — esta función NO      #
# asume ninguna forma específica de ese contrato, solo que sea un dict        #
# JSON-serializable. Cuando el contrato real se fije (Fase 2+), esta misma    #
# función sigue siendo válida sin cambios, porque no depende de sus campos.   #
# --------------------------------------------------------------------------- #
def compute_contract_hash(contract: dict[str, Any]) -> str:
    """Hash determinista (sha256, primeros 16 hex) de un contrato
    experimental serializable a JSON. `sort_keys=True` garantiza que el
    mismo contrato produce el mismo hash sin importar el orden de
    inserción de sus claves. Determinista entre corridas (no usa nada
    dependiente de tiempo/entorno/orden de iteración de sets)."""
    canonical = json.dumps(contract, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
