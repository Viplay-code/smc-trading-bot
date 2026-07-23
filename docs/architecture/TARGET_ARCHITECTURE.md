# Arquitectura Objetivo — SMC Trading Bot

**Estado:** Referencia oficial de arquitectura (v7 — Architecture Baseline v1)
**Última revisión:** 2026-07-22

Este documento describe la arquitectura **objetivo** del proyecto — cómo debería
verse el sistema, no cómo está hoy. El estado actual y el roadmap de migración
entre ambos se documentan por separado dentro de este mismo archivo (§3 y §6).

---

## 0. Principios de gobernanza

- **La arquitectura gobierna al código.** Si el código y este documento entran
  en conflicto, el código está mal — no el documento.
- **Los cambios importantes de arquitectura se reflejan primero aquí y después
  en el código.** Agregar o eliminar un componente, cambiar la dirección de una
  dependencia, o reordenar el roadmap de migración son cambios de arquitectura:
  requieren actualizar este documento antes (o como parte del mismo cambio) de
  tocar el código. Un PR de código que contradiga este documento sin haberlo
  actualizado primero no debe aprobarse.
- Este documento se revisa con el mismo rigor que el código — cambios aquí
  también pasan por review, no se reinterpretan informalmente.

## 1. Principios de diseño

1. **Un solo camino de señal.** La lógica de estrategia que corre en backtest
   es la misma que corre en vivo. Nunca dos implementaciones paralelas.
2. **Extender antes de construir.** Si algo parecido ya existe en el repo (el
   patrón `@dataclass Config`, el registro `EXIT_CONFIGS`, el simulador
   parametrizable `simulate_v3`), se extiende — no se reemplaza por un
   framework nuevo.
3. **Contratos pequeños y explícitos entre etapas**, al estilo de `dc_v1`, sin
   gobernanza pesada donde no se necesite.
4. **Archivos versionados en vez de infraestructura**, mientras el volumen de
   datos y experimentos quepa en CSV/parquet con nombres versionados.
5. **Escalar el número de variantes o activos no debería requerir escalar el
   número de componentes** — es una fila nueva en un registro, no un
   componente nuevo.

## 2. Reglas de dependencias

- **Cada componente expone un único punto de entrada público** (su
  `__init__.py`, con exports explícitos — `dc_v1/__init__.py` ya sigue este
  patrón hoy y es el precedente a replicar). Otros componentes importan solo
  desde ese punto de entrada, nunca desde un submódulo interno.
  - Correcto: `from research import build_signal`
  - Incorrecto: `from research.layers import _internal_helper`
- **Sin imports cruzados entre módulos internos de distintos componentes.** Un
  archivo interno de `research` (ej. `research/simulate.py`) no importa
  directamente de un archivo interno de `dc_v1` (ej. `dc_v1/pipeline.py`) —
  pasa por el punto de entrada público de `dc_v1`.
- **Las dependencias solo fluyen en la dirección que define la arquitectura:**

  ```
  market_data → dc_v1 → research → bot
  ```

  Ningún componente "aguas arriba" importa de uno "aguas abajo" (`dc_v1` nunca
  importa de `research`; `research` nunca importa de `bot`). Un import que
  viole esta dirección es una señal de que la arquitectura no se está
  respetando, y se corrige el código — salvo que se abra una revisión
  explícita de este documento primero (ver §0).

---

## 3. Arquitectura actual (resumen)

- `dc_v1` ya tiene consumidores reales, pero acotados a funciones de indicador
  individuales: `dc_v1.ema()`/`dc_v1.atr()` (TA-Lib) están importadas
  directamente por `research/layers.py`, `bot.py`, y el ATR de
  `backtest.py` (Iniciativa B, backlog post-Fase-B). Lo que sigue sin
  consumidor es el **output completo del pipeline** — nadie lee el DataFrame
  "Research Engine Input" de `build_dc_v1()` todavía; `bot.py`/`backtest.py`
  siguen con su propio fetch de datos contra Binance, no contra `dc_v1`. Esa
  conexión de pipeline completo sigue siendo Fase D.
- **`bot.py` y `backtest.py` ya no tienen dos implementaciones de señal
  completamente desconectadas para Capa 2 (Trigger) y Capa 3 (Entry)** — desde
  la migración de unificación del motor de señales (2026-07-21/22), ambos
  obtienen esas dos capas de un registro único, `research/layers.py`
  (`bot.py`: `A_sweep_bos`/`A_pullback_50`; `backtest.py`: `T1_ema_cross`/
  `C_market_close`). Que usen candidatos *distintos* es intencional — son dos
  variantes separadas que `FRAMEWORK.md` define para evaluar, no una
  divergencia a corregir.
