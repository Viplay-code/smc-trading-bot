# DC-v1 — Precisiones de Implementación
# Gobernanza: D-003 | Estado: Aprobado | Relación: complementa DC-v1 (no lo reemplaza)

Estas precisiones cierran ambigüedades detectadas en revisión técnica que producirían
resultados divergentes **sin lanzar error** — el modo de fallo que el blind set 2024
no perdona. Ninguna altera la arquitectura; fijan convenciones y añaden asserts.

Aprobadas: P-1, P-2, P-3, P-4, P-5, P-7, P-8.
P-6 resuelto por decisión del Research Director (conservar dominio ternario).
P-7: pin recomendado, **pendiente de ratificación** de librería/parámetros.

---

## P-1 — Convención temporal de la barra 1H
- `timestamp = apertura de la barra` (Binance klines = open-time).
- Regla de admisibilidad: en la fila `t` solo es lícita información **completada hasta
  el inicio de `t`**. Nada que cierre dentro de `[t, t+1h)`.
- El índice es tz-aware UTC (nunca naive).

## P-2 — Join HTF 4H→1H (sin lookahead, sin doble lag)
Secuencia canónica:
1. Resample de la serie **cruda continua** a 4H con `label='left', closed='left'`.
2. EMA200 sobre los cierres 4H (continua — ver P-3).
3. `shift(1)` sobre el frame 4H → cada fila pasa a portar la 4H **anterior completada**.
4. Unir a 1H con `merge_asof(direction='backward')` keyeado por el *inicio* de barra.

Verificación del alineamiento (por qué no hay lookahead ni doble lag):
- Fila 4H etiquetada `00:00` cubre `[00:00, 04:00)`, cierra a las `04:00`.
- Tras `shift(1)`, esa fila porta la barra `[prev, 00:00)` que cerró a las `00:00` → disponible.
- Para 1H en `[00:00, 04:00)`, `merge_asof` backward toma esa fila → última 4H completada. ✔
- Sin `shift(1)` se tomaría la 4H en formación → **lookahead**.
- Con etiqueta a la derecha + `shift(1)` se tomaría `B_{k-2}` → **lag oculto de 4h**.

