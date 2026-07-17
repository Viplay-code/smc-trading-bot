#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_dc_v1_contract.py — Lee el contrato de dc_v1 SIN importar el paquete.

No ejecuta ningun import de dc_v1 (por tanto no toca TA-Lib): parsea el codigo
fuente con ast. Confirma D-1 en cualquier interprete, con o sin TA-Lib:
  - firma real de build_dc_v1 (y otras etapas)
  - si build_dc_v1 llama internamente a prepare_raw / demas etapas
  - como se construye el indice temporal -> tz de salida (para period_slice)

Uso (desde la raiz del repo):  python scripts/inspect_dc_v1_contract.py
"""
import ast
import pathlib

TARGETS = {"build_dc_v1", "prepare_raw", "add_htf", "trim_warmup", "add_session"}
TZ_HINTS = ("tz_localize", "tz_convert", "utc=True", "to_datetime",
            "DatetimeIndex", ".tz")

pkg = pathlib.Path("dc_v1")
if not pkg.exists():
    raise SystemExit("No se encontro dc_v1/ - ejecuta desde la raiz del repo.")

for path in sorted(pkg.glob("*.py")):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS:
            ret = ast.unparse(node.returns) if node.returns else "?"
            print(f"[{path.name}] def {node.name}({ast.unparse(node.args)}) -> {ret}")
            if node.name == "build_dc_v1":
                calls = {n.func.id for n in ast.walk(node)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                stages = sorted(calls & {"prepare_raw", "detect_gaps", "add_htf",
                                         "trim_warmup", "add_session",
                                         "add_htf_bias", "stamp_attrs"})
                print(f"          llama internamente: {stages or '-'}")
    for i, line in enumerate(src.splitlines(), 1):
        if any(h in line for h in TZ_HINTS):
            print(f"          tz? {path.name}:{i}: {line.strip()[:90]}")