- **Capa 1 (Bias) tiene dos candidatos formalmente nombrados, no uno
  registrado y otro huérfano.** `bot.py` usa el candidato "A"
  (`bias_A_ema200_neutral`, registrado en `BIAS_LAYERS`): clasifica una vez
  por vela 4H, cierre 4H vs su propia EMA200. `backtest.py` mantiene inline
  el candidato "A2" (`bias_A2_ema200_neutral_1h_held`, portado y testeado en
  `research/layers.py` pero deliberadamente fuera de `BIAS_LAYERS`/`BiasFn`
  — su firma `(df1h, df4h)` no encaja en el contrato de una sola vela 4H):
  reclasifica cada vela 1H contra un nivel de EMA200 4H sostenido. Migrar
  cualquiera de los dos hacia el otro cambiaría señales observables de forma
  material (~15% de divergencia por fórmula, medida sobre datos sintéticos).
  La decisión de converger, mantener ambos, o diseñar un tercer candidato
  queda condicionada a validación con datos reales 2022/2023 — bloqueada en
  este momento por falta de acceso a Binance en el entorno de desarrollo
  (Iniciativa G, backlog post-Fase-B).
- **Fuente de indicadores (EMA/ATR) mayormente unificada en `dc_v1`.**
  `bias_A_ema200_neutral` y `trigger_T1_ema_cross` (`research/layers.py`),
  `bot.py::compute_ema`/`compute_atr`, y el ATR de `backtest.py::
  build_features` calculan vía `dc_v1.ema()`/`dc_v1.atr()` (TA-Lib) en vez de
  `pandas.ewm`. La única excepción deliberada es el EMA200 del candidato
  Bias "A2" de `backtest.py` — sigue en `pandas.ewm` a propósito, atada a la
  misma Iniciativa G de arriba, no a trabajo pendiente de esta unificación.
- `simulate_v3` en `backtest.py` **ya acepta una configuración de salida como
  parámetro** (`exit_cfg`) y ya corre variantes desde un diccionario
  (`EXIT_CONFIGS`) — el patrón de "registro de variantes" que necesita el
  Motor de Estrategia objetivo ya existe como precedente de estilo.
- Cuatro corridas de backtest ya generaron cuatro esquemas de CSV de trades
  **distintos entre sí** (`backtest_trades.csv`, `t1_trades_completos.csv`,
  `t1_trades_multiasset.csv`, `v3_barxbar_trades.csv`) — evidencia concreta de
  que sin un esquema canónico, cada experimento reinventa sus columnas.
- `market_data` existe y está versionado (Fase A cerrada): descarga y
  almacenamiento de OHLCV crudo vía `scripts/download_market_data.py`.
  `versions.py` importa `FETCHER_VERSION` desde su punto de entrada público y
  es importable hoy.
- `dc_v1` está conectado a datos reales (Fase B cerrada): los 9 datasets reales
  (3 activos × 2022/2023/2024) se generan y validan vía
  `scripts/build_dc_v1_datasets.py`, con `pipeline_version`/`dataset_version`
  consistentes en los 9 (`dc-v1` / `market-data-v1`). `dc_v1` ya no depende
  solo de datos sintéticos para su verificación end-to-end.

## 4. Arquitectura objetivo

### 4.1 Componentes

| Componente | Responsabilidad |
|---|---|
| **`market_data`** | Descarga y guarda OHLCV crudo versionado (`data/raw/`). Deliberadamente tonto: sin dedup, sin validación de sanity — eso es responsabilidad exclusiva de `dc_v1`. Solo Binance Futures, 1H/4H, los activos y rango ya definidos en `FRAMEWORK.md`. |
| **`dc_v1`** | Contrato de datos → "Research Engine Input". Ya construido y especificado (`DC-v1_Precisiones_Implementacion.md`). Único punto de validación de datos crudos y derivados. |
| **`research`** | Paquete único, con módulos internos: `layers.py` (registro de candidatos de capa 1/2/3 de `FRAMEWORK.md`, tipo de señal y columnas de `dc_v1` que cada capa requiere, documentadas explícitamente), `simulate.py` (gestión barra-a-barra, extraída de `simulate_v3`), `metrics.py` (métricas + gate de aceptación, consolidados), `runner.py` (orquesta el barrido de variantes × activos × períodos; produce un manifiesto de resultados con **un esquema canónico único de trade record**, fijo para todas las corridas). |
| **`bot`** | Loop en vivo, separado internamente en: cliente de exchange, máquina de estados, sizing/riesgo, y la llamada a `research` para la señal. Lee el artefacto de configuración ganadora que produce `research.runner`. Incluye circuit breaker y persistencia de estado. |

