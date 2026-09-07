"""
research/tests/test_decision_equivalence.py — Automatización experimental,
Componente 5 (capa de Decisión, 2026-09-04): equivalencia EXACTA contra
`scripts/bias_campaign.py::summarize_decision` legacy, sobre un dataset
REAL ya publicado (`gestion_campaign_session_results.csv`/
`gestion_campaign_session_decision.csv`, 36 filas: 3 activos x 3 ventanas
de sesión x 2 configs de salida x 2 años — mismo dataset ya usado como
ancla de equivalencia del runner en `test_runner_equivalence.py`).

DIFERENCIA SEMÁNTICA DOCUMENTADA (no oculta, ver docstring de
`research/decision.py`): legacy identifica los 2 años requeridos por su
valor LITERAL (2022/2023); la versión generalizada usa
`ExperimentResult.period_role` ("train"/"validate") — necesario para no
hardcodear ningún año (instrucción explícita del diseño de este
componente). Sobre el dataset real de este test, el mapeo es exacto
(2022->"train", 2023->"validate"), así que el comportamiento resultante es
IDÉNTICO — verificado acá campo por campo, no asumido.

Nota sobre el dataset elegido: las 36 combinaciones de
`gestion_campaign_session_results.csv` NO tienen ningún sobreviviente real
(`gate_pass=False` en las 72 filas por año — consistente con el hallazgo
ya cerrado de Espacio 6/auditoría transversal: 0/532 celdas sobreviven
ambos años en todo el programa). Esto significa que este test de
equivalencia cubre rigurosamente supervivencia, candidatos descartados,
determinismo y orden — pero NO ejercita el ranking con sobrevivientes
reales (`rank_within_asset` siempre `NaN`/`None` en este dataset
concreto). El ranking con sobrevivientes se verifica por separado, con
datos sintéticos, en `test_ranking_con_sobrevivientes_sinteticos` de este
mismo archivo (mismo patrón ya usado en el resto de `research/tests/` para
separar equivalencia-contra-dato-real de verificación-de-mecanismo).

Ejecutar:
    python -m research.tests.test_decision_equivalence  (o con pytest)
"""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")
from research.decision import summarize_decision, CandidateDecision
from research.schema import ExperimentResult

_RESULTS_PATH = "gestion_campaign_session_results.csv"
_DECISION_PATH = "gestion_campaign_session_decision.csv"

_YEAR_TO_ROLE = {2022: "train", 2023: "validate"}


