"""DC-v1 — Research Engine Input pipeline (Gobernanza D-003)."""
from .indicators import (
    CONTRACT_VERSION,
    ema,
    atr,
    derive_htf_bias,
    assert_equivalence_pandas_ta,
)
from .pipeline import (
    build_dc_v1,
    prepare_raw,
    detect_gaps,
    add_1h_derivatives,
    add_htf,
    trim_warmup,
    add_session,
    add_htf_bias,
    stamp_attrs,
    SESSION_DTYPE,
)
from .validator import validate_dc_v1

__all__ = [
    "CONTRACT_VERSION",
    "ema",
    "atr",
    "derive_htf_bias",
    "assert_equivalence_pandas_ta",
    "build_dc_v1",
    "prepare_raw",
    "detect_gaps",
    "add_1h_derivatives",
    "add_htf",
    "trim_warmup",
    "add_session",
    "add_htf_bias",
    "stamp_attrs",
    "SESSION_DTYPE",
    "validate_dc_v1",
]