Cuatro componentes, no más — evitar que un futuro cambio agregue una quinta
caja sin pasar primero por una revisión de este documento (§0).

### 4.2 Flujo ideal

```
Binance API
   │
   ▼
market_data ──────────────► data/raw/*.csv
   │                              │
   ▼                              │
dc_v1.build_dc_v1()  ◄────────────┘
   │
   ▼
dc_v1.validate_dc_v1()        (gate de calidad de datos)
   │
   ▼
periods.period_slice()        (2022 / 2023 / 2024)
   │
   ▼
research.layers                (capa1 + capa2 + capa3 → señal)
   │  ── contrato de señal, columnas documentadas ──
   ▼
research.simulate              (gestión: BE / trailing / timeout)
   │
   ▼
research.metrics                (PF, DD, expectancy, frecuencia → gate)
   │
   ▼
research.runner                 (barrido 2022 → filtra → valida 2023 →
   │                              congela → 2024 ciego; manifiesto canónico)
   ▼
artefacto: config de variante ganadora
   │
   ▼
bot                              (mismo research.layers + circuit breaker +
                                   persistencia de estado)
```

## 5. Brecha objetivo vs. actual

| Pieza | Existe hoy | Objetivo |
|---|---|---|
| `market_data` | Sí (Fase A cerrada) | — (cerrado) |
| `dc_v1` | Sí, conectado a datos reales (Fase B cerrada) | — (cerrado) |
| Contrato de señal (columnas requeridas por capa) | No (implícito, no declarado) | Declarado en `research/layers.py` |
| Registro de capas 1/2/3 intercambiables | Parcial — Trigger y Entry ya vienen de un registro único; Bias tiene dos candidatos formalmente nombrados (A registrado en `BIAS_LAYERS`, A2 documentado fuera de él por incompatibilidad de firma), convergencia condicionada a datos reales (ver §3) | Un registro único, consumido por `research` y `bot` |
| Simulador de gestión genérico | Ya existe dentro de `backtest.py`, acoplado a una sola señal | Extraído a `research/simulate.py` |
| Métricas + Gate | Parcial — núcleo numérico (`pf`/`wr`/`exp_r`/`total_r`/`max_dd`/`be`) consolidado en `research/metrics.py::compute_core_metrics`, consumido por `backtest.py` y `archive/analisis_mfe_mae.py`; el gate de aceptación (`passes()`) sigue solo en `backtest.py`, sin consolidar | Consolidado en `research/metrics.py` |
| Esquema canónico de trade record | No — 4 esquemas distintos ya en el repo | Un esquema fijo, usado por todas las corridas |
| Experiment Runner | Manual (correr script, leer consola) | Automatizado en `research/runner.py`, con manifiesto versionado |
| Config de variante ganadora | No — hardcodeada en `bot.py` | Artefacto de salida de `research.runner`, leído por `bot` |
| Circuit breaker | Especificado en `FRAMEWORK.md`, no implementado | Implementado en `bot` |
| Persistencia de estado del bot | No — `BotState` solo en memoria | Persistido para recuperación tras crash |
| Fuente única de indicadores (EMA/ATR) | Parcial — `dc_v1.ema()`/`dc_v1.atr()` en uso en el candidato Bias "A", el trigger T1, `bot.py`, y el ATR de `backtest.py`; el EMA del candidato Bias "A2" de `backtest.py` sigue en `pandas.ewm` a propósito, atado a la Iniciativa G | Una sola fuente (`dc_v1`) para todo indicador consumido por Capa 1/2/3 |

## 6. Roadmap de migración

### 6.1 Fases

