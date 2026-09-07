"""
research/tests/test_persistence_legacy_compat.py — Automatización
experimental, Componente 6 (Persistence / Artifacts, 2026-09-04):
evidencia de compatibilidad contra CSV legacy REALES ya publicados
(`gestion_campaign_session_results.csv`/`gestion_campaign_session_decision.csv`,
mismo dataset ancla usado en C1/C5).

NO es un contrato de igualdad byte-a-byte contra el formato legacy —
C6 define deliberadamente un esquema canónico distinto y mejor (ver
docstring de `research/persistence.py`: el artifact `decision` no aplana
años/roles en columnas fijas, a diferencia de
`gestion_campaign_session_decision.csv`). Este test demuestra que el
artifact nuevo contiene la información EQUIVALENTE necesaria, no que
reproduce el formato antiguo.

Ejecutar:
    python -m research.tests.test_persistence_legacy_compat  (o con pytest)
"""
from __future__ import annotations

import io
import csv
import sys

import pandas as pd

sys.path.insert(0, ".")
from research.decision import summarize_decision
from research.persistence import (
    render_experiment_csv, render_decision_csv, to_experiment_rows, to_decision_rows,
)
from research.schema import ExperimentResult

_RESULTS_PATH = "gestion_campaign_session_results.csv"
_DECISION_PATH = "gestion_campaign_session_decision.csv"
_YEAR_TO_ROLE = {2022: "train", 2023: "validate"}


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _load_real_results() -> list[ExperimentResult]:
    df = pd.read_csv(_RESULTS_PATH)
    out = []
    for _, row in df.iterrows():
        out.append(ExperimentResult(
            experiment_name="gestion_campaign_session", asset=row["asset"],
            period=int(row["year"]), period_role=_YEAR_TO_ROLE[int(row["year"])],
            bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
            session=row["candidate"], management=row["exit_config"],
            n_entries=int(row["n_entries"]), n_trades=int(row["n_trades"]),
            pf=row["pf"], wr=row["wr"], exp_r=row["exp_r"], total_r=row["total_r"],
            max_dd=row["max_dd"], freq=row["freq"], gate_pass=bool(row["gate_pass"]),
        ))
    return out


def test_artifact_results_contiene_toda_la_informacion_del_csv_legacy():
    """Cada celda (asset, session, exit_config, year) del CSV legacy real
    tiene una fila correspondiente en el artifact results nuevo, con los
    mismos valores de pf/n_entries/n_trades/gate_pass."""
    results = _load_real_results()
    rows = to_experiment_rows(results)
    legacy = pd.read_csv(_RESULTS_PATH)

    ok = len(rows) == len(legacy)
    mismatches = 0
    for row, (_, legacy_row) in zip(rows, legacy.iterrows()):
        if (row["asset"] != legacy_row["asset"] or row["session"] != legacy_row["candidate"]
                or row["management"] != legacy_row["exit_config"]
                or row["n_entries"] != legacy_row["n_entries"]
                or row["n_trades"] != legacy_row["n_trades"]
                or row["pf"] != legacy_row["pf"]
                or row["gate_pass"] != bool(legacy_row["gate_pass"])):
            mismatches += 1
    ok = ok and mismatches == 0
    return _p(f"El artifact results (36 filas) contiene, sin pérdida, la misma "
              f"información de asset/session/exit_config/n_entries/n_trades/pf/gate_pass "
              f"que {_RESULTS_PATH}", ok)


