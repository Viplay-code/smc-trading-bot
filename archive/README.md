# archive/

Herramientas y artefactos que ya cumplieron su propósito dentro del
proyecto y quedaron fuera del flujo activo — se conservan por su valor
documental (qué se probó, qué informó, por qué), no porque formen parte
de algo que se siga ejecutando.

No es lo mismo que un script "de debug puntual pero vigente" (como
`scripts/inspect_single_dataset.py`, que sí se puede volver a correr con
sentido hoy) — lo que entra acá ya no tiene un rol en el sistema actual
ni en el roadmap de corto plazo, aunque podría reincorporarse si en algún
momento existe la pieza de arquitectura que le daría un lugar de nuevo.

Cada archivo movido acá debe traer, en su propio docstring o en un
comentario inicial, al menos:
- su propósito original;
- qué problema resolvía y si ese problema sigue vigente o ya se resolvió
  de otra forma;
- por qué quedó fuera del flujo activo (no reproducible, sin
  consumidores, esquema no canónico, etc. — la razón concreta, no una
  genérica);
- bajo qué condición tendría sentido reincorporarlo, si alguna.

Preservar siempre el historial de git al mover algo acá (`git mv`, nunca
copiar y borrar el original).

## Contenido

- `analisis_mfe_mae.py` + `t1_trades_multiasset.csv` (archivados
  2026-07-22, Iniciativa F del backlog post-Fase-B): herramienta de
  tamizado de parámetros de trailing por aproximación MFE. Ver el
  docstring del propio script para el detalle completo.