| Fase | Contenido | Depende de | Estado |
|---|---|---|---|
| **A** | `market_data`: descarga y almacenamiento versionado de OHLCV crudo | — | Cerrada |
| **B** | `dc_v1` conectado a datos reales vía `market_data`; cerrar `versions.py` | A | Cerrada — 9/9 datasets reales (3 activos × 2022/2023/2024) generados y validados vía `scripts/build_dc_v1_datasets.py`, `pipeline_version`/`dataset_version` consistentes |
| **C1** | Consolidar métricas + gate en `research/metrics.py` | — (independiente, puede empezar ya) | Parcial — núcleo numérico consolidado (Iniciativa D, `f84217e`); gate de aceptación (`passes()`) sigue solo en `backtest.py`, sin consolidar |
| **C2** | Extraer el simulador de gestión a `research/simulate.py`, probado primero contra la ruta de datos legacy que ya funciona hoy | — (independiente de A/B) | Pendiente |
| **C3** | Construir `research/layers.py` (registro de capas + contrato de señal + esquema canónico de trade record) | — (independiente de A/B) | Parcial — registro de capas construido, Trigger+Entry consumidos por ambos; Bias con dos candidatos formalizados (A/A2) pendientes de reconciliación con datos reales (Iniciativa G, ver §3); esquema canónico de trade record aún no |
| **D** | `research/runner.py`: barrido completo 2022→2023→2024 con disciplina de blind set | A, B, C1, C2, C3 | Pendiente |
| **E** | Artefacto de configuración ganadora + refactor de `bot` (separación interna + circuit breaker + persistencia) | D | Pendiente |
| **F** | Paper trading operativo endurecido (monitoreo del circuit breaker en producción) | E | Pendiente |

C1/C2/C3 no dependían de datos reales ni del contrato `dc_v1` para su
desarrollo inicial (se validaban contra la ruta de datos legacy). Con A y B
ya cerradas, ya pueden re-apuntarse a los datasets reales de `dc_v1` en vez de
validarse solo contra la ruta legacy. Solo D requiere que A y B estén
cerradas, porque es el punto donde los resultados dejan de ser exploratorios
y empiezan a informar decisiones reales sobre qué variante operar.

La reconciliación de Bias (Iniciativa G, candidatos A/A2) no bloquea el
desarrollo estructural de la Fase D — el experiment runner puede
construirse y barrer variantes de Capa 2/3 sin que G esté resuelta. Es,
sin embargo, una dependencia parcial de *cierre*: declarar una variante
ganadora con confianza plena requiere que la elección de Bias detrás de
esa variante ya esté validada con datos reales, no solo estructuralmente.

### 6.2 Dependencias entre fases

```
Fase A (market_data) ──► Fase B (dc_v1 + datos reales) ──┐
                                                          │
Fase C1 (métricas/gate)   ──────────────────────────────┤
Fase C2 (simulador, extraído, probado con datos legacy) ─┤──► Fase D (experiment runner)
Fase C3 (registro de capas + contrato de señal)     ─────┘         │
                                                                     ▼
                                                          Fase E (config ganadora + bot refactor)
                                                                     │
                                                                     ▼
                                                          Fase F (paper trading endurecido)
```

## 7. Qué NO construir todavía

- Soporte multi-exchange en `market_data` — solo Binance Futures.
- Una capa de abstracción de estrategia "genérica para cualquier framework
  futuro" — solo lo necesario para las combinaciones ya enumeradas en
  `FRAMEWORK.md` (3×4×4).
- Base de datos relacional/documental para trades o resultados — archivos
  versionados alcanzan al volumen actual.
- Dashboard/UI de monitoreo.
- Alertas externas (Slack/Telegram/email) — tiene sentido recién en la Fase F,
  no antes.
- Re-optimización automática de parámetros cuando el circuit breaker se
  dispara — `FRAMEWORK.md` exige revalidación manual explícita; automatizarlo
  violaría esa regla de gobernanza.
- Paralelización/distribución del Experiment Runner — el tamaño de la
  búsqueda corre cómodamente en una sola máquina.
- Ejecución con capital real — condicionada, según `README.md`, a 4+ semanas
  de paper trading positivo *después* de que exista una variante ganadora de
  la Fase D/E.
- Carga dinámica de plugins, auto-discovery de candidatos de capa, o un
  lenguaje de configuración (YAML/DSL) para el registro de `research/layers.py`
  — un dict de funciones de Python cubre el conjunto finito y ya enumerado de
  candidatos.

## 8. Riesgos

- **Contaminación del blind set (2024).** Mitigado por el cómputo
  continuo-luego-slice de `dc_v1` (P-3) y por `periods.period_slice()`, pero
  el Experiment Runner (Fase D) debe además separar explícitamente el acceso a
  2024 (ej. requerir una invocación separada tras congelar la variante
  ganadora de 2023), no solo confiar en la disciplina manual.
- **Circuit breaker mal calibrado.** Debe probarse contra el histórico
  2022-2023 antes de operar en paper trading (Fase F), para no disparar
  demasiado tarde o demasiado pronto.
- **Riesgo de que la extracción (Fase C2) se convierta en reescritura.** El
  objetivo de C2 es desacoplar `simulate_v3` de `find_entries`, no rediseñar
  la lógica de gestión ya validada por el proyecto.
