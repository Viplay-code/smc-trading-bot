#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""versions.py — Fuente ÚNICA de las versiones que sellan cada dataset DC-v1.

Todos los consumidores (inspect_single_dataset, gate-runner, EXP-07) importan
de aquí, de modo que el gate "mismo pipeline_version en los 9 datasets" se
cumpla por construcción y nadie duplique literales dispersos.

Fuente canónica (parche de integración D-004):
  - build_dc_v1 RECIBE dataset_version/pipeline_version como parámetros
    —confirmado por inspect_dc_v1_contract—; no los define internamente. No
    existía, por tanto, una fuente previa: se define aquí, ahora.
  - PIPELINE_VERSION identifica la lógica de transformación. Valor adoptado del
    nombre del contrato (Data Contract DC-v1), no un literal arbitrario.
  - DATASET_VERSION se ata a market_data.FETCHER_VERSION (el productor del
    crudo), dando trazabilidad raw→transformado sin duplicar el string.

AJUSTE ÚNICO: si tu suite dc_v1/tests ya pasa un pipeline_version con otra
nomenclatura y la prefieres, cambia SOLO la línea de PIPELINE_VERSION aquí —
todos los consumidores la heredan. Es inocuo para el gate: éste exige que los 9
compartan valor, y todos lo toman de este módulo. (`grep -rn "build_dc_v1(" \
dc_v1/tests/` confirma qué usa tu suite, si quieres alinear nomenclatura.)
"""
from market_data import FETCHER_VERSION

PIPELINE_VERSION = "dc-v1"           # versión de la lógica de transformación
DATASET_VERSION = FETCHER_VERSION    # productor del crudo (trazabilidad raw→transformado)