def _p(name, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return ok


def _load_real_results_as_experimentresults() -> list[ExperimentResult]:
    """Reconstruye ExperimentResult a partir del CSV real ya publicado.
    bias/trigger/entry fijos según el propio docstring de
    scripts/gestion_campaign_session.py (Bias=A, Trigger=T1_ema_cross,
    Entry=C_market_close, fijos durante toda la campaña) — no inventados,
    documentados en el script de origen. 'candidate' (ventana de sesión)
    se mapea a ExperimentResult.session; 'exit_config' se mapea a
    ExperimentResult.management (identifica el mecanismo de salida, mismo
    rol que jugaba como segunda dimensión de agrupación en legacy)."""
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


def test_equivalencia_exacta_supervivencia_y_orden():
    """Compara, fila por fila, el output de summarize_decision (generalizado)
    contra gestion_campaign_session_decision.csv (legacy, ya publicado):
    mismo orden, misma supervivencia, mismo pf por rol, mismo rank
    (NaN/None en las 18 filas, ya que ningún candidato sobrevive en este
    dataset real)."""
    results = _load_real_results_as_experimentresults()
    out = summarize_decision(
        results, candidate_fields=("session", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )

    legacy = pd.read_csv(_DECISION_PATH)

    ok = len(out) == len(legacy)
    if not ok:
        return _p(f"equivalencia: longitud distinta (generalizado={len(out)}, "
                  f"legacy={len(legacy)})", False)

    mismatches = []
    for i, (decision, legacy_row) in enumerate(zip(out, legacy.itertuples(index=False))):
        session, management = decision.candidate
        if decision.asset != legacy_row.asset:
            mismatches.append(f"fila {i}: asset {decision.asset!r} != {legacy_row.asset!r}")
        if session != legacy_row.candidate:
            mismatches.append(f"fila {i}: session {session!r} != candidate legacy {legacy_row.candidate!r}")
        if management != legacy_row.exit_config:
            mismatches.append(f"fila {i}: management {management!r} != exit_config legacy {legacy_row.exit_config!r}")
        if decision.survives_required_roles != bool(legacy_row.survives_both_years):
            mismatches.append(f"fila {i}: survives {decision.survives_required_roles} != "
                              f"legacy {legacy_row.survives_both_years}")
        legacy_rank = None if pd.isna(legacy_row.rank_within_asset) else int(legacy_row.rank_within_asset)
        if decision.rank_within_asset != legacy_rank:
            mismatches.append(f"fila {i}: rank {decision.rank_within_asset!r} != legacy {legacy_rank!r}")
        pf_train = decision.per_role["train"].pf if "train" in decision.per_role else None
        pf_validate = decision.per_role["validate"].pf if "validate" in decision.per_role else None
        if pf_train != legacy_row.pf_2022:
            mismatches.append(f"fila {i}: pf(train) {pf_train!r} != pf_2022 legacy {legacy_row.pf_2022!r}")
        if pf_validate != legacy_row.pf_2023:
            mismatches.append(f"fila {i}: pf(validate) {pf_validate!r} != pf_2023 legacy {legacy_row.pf_2023!r}")

    ok = not mismatches
    if mismatches:
        print(f"    {len(mismatches)} discrepancias (mostrando hasta 5):")
        for m in mismatches[:5]:
            print(f"      {m}")
    return _p(f"summarize_decision generalizado reproduce EXACTO (orden, supervivencia, "
              f"pf por rol, rank) las {len(legacy)} filas de {_DECISION_PATH}", ok)


def test_ningun_sobreviviente_en_el_dataset_real():
    """Chequeo de cordura explícito: confirma que este dataset real
    efectivamente no tiene sobrevivientes (consistente con el cierre de
    Espacio 6) — si esto cambiara, la comparación de arriba dejaría de ser
    representativa y habría que revisarla."""
    results = _load_real_results_as_experimentresults()
    out = summarize_decision(
        results, candidate_fields=("session", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    ok = not any(c.survives_required_roles for c in out)
    return _p("Confirmado: 0 sobrevivientes en gestion_campaign_session (consistente con "
              "el cierre de Espacio 6 — 0/532 celdas sobreviven ambos años en el programa)", ok)


def test_ranking_con_sobrevivientes_sinteticos():
    """El dataset real no tiene sobrevivientes (ver docstring del módulo)
    — se verifica el ranking con datos SINTÉTICOS, estructuralmente
    equivalentes al mecanismo de summarize_decision legacy (rankear por
    pf del año/rol de validación, descendente, dentro del mismo activo),
    sin ninguna pretensión de que estos números representen un resultado
    científico real."""
    results = [
        ExperimentResult(
            experiment_name="synthetic", asset="BTCUSDT", period=2022, period_role="train",
            bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
            session="control_8h", management="V3-A (1R/2R/1R)",
            n_entries=60, n_trades=58, pf=1.55, wr=45.0, exp_r=0.12, total_r=6.0,
            max_dd=-6.0, freq=8.0, gate_pass=True,
        ),
        ExperimentResult(
            experiment_name="synthetic", asset="BTCUSDT", period=2023, period_role="validate",
            bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
            session="control_8h", management="V3-A (1R/2R/1R)",
            n_entries=58, n_trades=56, pf=1.70, wr=47.0, exp_r=0.15, total_r=7.0,
            max_dd=-5.5, freq=7.8, gate_pass=True,
        ),
        ExperimentResult(
            experiment_name="synthetic", asset="BTCUSDT", period=2022, period_role="train",
            bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
            session="dcv1_activo_15h", management="V3-A (1R/2R/1R)",
            n_entries=110, n_trades=105, pf=1.60, wr=44.0, exp_r=0.10, total_r=9.0,
            max_dd=-7.0, freq=9.0, gate_pass=True,
        ),
        ExperimentResult(
            experiment_name="synthetic", asset="BTCUSDT", period=2023, period_role="validate",
            bias="A_ema200_neutral", trigger="T1_ema_cross", entry="C_market_close",
            session="dcv1_activo_15h", management="V3-A (1R/2R/1R)",
            n_entries=108, n_trades=104, pf=2.10, wr=48.0, exp_r=0.20, total_r=12.0,
            max_dd=-6.0, freq=8.5, gate_pass=True,
        ),
    ]
    out = summarize_decision(
        results, candidate_fields=("session", "management"),
        required_roles=("train", "validate"), rank_by_role="validate",
    )
    survivors = sorted([c for c in out if c.survives_required_roles], key=lambda c: c.rank_within_asset)
    ok = (
        len(survivors) == 2
        and survivors[0].candidate == ("dcv1_activo_15h", "V3-A (1R/2R/1R)")  # pf validate 2.10
        and survivors[1].candidate == ("control_8h", "V3-A (1R/2R/1R)")       # pf validate 1.70
        and survivors[0].rank_within_asset == 1
        and survivors[1].rank_within_asset == 2
    )
    return _p("Ranking con 2 sobrevivientes sintéticos: dcv1_activo_15h (pf=2.10) "
              "rankea antes que control_8h (pf=1.70) en 'validate' — mismo mecanismo "
              "de ranking que summarize_decision legacy (descendente por pf)", ok)


ALL_TESTS = [
    test_equivalencia_exacta_supervivencia_y_orden,
    test_ningun_sobreviviente_en_el_dataset_real,
    test_ranking_con_sobrevivientes_sinteticos,
]


def main():
    print("research/tests/test_decision_equivalence — Componente 5, equivalencia contra "
          "summarize_decision legacy\n")
    results = [t() for t in ALL_TESTS]
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} tests OK")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