- **Riesgo de integración a ciegas entre C2 y C3** si se desarrollan en
  paralelo sin fijar antes el contrato de señal (columnas y tipos exactos que
  `research/layers.py` produce y `research/simulate.py` consume).

## 9. Historial de revisiones

| Versión | Cambio principal |
|---|---|
| v1 | Primera propuesta de arquitectura objetivo (6 fases, sin distinguir qué ya existía como precedente de estilo en el código). |
| v2 | Reordenamiento de fases para permitir paralelismo real (C en paralelo con A/B); corrección de componentes sobredimensionados (el simulador y el motor de backtest no se construyen desde cero, se extraen). |
| v3 | Reducción de 9 a 4 componentes nombrados; TA-Lib movido a "Decisiones Pendientes" (§10) por requerir validación técnica antes de ratificarse; se agregan principios de gobernanza (§0) y reglas de dependencias (§2); se documenta el hallazgo de los 4 esquemas de trade record ya divergentes como justificación del esquema canónico en `research/runner.py`. |
| v4 | Fase A dada por cerrada: §3 y §5 actualizados (`market_data` existe y está versionado, `versions.py` es importable). ADR-001 (§10) ratificado — TA-Lib queda fijado como dependencia de runtime para EMA/ATR, consistente con `DC-v1_Precisiones_Implementacion.md` P-7. |
| v5 | Fase B dada por cerrada: los 9 datasets reales (3 activos × 2022/2023/2024) se generaron y validaron vía `scripts/build_dc_v1_datasets.py` (`pipeline_version=dc-v1`, `dataset_version=market-data-v1` consistentes en los 9). §3, §5 y §6.1 (nueva columna "Estado") actualizados. |
| v6 | Migración de unificación del motor de señales (backlog post-Fase-B, ítem 1) reflejada: `bot.py` y `backtest.py` ya consumen `research/layers.py` para Trigger+Entry (Capa 2/3); Bias permanece inline en `backtest.py` por una fórmula genuinamente distinta a la registrada, no por trabajo pendiente — su reconciliación queda como backlog independiente. §3, §5 y §6.1 (Fase C3 → Parcial) actualizados. |
| v7 (este documento) — **Architecture Baseline v1** | Cierre de las Iniciativas A-G del backlog post-Fase-B: `dc_v1` gana consumidores reales para funciones de indicador (B); fuente EMA/ATR mayormente unificada, con la única excepción deliberada atada a G (B); Bias formalizado como dos candidatos nombrados A/A2 con convergencia condicionada a datos reales, todavía bloqueada (G); núcleo de métricas parcialmente consolidado en `research/metrics.py` (D); las preguntas de sesión y Config se evaluaron y cerraron sin consolidar (C, E). §3, §5, §6.1 y §10 (ADR-001) actualizados. |

---

## 10. Decisiones pendientes (ADRs)

Estas decisiones **no forman parte de la arquitectura oficial** hasta que se
resuelvan explícitamente. Se documentan aquí para no perderlas ni bloquear el
resto del roadmap mientras se resuelven.

### ADR-001 — Implementación de indicadores canónicos (EMA/ATR) en `dc_v1`

- **Estado:** Ratificado. `DC-v1_Precisiones_Implementacion.md` (P-7) registra
  la decisión: TA-Lib es la dependencia de runtime definitiva para EMA/ATR,
  coherente con `dc_v1/indicators.py` ("Gobernanza P-7 (congelado)").
- **Contexto:** `dc_v1/indicators.py` pinea EMA y ATR a TA-Lib, una librería
  en C que requiere instalación a nivel de sistema (no solo `pip install`).
  En etapas tempranas del proyecto se verificó que TA-Lib **no estaba
  instalado** en al menos un entorno de desarrollo (`ModuleNotFoundError` al
  importar); desde la Iniciativa B (backlog post-Fase-B) TA-Lib está
  instalado e importable en el entorno de desarrollo activo — es lo que
  permitió medir empíricamente las divergencias numéricas de esa iniciativa.
  Sigue siendo un paso de preparación de entorno explícito (Fase B, tarea de
  instalación), no algo que `pip install -r requirements.txt` resuelva, en
  cualquier máquina nueva donde falte.
- **Decisión:** TA-Lib como dependencia de runtime (opción 1 de las
  evaluadas). La alternativa vendorizada (pandas/numpy puro, verificada con
  `assert_equivalence_pandas_ta`) queda descartada como implementación de
  runtime salvo que una revisión futura reabra esta ADR explícitamente.

---
