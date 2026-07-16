# Arquitectura Objetivo — SMC Trading Bot

**Estado:** Referencia oficial de arquitectura (v3)
**Última revisión:** 2026-07-16

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

- Dos flujos de datos y señal **completamente desconectados**: el legacy
  (`bot.py` + `backtest.py`, cada uno con su propia lógica inline de
  indicadores/señal) y `dc_v1` (contrato de datos, sin nada que lo consuma
  todavía).
- **`bot.py` y `backtest.py` no implementan la misma estrategia.** `bot.py`
  usa *Liquidity Sweep + BOS + pullback 50%*; `backtest.py` (`find_entries`)
  usa un *cruce EMA9/EMA21 con filtro de bias 4H* ("T1"). El riesgo de "dos
  implementaciones de señal que divergen" no es hipotético — ya es el estado
  del repo.
- `simulate_v3` en `backtest.py` **ya acepta una configuración de salida como
  parámetro** (`exit_cfg`) y ya corre variantes desde un diccionario
  (`EXIT_CONFIGS`) — el patrón de "registro de variantes" que necesita el
  Motor de Estrategia objetivo ya existe como precedente de estilo.
- Cuatro corridas de backtest ya generaron cuatro esquemas de CSV de trades
  **distintos entre sí** (`backtest_trades.csv`, `t1_trades_completos.csv`,
  `t1_trades_multiasset.csv`, `v3_barxbar_trades.csv`) — evidencia concreta de
  que sin un esquema canónico, cada experimento reinventa sus columnas.
- `market_data` no existe; `versions.py` depende de él y no es importable hoy.

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
| `market_data` | No | Sí — bloqueante para todo lo que use datos reales |
| `dc_v1` | Sí (con datos sintéticos) | Conectado a datos reales vía `market_data` |
| Contrato de señal (columnas requeridas por capa) | No (implícito, no declarado) | Declarado en `research/layers.py` |
| Registro de capas 1/2/3 intercambiables | No — dos implementaciones fijas y **distintas** entre sí | Un registro único, consumido por `research` y `bot` |
| Simulador de gestión genérico | Ya existe dentro de `backtest.py`, acoplado a una sola señal | Extraído a `research/simulate.py` |
| Métricas + Gate | Duplicado (2 versiones casi idénticas) | Consolidado en `research/metrics.py` |
| Esquema canónico de trade record | No — 4 esquemas distintos ya en el repo | Un esquema fijo, usado por todas las corridas |
| Experiment Runner | Manual (correr script, leer consola) | Automatizado en `research/runner.py`, con manifiesto versionado |
| Config de variante ganadora | No — hardcodeada en `bot.py` | Artefacto de salida de `research.runner`, leído por `bot` |
| Circuit breaker | Especificado en `FRAMEWORK.md`, no implementado | Implementado en `bot` |
| Persistencia de estado del bot | No — `BotState` solo en memoria | Persistido para recuperación tras crash |

## 6. Roadmap de migración

### 6.1 Fases

| Fase | Contenido | Depende de |
|---|---|---|
| **A** | `market_data`: descarga y almacenamiento versionado de OHLCV crudo | — |
| **B** | `dc_v1` conectado a datos reales vía `market_data`; cerrar `versions.py` | A |
| **C1** | Consolidar métricas + gate en `research/metrics.py` | — (independiente, puede empezar ya) |
| **C2** | Extraer el simulador de gestión a `research/simulate.py`, probado primero contra la ruta de datos legacy que ya funciona hoy | — (independiente de A/B) |
| **C3** | Construir `research/layers.py` (registro de capas + contrato de señal + esquema canónico de trade record) | — (independiente de A/B) |
| **D** | `research/runner.py`: barrido completo 2022→2023→2024 con disciplina de blind set | A, B, C1, C2, C3 |
| **E** | Artefacto de configuración ganadora + refactor de `bot` (separación interna + circuit breaker + persistencia) | D |
| **F** | Paper trading operativo endurecido (monitoreo del circuit breaker en producción) | E |

C1/C2/C3 pueden empezar de inmediato, en paralelo con A/B — no dependen de
datos reales ni del contrato `dc_v1` para su desarrollo inicial (se validan
contra la ruta de datos legacy y se re-apuntan a `dc_v1` cuando B esté listo).
Solo D requiere que A y B estén cerradas, porque es el punto donde los
resultados dejan de ser exploratorios y empiezan a informar decisiones reales
sobre qué variante operar.

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
| v3 (este documento) | Reducción de 9 a 4 componentes nombrados; TA-Lib movido a "Decisiones Pendientes" (§10) por requerir validación técnica antes de ratificarse; se agregan principios de gobernanza (§0) y reglas de dependencias (§2); se documenta el hallazgo de los 4 esquemas de trade record ya divergentes como justificación del esquema canónico en `research/runner.py`. |

---

## 10. Decisiones pendientes (ADRs)

Estas decisiones **no forman parte de la arquitectura oficial** hasta que se
resuelvan explícitamente. Se documentan aquí para no perderlas ni bloquear el
resto del roadmap mientras se resuelven.

### ADR-001 — Implementación de indicadores canónicos (EMA/ATR) en `dc_v1`

- **Estado:** Pendiente de decisión. No bloquea las Fases A–F del roadmap
  (§6), salvo que se cierre antes de dar por completada la Fase B.
- **Contexto:** `dc_v1/indicators.py` pinea EMA y ATR a TA-Lib, una librería
  en C que requiere instalación a nivel de sistema (no solo `pip install`).
  Se verificó que TA-Lib **no está instalado** en al menos un entorno de
  desarrollo de este proyecto (`ModuleNotFoundError` al importar). El propio
  `DC-v1_Precisiones_Implementacion.md` marca esta decisión como **P-7,
  "pendiente de ratificación"** por el Research Director — no es una
  decisión de gobernanza ya cerrada.
- **Opciones a evaluar:**
  1. Mantener TA-Lib como dependencia de runtime (estado actual de P-7).
  2. Implementación propia (pandas/numpy puro) de EMA con semilla SMA y ATR
     con suavizado de Wilder, verificada una única vez contra TA-Lib
     (`assert_equivalence_pandas_ta`, ya existente en el módulo) y luego
     vendorizada, sin dependencia de runtime.
- **Qué falta para decidir:** confirmar equivalencia numérica en casos borde
  (no solo el caso general que ya cubre `assert_equivalence_pandas_ta`) y que
  el Research Director ratifique la opción elegida, tal como el propio
  documento de precisiones exige.
- **Próximo paso:** llevar esta comparación al Research Director antes de
  cerrar la Fase B del roadmap.

---
