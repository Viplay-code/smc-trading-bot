# SMC Trading Bot — Framework de Diseño y Validación

## Objetivos

| Parámetro | Valor |
|-----------|-------|
| Activos | BTCUSDT, ETHUSDT, SOLUSDT |
| Frecuencia objetivo | 6-12 trades/mes por activo |
| Timeframe HTF | 4H |
| Timeframe entrada | 1H |
| Riesgo por trade | 0.5% del equity |
| RR mínimo | 1:2.5 |

---

## Criterios de aceptación (jerarquía estricta)

Una variante es válida SOLO si cumple TODOS estos criterios en este orden:

### Requisitos eliminatorios (todos obligatorios)
1. Profit Factor ≥ 1.50
2. Drawdown máximo ≤ -10%
3. Expectancy positiva después de comisiones y slippage
4. Frecuencia: 6-12 trades/mes por activo (72-144 trades/año)

### Métrica de selección entre variantes válidas
- Criterio principal: Profit Factor (mayor = mejor)
- Una variante con PF mayor que NO cumpla los 4 requisitos anteriores
  es descalificada automáticamente, sin excepciones.

---

## Supuestos de costos (comisiones + slippage)

| Concepto | Valor aplicado |
|----------|---------------|
| Comisión Binance Futures maker | 0.02% por lado |
| Comisión total por trade | 0.04% (entrada + salida) |
| Slippage estimado | 0.05% por trade |
| Costo total por trade | 0.09% del tamaño de posición |

Aplicación: reducir el PnL de cada trade en 0.09% antes de calcular métricas.

---

## Método de validación — 3 períodos

| Período | Fechas | Rol |
|---------|--------|-----|
| In-Sample | 2022-01-01 → 2022-12-31 | Desarrollo y ajuste de parámetros |
| Validación | 2023-01-01 → 2023-12-31 | Selección de variante ganadora |
| Prueba ciega | 2024-01-01 → 2024-12-31 | Evaluación final sin tocar parámetros |

Regla: Los parámetros se eligen exclusivamente con datos de 2022.
El período 2024 NO se consulta hasta que la variante ganadora esté seleccionada.

---

## Arquitectura de la estrategia — 3 capas evaluables

### Capa 1: Contexto HTF (filtro de dirección)
Candidatos a evaluar:
- A: EMA200 4H con zona neutral ±1%  ← baseline actual, único registrado en
  `BIAS_LAYERS` (`research.layers::bias_A_ema200_neutral`), lo usa `bot.py`.
  Clasifica una vez por vela 4H: cierre 4H vs su propia EMA200 4H.
- A2: misma EMA200 4H y zona neutral ±1% que A, pero con mecánica temporal
  distinta — reclasifica en CADA vela 1H, comparando el cierre 1H (que se
  mueve cada hora) contra el nivel de EMA200 de la última vela 4H ya cerrada
  (sostenido/`ffill` durante las 4 horas siguientes). Es la fórmula que
  `backtest.py::build_features` calcula inline hoy; formalizada como port
  literal en `research.layers::bias_A2_ema200_neutral_1h_held` (2026-07-22,
  Iniciativa G del backlog post-Fase-B), fuera de `BIAS_LAYERS` porque su
  firma `(df1h, df4h)` no encaja en el contrato `BiasFn` de A. Documentar A2
  no es una recomendación de converger hacia ella ni de preferirla sobre A:
  **a la fecha (2026-07-22) no existe validación empírica registrada con
  datos reales que compare A vs A2** contra las métricas de esta sección (PF,
  DD, Expectancy, frecuencia) — la decisión de mantener ambas, converger
  hacia una sola, o diseñar una tercera fórmula queda condicionada a esa
  validación (2022 in-sample como mínimo). Ver Iniciativa G en el backlog
  post-Fase-B para el análisis de la divergencia numérica medida sobre datos
  sintéticos.
- B: EMA50 + EMA200 4H (cruce de medias)
- C: Precio vs máximo/mínimo de las últimas 20 velas 4H

### Capa 2: Trigger LTF (señal de entrada)
Candidatos a evaluar:
- A: Liquidity Sweep + BOS (3 velas)  ← baseline actual
- B: Liquidity Sweep + BOS (5 velas)
- C: Solo BOS sin sweep previo
- D: Ruptura y cierre fuera de rango de 10 velas
- T1: Cruce EMA9/EMA21 — implementado en `backtest.py` (validación V3
  barra-a-barra), portado a `research.layers::trigger_T1_ema_cross`
  (2026-07-21). Dirección del evento = dirección del cruce (alcista/bajista),
  sin filtrar por bias — igual que A, ese filtro lo aplica quien orqueste.

### Capa 3: Entrada (precio exacto)
Candidatos a evaluar:
- A: Orden límite al 50% del rango Sweep→BOS  ← baseline actual
- B: Zona 40%-60% (entrada al tocar la zona)
- C: Cierre de la vela de señal (entrada a mercado) — generalizado de
  "cierre de vela BOS": no depende de qué candidato de Capa 2 produjo el
  evento. Implementado en `research.layers::entry_C_market_close`
  (2026-07-21); es el precio de entrada que usa T1 hoy en `backtest.py`.
- D: Apertura de vela siguiente al BOS

### Gestión (fija para todas las variantes)
- Stop Loss: mínimo entre estructura y ATR(14) × 1.5
- Take Profit: 2.5R fijo
- Sesiones: Londres 07-11 UTC + Nueva York 13-17 UTC — ventana operativa que
  filtra CUÁNDO se buscan setups (`bot.py::in_session`, `backtest.py`'s
  columna `in_session`), distinta de la taxonomía de sesión de mercado que
  produce `dc_v1` (`london`/`overlap`/`ny`/`off` sobre las 24h, análisis
  2026-07-22 en el backlog post-Fase-B — Iniciativa C). Cada ventana arranca
  exactamente en la apertura de Londres/NY y dura 4h, consistente con
  filtrar las horas de mayor probabilidad de barrido de liquidez, y excluye
  a propósito el overlap (11-13 UTC) y las horas tardías de cada sesión —
  no es la misma ventana que "está abierto el mercado de Londres/NY".
  **A la fecha (2026-07-22) no existe una validación empírica registrada
  que compare esta ventana operativa contra ventanas alternativas** (a
  diferencia de Capa 1/2/3, que sí tienen candidatos enumerados y
  evaluables) — esto documenta el estado de la evidencia, no implica que
  la configuración actual esté mal elegida.
- Una posición a la vez por activo

---

## Parada automática del bot (circuit breaker)

Condiciones que detienen el bot hasta nueva validación manual:
1. Drawdown sobre equity inicial del período supera -10%
2. Profit Factor rolling de últimos 20 trades cae por debajo de 1.0
3. 5 pérdidas consecutivas (alerta, no parada automática)

---

## Orden de ejecución del proyecto

1. [x] Definir framework y criterios
2. [ ] Construir backtester modular (cada capa es un módulo independiente)
3. [ ] Evaluar todas las combinaciones en 2022 (in-sample)
4. [ ] Seleccionar top 3 variantes que cumplan criterios
5. [ ] Validar top 3 en 2023 — elegir ganadora
6. [ ] Prueba ciega en 2024 — aceptar o rechazar
7. [ ] Paper trading en Testnet mínimo 4 semanas
8. [ ] Capital real con tamaño mínimo