**Test unitario obligatorio (garantía #1 verificada, no solo afirmada):**
armar 5–6 barras 4H a mano y comprobar que `htf_close_prev` en la primera 1H de cada
ventana corresponde exactamente a la 4H anterior. Sin este test, la garantía es una
afirmación.

## P-3 — Cómputo continuo, luego slice (protección del blind set)
- Todas las derivadas (ema50, atr14, htf_ema200, htf_*) se calculan sobre la **serie
  cruda continua**, y el particionado por período (2022 / 2023 / 2024) se hace **después**.
- Regla: una derivada puede sembrarse desde barras crudas **pasadas** cruzando fronteras
  de período (es pasado → legítimo); **nunca** desde futuras.
- Consecuencia: 2024 no pierde ~33 días de warmup (dominado por EMA200 4H) y sus valores
  de indicador son idénticos a los de producción. Calcular dentro de cada slice mutila el
  blind set y cambia los valores — prohibido.

## P-4 — Persistencia de `df.attrs`
- `df.attrs` es experimental y se pierde en `merge`/`concat` según versión de pandas.
  El propio pipeline hace un merge (P-2), y `asset` + los tres `*_version` viven ahí.
- Mitigación: **re-estampar** `attrs` (asset, contract_version, dataset_version,
  pipeline_version) después de **cada etapa** que pueda descartarlos, en especial el merge.
- El validador **assertea** presencia de los cuatro en el **punto de consumo**, no solo
  al crear el DataFrame. La regla "declarar contract_version" no puede leer un dict vacío.

## P-5 — Columna de warmup dominante para el trim
- El trim **no** lo fija ema50 (50) ni atr14 (14): lo fija `htf_ema200_prev`
  (200 barras 4H ≈ 800 barras 1H).
- Regla: `trim = primera fila donde la columna obligatoria de mayor warmup es válida`.
- Con P-3 (continuo→slice), la historia pre-período alimenta la EMA200 y el trim solo
  muerde el arranque global de la serie cruda, no el de cada período.

## P-6 — `htf_bias`: derivación oficial (decisión de gobernanza)
- **Dominio conservado `{+1, -1, 0}` (int8)** por estabilidad semántica y compatibilidad
  con una futura zona neutral. Hoy `0` = igualdad exacta de floats (medida cero, ~inalcanzable).
- **Única fuente de verdad**: una función compartida, importada por pipeline y validador.
  Prohibido transcribir la fórmula dos veces.

```python
import numpy as np
import pandas as pd

def derive_htf_bias(htf_close_prev: pd.Series, htf_ema200_prev: pd.Series) -> pd.Series:
    """Derivación OFICIAL de htf_bias (DC-v1). Dominio {+1,-1,0} int8.
    0 = igualdad exacta (reservado). Requiere inputs sin NaN (post-trim)."""
    if htf_close_prev.isna().any() or htf_ema200_prev.isna().any():
        raise ValueError("htf_bias: NaN en _prev — derivar después del trim de warmup")
    diff = htf_close_prev.to_numpy() - htf_ema200_prev.to_numpy()  # float64
    return pd.Series(np.sign(diff).astype(np.int8),
                     index=htf_close_prev.index, name="htf_bias")
```

- **`np.sign`, no `np.where`**: `np.where(c>e,1,np.where(c<e,-1,0))` mapea NaN→0 en
  silencio (comparaciones con NaN son False). `np.sign` propaga NaN y el guard lo caza.
- Orden de resta fijado `(close_prev − ema200_prev)`. Todo float64.
- Assert del validador: `(df.htf_bias == derive_htf_bias(df.htf_close_prev, df.htf_ema200_prev)).all()`.
- Derivar un bias alternativo desde columnas `_prev` sigue requiriendo decisión de
  gobernanza propia (DC-v1, regla 3).

## P-7 — Pin de indicadores (PENDIENTE DE RATIFICACIÓN)
Registrar en `pipeline_version` no *previene* la divergencia; hay que nombrar librería +
parámetros para que el esquema 3×3 sea determinista y no dependa de disciplina manual.

Pin **recomendado**:
- **EMA** (ema50, htf_ema200): recursiva `adjust=False`, semilla = SMA de las primeras N.
  Convención TA-Lib / TradingView (coherente con el diseño de T4).
- **ATR14**: suavizado de Wilder (RMA) sobre True Range, período 14.
- **Librería**: TA-Lib para ambos. Fallback pandas-ta con parámetros idénticos **solo si**
  se verifica igualdad numérica.

> Estado: a la espera de "confirmo TA-Lib / uso X" del Research Director.

## P-8 — `session`
- Ventanas por **horas UTC fijas** (declaradas; sin DST, por reproducibilidad).
  Un mapeo sobre hora local con DST estaría mal dos veces al año.
- Dtype **explícito**: `pd.CategoricalDtype(['london','ny','overlap','off'])`.
  Un `.astype('category')` sin dtype fijo produce categorías distintas por período si
  alguno nunca ve `overlap` → el `concat`/comparación de los 9 datasets degrada a object
  y rompe "esquema idéntico".

---

## Higiene pandas (notas de implementación)
- Frecuencias en minúscula: `'h'` / `'4h'` (mayúsculas deprecadas en pandas 2.2+, ruptura en 3.0).
- Fijar `label`/`closed` explícitos en todo resample (no confiar en defaults).
- Validaciones de entrada (antes de todo): `index.is_monotonic_increasing`,
  `index.is_unique`, `index.tz is not None`; **dedup** de klines duplicadas de Binance
  en fronteras de paginación.
- Sanity OHLC: `high >= max(open,close)`, `low <= min(open,close)`, `high >= low`.
- El índice **no** es una grilla completa (hay gaps en `attrs['gaps']`): nada de
  `asfreq('1h')` ni asumir `.freq`. `merge_asof` lo maneja; un reindex introduciría NaN.

## Asserts del validador (consolidado)
1. Índice: tz-aware UTC, monótono creciente, único.
2. Dtypes exactos por columna (incl. `session` = CategoricalDtype fijo, `htf_bias` = int8).
3. Sin NaN en obligatorias; trim = columna de mayor warmup (P-5).
4. `contract_version`, `dataset_version`, `pipeline_version`, `asset` presentes en attrs
   **en el punto de consumo** (P-4).
5. `htf_bias == derive_htf_bias(...)` (P-6).
6. Sanity OHLC (P-8/higiene).
7. Categorías de `session` == set fijo (P-8).
8. Test unitario de no-lookahead del join HTF con ejemplo a mano (P-2).