def test_artifact_decision_contiene_la_supervivencia_y_ranking_equivalentes():
    """El artifact decision (nuevo esquema) contiene la misma información
    de supervivencia/ranking que gestion_campaign_session_decision.csv
    (legacy) -- ya verificado exhaustivamente campo por campo en
    test_decision_equivalence.py; acá se confirma que PERSISTIRLO no
    pierde ni altera esa información."""
    results = _load_real_results()
    decisions = summarize_decision(
        results, candidate_fields=("session", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    rows = to_decision_rows(decisions, candidate_fields=("session", "management"))
    legacy = pd.read_csv(_DECISION_PATH)

    ok = len(rows) == len(legacy)
    mismatches = 0
    for row, (_, legacy_row) in zip(rows, legacy.iterrows()):
        legacy_rank = None if pd.isna(legacy_row["rank_within_asset"]) else int(legacy_row["rank_within_asset"])
        if (row["asset"] != legacy_row["asset"] or row["session"] != legacy_row["candidate"]
                or row["management"] != legacy_row["exit_config"]
                or row["survives_required_roles"] != bool(legacy_row["survives_both_years"])
                or row["rank_within_asset"] != legacy_rank):
            mismatches += 1
    ok = ok and mismatches == 0
    return _p(f"El artifact decision (18 filas, esquema nuevo sin pf_2022/pf_2023 "
              f"embebidos) contiene la misma supervivencia y ranking que "
              f"{_DECISION_PATH} — información equivalente, esquema deliberadamente distinto", ok)


def test_diferencia_de_esquema_documentada_explicitamente():
    """Confirma la diferencia de esquema declarada: el CSV legacy SÍ tiene
    columnas pf_2022/pf_2023 embebidas; el artifact decision nuevo NO las
    tiene (esa información vive en el artifact results, no se pierde,
    solo cambia de archivo)."""
    legacy_cols = set(pd.read_csv(_DECISION_PATH).columns)
    decision_text = render_decision_csv(
        summarize_decision(
            _load_real_results(), candidate_fields=("session", "management"),
            required_roles=("train", "validate"), rank_by_role="validate",
        ),
        candidate_fields=("session", "management"),
    )
    new_cols = set(next(csv.reader(io.StringIO(decision_text))))

    ok = (
        "pf_2022" in legacy_cols and "pf_2023" in legacy_cols
        and "pf_2022" not in new_cols and "pf_2023" not in new_cols
        and new_cols == {"asset", "session", "management", "survives_required_roles", "rank_within_asset"}
    )
    return _p(f"Diferencia de esquema confirmada: legacy embebe pf_2022/pf_2023 en decision.csv "
              f"({sorted(legacy_cols)}); el artifact nuevo no lo hace ({sorted(new_cols)}) — "
              f"esa métrica vive en el artifact results, no se pierde", ok)


def test_reconstruccion_de_pf_por_rol_desde_el_artifact_results():
    """La información de pf_2022/pf_2023 que legacy embebía en decision.csv
    sigue siendo recuperable -- desde el artifact results, filtrando por
    (asset, session, exit_config, period_role)."""
    results = _load_real_results()
    rows = to_experiment_rows(results)

    target_row = next(r for r in rows if r["asset"] == "BTCUSDT" and r["session"] == "control_8h"
                       and r["management"] == "V3-A (1R/2R/1R)" and r["period_role"] == "train")
    legacy = pd.read_csv(_DECISION_PATH)
    legacy_row = legacy[(legacy["asset"] == "BTCUSDT") & (legacy["candidate"] == "control_8h")
                         & (legacy["exit_config"] == "V3-A (1R/2R/1R)")].iloc[0]

    ok = target_row["pf"] == legacy_row["pf_2022"]
    return _p("pf del rol 'train' reconstruido desde el artifact results coincide con "
              "pf_2022 del decision.csv legacy — la información no se perdió, solo cambió de archivo", ok)


ALL_TESTS = [
    test_artifact_results_contiene_toda_la_informacion_del_csv_legacy,
    test_artifact_decision_contiene_la_supervivencia_y_ranking_equivalentes,
    test_diferencia_de_esquema_documentada_explicitamente,
    test_reconstruccion_de_pf_por_rol_desde_el_artifact_results,
]


def main():
    print("research/tests/test_persistence_legacy_compat — Componente 6, evidencia contra "
          "CSV legacy reales\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
