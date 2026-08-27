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
- B: EMA50 + EMA200 4H (cruce de medias) — evaluado bajo el contrato
  Trigger=`T1_ema_cross`/Entry=`C_market_close`/sesión=`dcv1_activo_15h`/
  Gestión V3-A, comparador principal Bias A bajo el mismo contrato. Ver
  sección "Bias B — EMA50+EMA200 4H (cruce) — cerrado" más abajo.
- C: Precio vs máximo/mínimo de las últimas 20 velas 4H

### Capa 2: Trigger LTF (señal de entrada)
Candidatos a evaluar:
- A: Liquidity Sweep + BOS (3 velas)  ← baseline actual
- B: Liquidity Sweep + BOS (5 velas)
- C: Solo BOS sin sweep previo — evaluado bajo el contrato Bias=A/
  Entry=`C_market_close`/sesión=`dcv1_activo_15h`/Gestión V3-A,
  comparador principal `A_sweep_bos` bajo el mismo contrato. Ver
  sección "Trigger C — BOS-only — cerrado" más abajo.
- D: Ruptura y cierre fuera de rango de 10 velas — implementado como
  `research.layers::trigger_D_range_breakout` (2026-08-18, Rama B, ver
  sección "Rama B — Trigger/Entry" más abajo). Evaluado en esa campaña
  únicamente en la combinación `D_range_breakout`+`C_market_close`, bajo
  el contrato específico documentado ahí — no bajo todas las sesiones,
  Gestión o combinaciones de Entry posibles. Ver esa sección también para
  la relación de este candidato con Espacio 5 (`docs/research/
  EXPERIMENTAL_ROADMAP.md`), donde figuraba como sub-candidato sin evaluar.
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
- D: Apertura de vela siguiente al BOS — generalizado a "apertura de la vela
  siguiente al evento de Capa 2" (mismo criterio que C: no depende de qué
  candidato lo produjo). Implementado en
  `research.layers::entry_D_next_candle_open` (2026-07-27).

### Gestión (fija para todas las variantes)
- Stop Loss: mínimo entre estructura y ATR(14) × 1.5
- Take Profit: 2.5R fijo — especificación histórica de este documento, NO
  la Gestión vigente del motor (esa es V3-A, ver Espacio 1). Evaluada
  como mecanismo alternativo de salida en Espacio 6, Experimento 1 — ver
  sección "Espacio 6 — Experimento 1 — TP fijo 2.5R — cerrado" más abajo.
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
- Búsqueda de mejora en gestión (BE/trailing): diagnóstico MFE/MAE sobre datos
  reales 2022/2023 (2026-07-30, baseline Bias=A/Trigger=T1/Entry=C/
  atr_mult=1.5/sesión control_8h/salida V3-A) encontró un margen positivo y
  consistente entre `avg_win` realizado y la media de MFE_R de los trades
  ganadores en los 6 combos activo×año evaluados (Paso 1) — evidencia
  compatible con que la gestión activa limita la captura del movimiento
  favorable disponible, en los tres activos. Comparado contra el `avg_win`
  que exigiría el gate PF≥1.50 de este documento (Paso 2, umbral derivado
  algebraicamente, no arbitrario), el techo teórico lo alcanza en 5 de 6
  combos: ETHUSDT y SOLUSDT en ambos años, BTCUSDT solo en 2022 (en 2023 el
  margen es negativo, -0.43R sobre un requerido de 3.58R). Esto no
  demuestra que una implementación realista de BE/trailing desacoplados
  ("H2") sea incapaz de cerrar esa diferencia en BTCUSDT — solo que la
  evidencia previa es más fuerte en ETHUSDT/SOLUSDT. Habilita una futura
  campaña H2 sobre los tres activos, con BTCUSDT evaluado por separado
  dentro de esa campaña (no excluido de antemano) dado su resultado más
  débil en 2023. Todavía no implementada. El baseline usado (sesión
  control_8h) ya reprueba el gate de frecuencia de FRAMEWORK.md en los 6
  combos evaluados (campaña de sesión, 2026-07-29); superar el Paso 2 no
  implica que este baseline pasaría los 4 gates — eso lo determina el
  `gate_check()` de la futura campaña H2. Detalle:
  `scripts/gestion_mfe_diagnostico.py`, `gestion_mfe_diagnostico_summary.csv`/
  `_trades.csv`.
- Familia H2 (BE/trailing desacoplados) — cierre de las dos primeras
  campañas aisladas, cada una con Bias=A/Trigger=T1/Entry=C/atr_mult=1.5/
  sesión control_8h fijos (mismo baseline que la campaña de sesión ya
  reprobó en frecuencia, 2026-07-29 — heredado a propósito para preservar
  comparabilidad dentro de la familia, no por desconocimiento):
  - **H2.1 — distancia de trailing** (`distance`; `be`=1.0R/`activation`=2.0R
    fijos en su ancla V3-A; 2026-07-30/31, `scripts/gestion_campaign_
    trailing_distance.py`, cerrada commit `9e05c96`). Grilla base
    {0.5, 0.75, 1.0, 1.5} + extensiones por contingencia {0.25, 1.25}.
    Ninguna combinación superó los 4 gates en 2022+2023 en ningún activo
    — la frecuencia, idéntica para todo el rango de `distance` dentro de
    cada (activo, año) por construcción (las entradas no dependen de esta
    variable), nunca alcanzó el piso de 6 bajo `control_8h`. Se observó
    una asociación entre valores de `distance` más ajustados (0.25R-0.5R)
    y PF más alto, consistente en 2022 y 2023, en ETHUSDT y SOLUSDT; en
    BTCUSDT el signo de esa asociación se invirtió entre 2022 y 2023, sin
    dirección estable. Sin evidencia suficiente para promover ningún
    valor de `distance` — ninguna combinación superó los 4 gates.
  - **H2.2 — activación del trailing** (`activation`; `be`=1.0R/
    `distance`=1.0R fijos en su ancla V3-A — explícitamente NO el valor
    asociado con PF más alto en H2.1, para no promover un candidato nunca
    validado por gates; 2026-07-31 a 2026-08-03, `scripts/gestion_
    campaign_activation.py`, cerrada commit `c0add0a`). Grilla base
    {1.5, 2.0, 2.5} + extensiones por contingencia {1.25, 3.0} (disparadas
    en BTCUSDT 2022/superior, SOLUSDT 2022/superior, ETHUSDT 2023/
    superior, BTCUSDT 2023/inferior, SOLUSDT 2023/inferior; ETHUSDT 2022
    no disparó ninguna — el mejor PF observado entre los 3 puntos base
    coincidió con el propio ancla). Ninguna combinación superó los 4
    gates en ningún activo — mismo mecanismo estructural que H2.1: la
    frecuencia es idéntica dentro de cada (activo, año) sin importar
    `activation` (verificado: las entradas no dependen de esta variable
    por construcción del motor) y nunca cruza el piso de 6 bajo
    `control_8h` — el gate de frecuencia no dependía de `activation` en
    absoluto. Se observó una asociación monótona y consistente en las 6
    combinaciones activo×año entre valores más altos de `activation` y WR
    más bajo junto con `avg_win` más alto — consistente con el mecanismo
    determinístico del motor (`simulate_v3`): a mayor umbral de
    activación, menos operaciones lo alcanzan antes de revertir, y las
    que lo alcanzan lo hacen tras un movimiento favorable mayor. `avg_loss`
    también se observó levemente menor en magnitud en el mismo sentido. A
    diferencia de H2.1, esta asociación no se acompañó de una dirección de
    PF consistente entre 2022 y 2023 en ningún activo: en BTCUSDT y
    SOLUSDT el signo de la asociación entre `activation` y PF se invirtió
    entre años; en ETHUSDT el mejor PF observado coincidió con el ancla en
    2022, mientras que en 2023 el ancla fue el peor PF observado entre los
    3 puntos base. Sin evidencia suficiente para promover ningún valor de
    `activation` — ninguna combinación superó los 4 gates.
  - **H2.3 — nivel de breakeven** (`be`; `activation`=2.0R/`distance`=1.0R
    fijos en su ancla V3-A — explícitamente NO los hallazgos de H2.1/H2.2,
    misma regla de no-promoción; 2026-08-03/04, `scripts/gestion_
    campaign_be.py`, cerrada commit `b5cee18`). Grilla base
    {0.5, 1.0, 1.5} + extensiones por contingencia {0.25, 2.0} (disparadas
    en BTCUSDT 2022/inferior, SOLUSDT 2022/inferior, ETHUSDT 2022/
    superior, BTCUSDT 2023/superior, ETHUSDT 2023/inferior; SOLUSDT 2023
    no disparó ninguna — el mejor PF observado entre los 3 puntos base
    coincidió con el propio ancla). Ninguna combinación superó los 4
    gates en ningún activo — mismo mecanismo estructural que H2.1/H2.2:
    la frecuencia es idéntica dentro de cada (activo, año) sin importar
    `be` y nunca cruza el piso de 6 bajo `control_8h`. A diferencia de
    H2.1, no se observó una dirección de PF que se repita entre 2022 y
    2023 en ningún activo — ni siquiera en ETHUSDT/SOLUSDT, donde
    `distance` sí la había mostrado: en BTCUSDT y ETHUSDT el signo de la
    asociación entre `be` y PF se invirtió entre años; en SOLUSDT el
    mejor PF observado se ubicó en extremos distintos cada año. Se
    observaron dos asociaciones monótonas y consistentes en las 6
    combinaciones activo×año: WR más alto y `avg_loss` de mayor magnitud
    a medida que aumenta `be`. Una interpretación consistente con la
    lógica de `simulate_v3` (`backtest.py:192-198`) — no una demostración
    causal derivada de esta campaña — es que un `be` más bajo mueve el
    stop a la entrada antes, lo que podría limitar tanto la magnitud de
    las pérdidas de operaciones que nunca alcanzan ese nivel como el
    conteo de ganadoras (operaciones que hubieran seguido a favor
    quedarían cortadas en breakeven). `avg_win` no mostró una asociación
    monótona en ninguna de las 6 combinaciones. Sin evidencia suficiente
    para promover ningún valor de `be` — ninguna combinación superó los
    4 gates.
  - La familia H2 queda formalmente cerrada: `distance`, `activation` y
    `be` quedaron caracterizadas de forma aislada, cada una bajo el mismo
    protocolo homogéneo (Bias=A/Trigger=T1/Entry=C/atr_mult=1.5/sesión
    control_8h fijos, grilla simétrica con reglas de contingencia
    pre-especificadas, gates literales de FRAMEWORK.md). Ninguna de las
    tres campañas produjo una configuración que superara los 4 gates, por
    lo que ninguno de los tres cierres autoriza adoptar un valor de
    `distance`, `activation` o `be` para el sistema integrado. La
    selección de una configuración integrada — entre los candidatos que
    cada campaña no descartó objetivamente (dominados en las 4 métricas
    de `gate_check()` por otro candidato) — queda diferida a la futura
    Fase de Integración, bajo la regla de eliminación-no-promoción
    acordada 2026-07-31.
- Fase de Integración (I1) — primera prueba conjunta de sesión y un
  parámetro de Gestión, motivada porque toda campaña de la familia H2 fijó
  sesión=`control_8h` (que por sí sola ya garantiza freq<6) mientras que la
  campaña de sesión solo probó `dcv1_activo_15h` bajo la Gestión por
  defecto, nunca bajo un valor de `distance`/`activation`/`be` con
  evidencia de PF real — la celda del espacio de búsqueda que ningún
  experimento anterior había tocado:
  - **Paso 0 — congelamiento del espacio experimental** (2026-08-04,
    análisis sobre CSV ya publicados, sin campaña nueva): dominación
    Pareto sobre (pf, max_dd, exp_r) por (activo, año), sin comparar entre
    activos, aplicada a los resultados ya publicados de H2.1/H2.2/H2.3.
    `distance` se poda de 6 a 3 valores no-dominados ({0.25, 0.5, 1.5} —
    el ancla V3-A, `distance`=1.0, queda dominada en TODOS los contextos
    probados); `activation` y `be` no se podan en absoluto (los 5 valores
    probados en cada campaña sobreviven en algún contexto — reflejo
    directo de que ninguno de los dos mostró una dirección de PF estable
    entre años). Este conjunto queda congelado: I1 no recalcula
    dominación, cualquier cambio exige repetir formalmente el Paso 0 y
    aprobar un nuevo contrato.
  - **I1-distance** (`distance` ∈ {0.25, 0.5, 1.5} × sesión ∈
    {`control_8h`, `dcv1_activo_15h`}, `be`=1.0R/`activation`=2.0R fijos
    en su ancla V3-A; 2026-08-04/05, `scripts/integration_campaign_
    distance.py`, cerrada commit `8688020`). Protocolo con Fase A
    (verificación de integridad, obligatoria antes de cualquier resultado
    experimental) + Fase B (barrido). Fase A verificada de forma
    independiente antes de aceptar cualquier fila experimental: las 12
    filas de control (`distance`=1.0 × 2 sesiones × 3 activos × 2 años)
    coinciden EXACTO, sin un solo mismatch, con `gestion_campaign_
    trailing_distance_results.csv` (H2.1) y `gestion_campaign_session_
    results.csv` (V3-A). Ninguna de las 6 combinaciones candidatas superó
    los 4 gates en ningún activo — de las 36 filas candidatas evaluadas,
    ninguna alcanzó siquiera PF≥1.50 en un solo año (máximo observado:
    1.417, SOLUSDT 2023, `0.5 | dcv1_activo_15h`). Bajo `dcv1_activo_15h`
    la frecuencia pasó siempre (18/18 en [6,12]) y `max_dd`/`exp_r`
    pasaron la mayoría de las veces (15/18 y 11/18) — PF queda
    establecido como el gate universalmente vinculante en esta rama del
    espacio, ya no la frecuencia. Se observó una asociación entre
    `distance` más ajustado (0.25R-0.5R) y PF más alto en 7 de los 12
    contextos activo×año×sesión, monótona en ambas sesiones (cero
    contextos con la dirección opuesta) — reproduce y extiende la
    asociación ya vista en H2.1 a la sesión `dcv1_activo_15h`, pero su
    magnitud es insuficiente para cerrar el gate incluso en la mejor
    combinación observada. El efecto de la sesión sobre PF (a `distance`
    fijo) no mostró dirección estable entre años en ningún activo.
    Hipótesis I1-distance falsificada: ninguna combinación (`distance`,
    sesión) del conjunto no-dominado supera los 4 gates en 2022 Y 2023
    para ningún activo. Sin evidencia suficiente para promover ninguna
    combinación — quedan pendientes I1-activation e I1-be, mismo
    protocolo, sobre los conjuntos ya congelados en el Paso 0.
  - **I1-activation** (`activation` ∈ {1.25, 1.5, 2.0, 2.5, 3.0} × sesión
    ∈ {`control_8h`, `dcv1_activo_15h`}, `be`=1.0R/`distance`=1.0R fijos
    en su ancla V3-A — anclas de H2.2, NO los hallazgos de H2.1/H2.3;
    2026-08-06, `scripts/integration_campaign_activation.py`, cerrada
    commit `d3930ff`). Protocolo idéntico a I1-distance, con dos
    verificaciones adicionales por el rol dual del ancla (`activation`=2.0
    es simultáneamente candidato no-dominado del Paso 0 y valor de
    control, a diferencia de `distance`=1.0 en I1-distance): Fase A (12
    verificaciones independientes — 6 contra `gestion_campaign_
    activation_results.csv` (H2.2) y 6 contra `gestion_campaign_session_
    results.csv` (V3-A)) y verificación de rol dual (la fila control de
    `activation`=2.0 y su fila candidata equivalente, misma sesión, deben
    coincidir exacto en TODAS las métricas publicadas, no solo PF/
    gate_pass). Ambas verificadas de forma independiente antes de aceptar
    cualquier resultado: 12/12 coincidencias exactas en cada una. Ninguna
    de las 10 combinaciones candidatas superó los 4 gates en ningún activo
    — de las 60 filas candidatas evaluadas, ninguna alcanzó siquiera
    PF≥1.50 en un solo año (máximo observado: 1.360, SOLUSDT 2023,
    `1.25 | dcv1_activo_15h`). Bajo `dcv1_activo_15h` la frecuencia pasó
    siempre (30/30 en [6,12]) y `max_dd`/`exp_r` pasaron la mayoría de las
    veces (21/30 y 17/30) — PF vuelve a quedar como el gate universalmente
    vinculante, mismo patrón que I1-distance. El efecto de la sesión sobre
    PF (a `activation` fijo) mostró el mismo signo para los 5 valores de
    `activation` dentro de cada (activo, año) — BTCUSDT y SOLUSDT
    favorecen `control_8h` en 2022 y `dcv1_activo_15h` en 2023; ETHUSDT
    muestra el patrón invertido — más nítido que en I1-distance, donde el
    signo variaba también dentro de un mismo (activo, año). La evidencia
    respalda que ese efecto depende del contexto (activo, año) y no de
    `activation`; su causa queda como hipótesis abierta, explícitamente
    sin atribuir — no se interpreta como régimen de mercado ni ningún otro
    mecanismo sin evidencia adicional que lo sustente. La asociación de PF
    con `activation` fue no-monótona en 10 de los 12 contextos
    activo×año×sesión (a diferencia de la mayoría monótona que mostró
    `distance` en I1-distance) — reconfirma la falta de dirección estable
    ya vista en H2.2, ahora también bajo la sesión nueva. En cambio, el
    patrón mecánico de H2.2 (WR más bajo / `avg_win` más alto con
    `activation` más alto) se reprodujo con alta consistencia: WR
    monótonamente decreciente en 12/12 contextos, `avg_win` monótonamente
    creciente en 10/12 — coherente con el mecanismo determinístico de
    `simulate_v3` ya documentado, confirmado ahora bajo ambas sesiones.
    Hipótesis I1-activation falsificada: ninguna combinación (`activation`,
    sesión) del conjunto no-dominado supera los 4 gates en 2022 Y 2023
    para ningún activo. Sin evidencia suficiente para promover ninguna
    combinación — queda pendiente `I1-be`, mismo protocolo, sobre el
    conjunto ya congelado en el Paso 0.
  - **I1-be** (`be` ∈ {0.25, 0.5, 1.0, 1.5, 2.0} × sesión ∈ {`control_8h`,
    `dcv1_activo_15h`}, `activation`=2.0R/`distance`=1.0R fijos en su
    ancla V3-A — anclas de H2.3, NO los hallazgos de H2.1/H2.2; 2026-08-07,
    `scripts/integration_campaign_be.py`, cerrada commit `dfe595e`).
    Protocolo idéntico a I1-activation, incluida la verificación de rol
    dual (`be`=1.0 es simultáneamente candidato no-dominado del Paso 0 y
    valor de control, igual que `activation`=2.0 en el bloque anterior):
    Fase A (12 verificaciones independientes — 6 contra `gestion_campaign_
    be_results.csv` (H2.3) y 6 contra `gestion_campaign_session_
    results.csv` (V3-A)) y verificación de rol dual (la fila control de
    `be`=1.0 y su fila candidata equivalente, misma sesión, coinciden
    exacto en las 13 métricas publicadas). Ambas verificadas de forma
    independiente antes de aceptar cualquier resultado: 12/12 coincidencias
    exactas en cada una. Ninguna de las 10 combinaciones candidatas superó
    los 4 gates en ningún activo — de las 60 filas candidatas evaluadas,
    ninguna alcanzó siquiera PF≥1.50 en un solo año (máximo observado:
    1.471, SOLUSDT 2022, `0.5 | control_8h`). Bajo `dcv1_activo_15h` la
    frecuencia pasó siempre (30/30 en [6,12]) y `max_dd`/`exp_r` pasaron
    una fracción similar a la de I1-activation (22/30 y 18/30) — PF vuelve
    a quedar como el gate universalmente vinculante, mismo patrón que
    I1-distance e I1-activation. La sesión con mejor PF a `be` fijo fue
    consistente para los 5 valores dentro de cada (activo, año) en 5 de 6
    combinaciones (todas salvo ETHUSDT 2022); entre años, esa sesión
    favorecida se mantuvo igual solo en ETHUSDT (`control_8h` ambos años),
    mientras que en BTCUSDT y SOLUSDT se invirtió (`control_8h` en 2022,
    `dcv1_activo_15h` en 2023) — mismo patrón de dependencia de contexto
    (activo, año) ya visto en I1-activation, sin atribuir causa. La
    asociación entre `be` y PF no mostró una dirección estable entre 2022
    y 2023 en 5 de los 6 contextos activo×sesión; la única excepción
    (BTCUSDT, `dcv1_activo_15h`) mantuvo el mismo signo pero con magnitud
    muy distinta entre años (correlación ≈0.88 en 2022 vs ≈0.22 en 2023) —
    evidencia débil, no una dirección confiable. El patrón mecánico ya
    visto en H2.3 se reprodujo con alta consistencia bajo ambas sesiones:
    WR monótonamente no decreciente en 12/12 contextos activo×año×sesión
    y `avg_loss` (magnitud) monótonamente no decreciente en 12/12;
    `avg_win` no mostró asociación monótona en ninguno de los 12 contextos.
    Hipótesis I1-be falsificada: ninguna combinación (`be`, sesión) del
    conjunto no-dominado supera los 4 gates en 2022 Y 2023 para ningún
    activo. Sin evidencia suficiente para promover ninguna combinación.
  - **Cierre integrado de la Fase I1** (2026-08-07): con `I1-distance`,
    `I1-activation` e `I1-be` cerrados bajo el mismo protocolo (Fase A de
    verificación de integridad obligatoria + Fase B de barrido, ambas
    verificadas de forma independiente en los tres bloques, sin un solo
    mismatch en ninguna de las verificaciones), el espacio experimental
    congelado en el Paso 0 (un parámetro de Gestión de la familia H2 ×
    sesión, con los otros dos parámetros de Gestión fijos en su ancla
    V3-A) queda agotado: de las 156 filas candidatas evaluadas en total
    (36 + 60 + 60), ninguna superó los 4 gates y ninguna combinación
    sobrevivió 2022 Y 2023 en ningún activo, en ningún bloque. El gate de
    frecuencia se resolvió, en los tres bloques por igual, exclusivamente
    en función de la sesión (0% bajo `control_8h`, 100% bajo
    `dcv1_activo_15h`, independiente de cuál parámetro de Gestión se
    varió) — el mismo patrón ya visto en la campaña de sesión aislada,
    ahora confirmado bajo tres interacciones independientes distintas. El
    PF observado no cruzó el gate de 1.50 en ninguna de las 156 filas; el
    máximo observado en toda la Fase I1 (1.476, I1-distance, SOLUSDT 2022,
    `0.25 | control_8h`) es consistente con los máximos ya vistos en
    H1/H2.1/H2.2/H2.3 bajo `control_8h` en solitario — un máximo empírico
    que se repite de forma consistente a través de todas las campañas
    realizadas hasta ahora, sin que la evidencia disponible permita
    identificar su causa; se documenta como observación abierta, no como
    límite estructural demostrado. Los trade-offs mecánicos ya vistos en
    H2.1/H2.2/H2.3 (asociaciones monótonas y consistentes entre cada
    parámetro de Gestión y WR/avg_win/avg_loss) se reprodujeron bajo ambas
    sesiones en I1-activation e I1-be, pero en ningún bloque se tradujeron
    en una dirección de PF estable entre 2022 y 2023 para ningún activo.
    Los tres cierres son consistentes entre sí: la hipótesis de que variar
    un único parámetro de Gestión junto con la sesión sea suficiente para
    producir una configuración que supere los 4 gates queda falsificada en
    sus tres instancias (`distance`, `activation`, `be`). Esto no
    determina por sí solo cuál es el siguiente espacio experimental a
    explorar (Gestión multivariable, revisión de Capa 1/2/3, u otra
    alternativa) — esa elección queda diferida a una decisión posterior,
    fuera del alcance de este cierre.

### Espacio 3 — Trigger × Sesión (`A_sweep_bos`) — cerrado

Bloque independiente de la Fase de Integración (I1): I1 varió sesión × un
parámetro de Gestión con Trigger fijo en `T1_ema_cross`; Espacio 3 varía
sesión con Trigger fijo en `A_sweep_bos` y Gestión fija en su ancla V3-A —
pregunta científica distinta (Capa 2/sesión, no Gestión de salidas), por lo
que se documenta en un bloque propio en vez de integrarse al cierre de I1.
Aprobado y ejecutado 2026-08-07 tras una fase de planificación metodológica
que comparó los espacios experimentales abiertos post-I1 por valor de
información esperado, costo experimental y riesgo metodológico, y priorizó
este espacio primero por su mayor VoI de primer y segundo orden.

- **Objetivo**: `trigger_campaign.py` había probado `A_sweep_bos`
  únicamente bajo `control_8h`, con PF extremos en 2022 (0.79-4.02 según
  activo) pero una muestra de apenas 2-4 trades/año en 2023 — insuficiente
  para que `backtest.metrics()` calculara ninguna métrica
  (`n_trades<5 → None`). Nunca se había probado si `A_sweep_bos` produce una
  muestra evaluable, y si el PF se sostiene, bajo una sesión más ancha —
  la celda que este bloque cierra.
- **Contrato experimental**: Bias=A/Entry=`C_market_close`/Gestión V3-A
  única (`be`=1.0R/`activation`=2.0R/`distance`=1.0R, sin V3-A y V3-B en
  paralelo)/`atr_mult`=1.5 fijos; una sola variable libre, sesión, 2
  niveles — `control_8h` (rol="control", NO candidato — resultado ya
  publicado en `trigger_campaign_results.csv`/`entry_campaign_sweep_bos_
  results.csv`) y `dcv1_activo_15h` (rol="candidate", única celda
  experimental; `sin_filtro_24h` quedó fuera, ya dominada objetivamente en
  la campaña de sesión bajo `T1_ema_cross`). Sin Paso 0 de dominación
  Pareto ni reglas de contingencia (a diferencia de H2/I1): con un solo
  nivel candidato no hay grilla que podar ni borde al que escalar.
  Hipótesis a falsificar: existe al menos un activo donde `A_sweep_bos` ×
  `dcv1_activo_15h` supera los 4 gates en 2022 Y 2023. Implementado en
  `scripts/trigger_campaign_sweep_bos_session.py` (commit `31a58ab`),
  resultados en `trigger_campaign_sweep_bos_session_results.csv`/
  `_decision.csv` (commit `76980f0`).
- **Verificación de integridad (Fase A)**: para los 6 combos (activo, año),
  la fila `control_8h` se comparó EXACTO (comparación NaN-consciente, los 3
  combos de 2023 tienen referencia NaN por el piso de `metrics()`) contra
  `trigger_campaign_results.csv` y `entry_campaign_sweep_bos_results.csv`
  — 12 verificaciones totales, sin rol dual (`control_8h` nunca es
  candidato en este espacio). Reproducidas de forma independiente
  (`pandas`, recalculando desde las métricas crudas del CSV, no
  confiando en la ausencia de `AssertionError` del script): **12/12
  coincidencias exactas, 0 mismatches**. Suite de tests estructural
  (`research/tests/test_trigger_campaign_sweep_bos_session.py`, 15
  funciones `test_*`) corrida en su totalidad: **15/15 pasan**, incluida
  la verificación de que las dos referencias históricas siguen
  coincidiendo entre sí sobre datos reales. La decisión publicada
  (`trigger_campaign_sweep_bos_session_decision.csv`) se recalculó de
  forma independiente desde las métricas crudas (`gate_check` +
  `summarize_decision`, sin modificar): 0 mismatches en los 5 campos
  publicados.
- **Resultados (Fase B)**: de las 6 celdas candidatas, 5/6 resultaron
  computables (n_trades≥5) — la sesión ancha resolvió computabilidad
  respecto de `control_8h` (donde los 3 combos de 2023 eran no
  computables); solo ETHUSDT/2023 permanece no computable (n_trades=4). El
  gate de frecuencia (6-12 trades/mes) **nunca se satisface, en ninguna de
  las 6 celdas** — freq observado 0.5-1.6/mes, un factor ~4x-24x por debajo
  del piso, pese a casi duplicar la ventana horaria (8h→15h). PF≥1.50 se
  cumple en 2/6 celdas (ETHUSDT 2022: 2.966; SOLUSDT 2022: 2.729, ambas
  también con `max_dd`/`exp_r` en regla) — únicamente el gate de
  frecuencia las bloquea. En las 4 celdas restantes PF no alcanza 1.50
  (0.637-1.395), con `exp_r`≤0 adicional en 2 de ellas (BTCUSDT 2022,
  SOLUSDT 2023). Ninguna celda supera los 4 gates simultáneamente; ningún
  activo sobrevive 2022 Y 2023 (`survives_both_years=False` en los 3
  activos).
- **Interpretación basada en evidencia**: patrón observado, no una
  explicación causal — en los tres activos, el PF de 2022 bajó al pasar de
  `control_8h` a `dcv1_activo_15h` (BTCUSDT 0.790→0.637, ETHUSDT
  3.203→2.966, SOLUSDT 4.022→2.729), dirección consistente en los tres
  casos. Con solo dos anchos de sesión probados no hay base para atribuir
  esa dirección a ningún mecanismo específico; se documenta como
  observación abierta y sin atribuir, no como explicación causal — mismo
  estándar aplicado en los cierres de I1-activation/I1-be. El gate de
  frecuencia es, con claridad, el factor universalmente vinculante en este
  espacio — a diferencia de I1 (donde `dcv1_activo_15h` resolvía
  frecuencia siempre y PF era el gate vinculante), acá ni la sesión más
  ancha alcanza a resolver frecuencia para `A_sweep_bos`. Esto es, en sí
  mismo, otra observación (no una explicación): es consistente con que el
  problema de este trigger sea de tasa de generación de eventos y no
  únicamente de ventana horaria, pero esta campaña no aísla esa causa —
  distinguirla exigiría un experimento propio, fuera de este contrato.
- **Conclusión**: hipótesis de Espacio 3 **falsificada bajo el contrato
  experimental evaluado** — dentro de esta configuración exacta (Bias=A/
  Entry=`C_market_close`/Gestión V3-A única/`atr_mult`=1.5, sesiones
  `control_8h` vs `dcv1_activo_15h`), ningún activo supera los 4 gates en
  2022 Y 2023 bajo `A_sweep_bos` × `dcv1_activo_15h`. Esto no generaliza
  que `A_sweep_bos` sea inviable en términos absolutos — otra Gestión,
  otra sesión, u otra combinación de Capa 1/3 podrían producir un
  resultado distinto y quedan fuera del alcance de lo que este contrato
  evaluó. Dentro de lo evaluado, predominantemente el caso "falsificación
  con muestra ya computable" (5/6 celdas), con la salvedad de que
  ETHUSDT/2023 permanece en el caso más débil (computabilidad no
  resuelta). La evidencia fortalece la elección actual de `T1_ema_cross`
  como trigger de trabajo, al reducir significativamente la incertidumbre
  sobre `A_sweep_bos` bajo esta configuración, sin demostrar por sí sola
  que `T1_ema_cross` sea el trigger óptimo ni que `A_sweep_bos` esté
  descartado en general.
- **Lecciones aprendidas**: (1) ampliar la ventana de sesión resuelve
  computabilidad de forma parcial pero no garantiza resolver el gate de
  frecuencia — depende de la tasa de generación de eventos del trigger
  subyacente, no solo de cuántas horas se observan; (2) el patrón "PF
  vinculante bajo sesión ancha" que dominó los tres bloques de I1 no se
  repite automáticamente para otro trigger — acá el gate vinculante volvió
  a ser frecuencia, contrario a lo esperado por analogía directa con I1.
- **Estado**: **CERRADO** (2026-08-07). No se continuará explorando este
  espacio experimental bajo el contrato actual — el resultado queda
  registrado como definitivo para esta configuración exacta, sin más
  iteraciones pendientes. Reabrir `A_sweep_bos` bajo una sesión distinta,
  otra Gestión, u otra combinación con Capa 1/3 requeriría un contrato
  nuevo explícitamente propuesto y aprobado, no una extensión ni una
  reapertura de este cierre.

### Espacio 2 — `max_hold` (parámetro de Gestión nunca variado) — cerrado

Bloque independiente, segundo en el orden de exploración aprobado
(Espacio 3 → Espacio 2 → Espacio 4 → Espacio 1, `docs/research/
EXPERIMENTAL_ROADMAP.md`). Contrato acordado 2026-08-08, tras una fase de
refinamiento metodológico previa a la implementación (ver esa misma fecha
en el roadmap para el detalle completo del razonamiento).

- **Objetivo e hipótesis**: `max_hold` (20 velas, fijo en absolutamente
  todas las campañas anteriores del programa) nunca había sido variado —
  laguna total de evidencia, ni siquiera indiferencia demostrada. Hipótesis
  a falsificar: bajo Bias=A/Trigger=`T1_ema_cross`/Entry=`C_market_close`/
  Gestión V3-A completa (`be`=1.0R/`activation`=2.0R/`distance`=1.0R)/
  `atr_mult`=1.5/`atr_period`=14 fijos, existe al menos un activo donde,
  bajo la combinación experimental (`max_hold`, sesión), el candidato
  supera los 4 gates de `FRAMEWORK.md` en 2022 Y 2023. Falsificada si,
  evaluados los 3 activos, ninguno sobrevive ambos años.
- **Contrato y alcance final**: originalmente concebido con dos
  parámetros (`max_hold`, `atr_period`); reducido a `max_hold` en
  solitario durante el refinamiento previo a la implementación (ver
  exclusiones abajo). Diseño sesión × parámetro (protocolo I1, no el
  patrón de un solo `control_8h` de H2) — justificado porque, a diferencia
  de `distance`/`activation`/`be`, `max_hold` sí tiene un mecanismo
  estructural verificado de interacción con `freq` (`run_config`/
  `simulate_v3`: reducir `max_hold` solo puede adelantar o igualar el
  `exit_time` de cada trade, nunca atrasarlo). Grilla: `max_hold` ∈
  {5, 10, 20(ancla), 30, 40} — proporciones 0.25x/0.5x/1x/1.5x/2.0x
  reutilizadas de H2.3, contingencia simétrica (`_is_extreme_best`,
  PF-only) evaluada independientemente por (activo, año, sesión) — ×
  sesión ∈ {`control_8h`, `dcv1_activo_15h`}. Implementado en
  `scripts/gestion_campaign_max_hold_session.py` (commit `f467f50`),
  resultados en `gestion_campaign_max_hold_session_results.csv`/
  `_decision.csv` (commit `a9f1dbd`).
- **Exclusión justificada de `risk`**: no una hipótesis sin explorar, sino
  una exclusión determinada por el propio diseño del sistema. Verificado en
  código (`research/metrics.py`, `backtest.py::metrics`) y confirmado
  empíricamente: `pf`/`wr`/`exp_r`/`total_r`/`freq` son exactamente
  invariantes a `risk` — solo afecta `max_dd`/`ret` vía la curva de equity.
  Escaneados los 12 CSV de resultados ya publicados del programa completo
  (previos a este cierre): cero filas bloqueadas exclusivamente por
  `max_dd`. Válida para la arquitectura actual de sizing; revisitable si
  cambia el modelo de gestión monetaria.
- **Exclusión justificada de `atr_period`**: no por "sin efecto", sino
  porque el pipeline de investigación vigente (`bias_campaign.
  to_backtest_frame` + `trigger_campaign.find_entries_for_trigger`) no
  puede medirlo — `risk_pts` de cada entrada se calcula desde la columna
  `atr14` de `dc_v1` (pin ratificado, `DC-v1_Precisiones_Implementacion.md`
  P-7), nunca desde `cfg.atr_period`. Confirmado empíricamente sobre datos
  sintéticos: `n_entries`/`n_trades`/`pf`/`freq`/`risk_pts` bit-idénticos
  barriendo `atr_period` ∈ {7,14,21,28}. Queda como iniciativa de
  infraestructura independiente (ATR de período arbitrario sobre la serie
  continua, con su propio test de equivalencia y de disciplina P-3),
  documentada en `docs/research/EXPERIMENTAL_ROADMAP.md`, no como hipótesis
  cerrada.
- **Verificación de integridad**: Fase A (24 verificaciones — 2 sesiones ×
  2 referencias × 6 combos, contra `trigger_campaign_results.csv`/
  `gestion_campaign_atr_mult_results.csv` para `control_8h` y
  `gestion_campaign_session_results.csv`/`integration_campaign_
  activation_results.csv` para `dcv1_activo_15h`) y verificación de rol
  dual (`max_hold`=20, ambas sesiones, 13 campos publicados). Ambas
  reproducidas de forma independiente antes de aceptar cualquier
  resultado, sin confiar en la ausencia de `AssertionError` del script:
  **24/24 y 12/12 coincidencias exactas, 0 mismatches**. `gate_check`
  recalculado desde métricas crudas sobre las 47 filas candidatas: 0
  mismatches. `summarize_decision` recalculado independientemente: 0
  diferencias contra la decisión publicada.
- **Resultados**: 47 filas candidatas, **47/47 computables** (n_trades≥5
  en todas — a diferencia de Espacio 3, acá la computabilidad nunca fue el
  problema). `max_dd` pasa 41/47, `exp_r` 27/47, `freq` 23/47 (siempre bajo
  `dcv1_activo_15h`, 0/24 bajo `control_8h` — mismo patrón que los 3
  bloques de I1), **`pf`≥1.50 pasa 0/47** — PF vuelve a ser el gate
  universalmente vinculante. Máximo PF observado: 1.364 (SOLUSDT 2023,
  `10 | dcv1_activo_15h`), dentro de la misma banda estrecha (~1.36-1.48)
  ya vista en los 3 bloques de I1. Ningún activo sobrevive 2022 Y 2023
  (`survives_both_years=False` en los 3 activos).
- **Análisis**: el mecanismo estructural sobre `freq` se confirma en
  **dirección** — monótonamente no-creciente en `max_hold` en **12/12**
  contextos (activo, año, sesión), exactamente como predice `busy_until`/
  `simulate_v3` — pero es **demasiado débil en magnitud**: bajo
  `control_8h`, el delta máximo observado en toda la grilla (5→40) es
  0.6 trades/mes, frente a una brecha real hacia el piso de 6 de entre
  +0.4 y +2.0 según el combo — nunca suficiente para cruzar el gate. La
  justificación metodológica de correr sesión × parámetro fue correcta
  *ex ante* (no había forma de conocer la magnitud sin ejecutar el
  contrato); el resultado específico que la motivó no se materializó. La
  dirección de la asociación PF-`max_hold` es específica de cada activo,
  sin atribución de causa: BTCUSDT decreciente en las 4 combinaciones
  año×sesión, ETHUSDT creciente en las 4, SOLUSDT mixto (positivo ambos
  años bajo `control_8h`; bajo `dcv1_activo_15h`, -0.27 en 2022 y +0.12 en
  2023) — se documenta como observación contextual, no como relación
  causal, mismo estándar que I1-activation/I1-be. Patrones mecánicos
  deterministas de `simulate_v3` (no requieren atribución causal, son
  consecuencia directa de la lógica de salida): `avg_win` monótonamente
  no-decreciente en `max_hold` en 12/12 contextos, `timeout_frac`
  monótonamente no-creciente en 12/12, `wr` no-creciente en 10/12 —
  coherente con "más tiempo de holding permite que los ganadores se
  desarrollen más, a costa de que más operaciones marginales reviertan
  antes del timeout" (mismo tipo de trade-off ya visto en H2.2 con
  `activation`). Estos patrones mecánicos son consecuencias observadas del
  mecanismo de gestión, no la conclusión principal del cierre.
- **Determinación**: hipótesis de Espacio 2 (`max_hold`) **falsificada
  bajo el contrato experimental evaluado** — ningún activo supera los 4
  gates en 2022 Y 2023 bajo ninguna combinación (`max_hold`, sesión),
  dentro de esta configuración exacta (Gestión V3-A completa salvo
  `max_hold`, `atr_mult`=1.5, `atr_period`=14 fijo, Trigger=`T1_ema_cross`,
  sesiones `control_8h`/`dcv1_activo_15h`). El 100% de las filas candidatas
  (47/47) fue computable — la forma más fuerte de falsificación
  ("falsificación con muestra ya computable") vista hasta ahora en el
  programa. Esto no generaliza que `max_hold` sea irrelevante en términos
  absolutos: otra Gestión, otro trigger, u otra combinación de sesión
  podrían producir un resultado distinto y quedan fuera del alcance de lo
  que este contrato evaluó.
- **Limitaciones y observaciones secundarias**: (1) el mecanismo de `freq`
  quedó confirmado en dirección pero no en magnitud suficiente — no
  descarta que un rango de `max_hold` más extremo (fuera de la grilla
  5-40 probada) pudiera cruzar el gate, algo que este contrato no evaluó;
  (2) `atr_period` permanece sin caracterizar, no por hallazgo negativo
  sino por una limitación estructural del pipeline de investigación
  vigente, documentada como iniciativa de infraestructura separada; (3)
  las asociaciones de dirección PF-`max_hold` por activo y los patrones
  mecánicos de `avg_win`/`wr`/`timeout_frac` se reportan como evidencia
  descriptiva, explícitamente no como explicaciones causales ni como
  fundamento para promover ningún valor de `max_hold`.
- **Estado**: **CERRADO** (2026-08-10). No se continuará explorando este
  espacio experimental bajo el contrato actual. Reabrir `max_hold` bajo
  otra Gestión, otro trigger, u otro rango de grilla requeriría un
  contrato nuevo explícitamente propuesto y aprobado. Este cierre no
  reabre ni reinterpreta ninguna conclusión de H1, H2, I1 o Espacio 3.

### Espacio 4 — Entry (Capa 3) bajo `T1_ema_cross` — cerrado

Espacio 4, tal como fue planteado en `docs/research/EXPERIMENTAL_ROADMAP.md`
("`A_pullback_50` bajo `T1_ema_cross`"), se cierra **sin ejecutar ninguna
campaña nueva**: la auditoría de 2026-08-10 encontró que (a) la comparación
computable bajo T1 (`C_market_close` vs `D_next_candle_open`) ya está
corrida con datos reales desde 2026-07-27 (`scripts/entry_campaign_t1.py`,
commits `9588277`/`487beb8`), nunca formalizada en este documento, y (b)
`A_pullback_50` no es computable bajo `T1_ema_cross` con su definición
vigente — un hallazgo estructural, no un resultado experimental.

- **Qué parte del espacio fue realmente evaluada**: únicamente la
  sub-pregunta "¿el timing de ejecución a mercado (cierre de la vela de
  señal vs. apertura de la vela siguiente) importa bajo `T1_ema_cross`?" —
  los dos únicos candidatos de Entry agnósticos al candidato de Capa 2
  (`research/layers.py`: `entry_C_market_close`, `entry_D_next_candle_open`).
  La sub-pregunta "¿esperar un retroceso antes de entrar cambia algo bajo
  T1?" — la que motivaba originalmente incluir `A_pullback_50` — **no fue
  evaluada**, por la incompatibilidad estructural descrita abajo.
- **Verificación independiente de la evidencia histórica**:
  `entry_campaign_t1_results.csv`/`_decision.csv` (24 y 12 filas)
  reauditados sin confiar en `gate_pass` ni en la decisión ya publicada.
  `gate_check` recalculado desde métricas crudas sobre las 24 filas: 0
  mismatches. `summarize_decision` recalculado independientemente: 0
  diferencias contra la decisión publicada, 0 sobrevivientes confirmados.
  Verificación adicional, no presente en el script original (anterior al
  patrón de Fase A introducido con I1): las 6 filas `C_market_close`/`V3-A`
  coinciden EXACTO, 0 mismatches, con las filas `T1_ema_cross`/`V3-A` ya
  publicadas en `trigger_campaign_results.csv` (script independiente,
  misma computación). Suite estructural
  (`research/tests/test_entry_campaign_t1.py`): 3/3 pasan.
- **Qué quedó demostrado**: con datos reales, `C_market_close` y
  `D_next_candle_open` muestran comportamiento prácticamente indiferente
  bajo `T1_ema_cross` — diferencia de PF entre ambos de 0.000 a 0.135 en
  los 12 combos (activo×año×exit_config), mediana 0.0005; `freq` idéntico
  entre ambos en cada fila. 0/24 filas superan los 4 gates; ningún activo
  sobrevive 2022 Y 2023 bajo ninguno de los dos candidatos. Esto demuestra
  indiferencia dentro del conjunto evaluado (ejecución inmediata, dos
  variantes de timing de ≤1 vela) — no que "el Entry no importa bajo T1"
  en términos generales.
- **Qué quedó abierto**: si un mecanismo de entrada cualitativamente
  distinto de la ejecución inmediata a mercado — específicamente, esperar
  un retroceso antes de entrar — cambiaría el comportamiento bajo
  `T1_ema_cross`. No hay evidencia directa en ningún sentido; es un hueco
  de diseño genuino, no una hipótesis ya puesta a prueba y sin resolver.
  Esta celda ("Entry de retroceso bajo T1") no forma parte de ningún
  espacio experimental actualmente aprobado.
- **Por qué `A_pullback_50` no puede considerarse un resultado negativo**:
  `entry_A_pullback_50` (`research/layers.py:282-304`) lee
  `event.meta["bos_level"]`/`swing_low`/`swing_high` — campos que produce
  únicamente `trigger_A_sweep_bos`. `trigger_T1_ema_cross` emite
  `TriggerEvent(..., meta={})` siempre — invocar `entry_A_pullback_50`
  sobre un evento de T1 lanza `KeyError`, no calcula un PF bajo. No hay
  corrida, no hay métrica, no hay gate evaluado — es una incompatibilidad
  de definición (el candidato depende semánticamente de niveles de
  sweep/BOS que un cruce de EMA no produce), verificada en código y ya
  documentada, antes de este roadmap, en `scripts/trigger_campaign.py` y
  en el propio `scripts/entry_campaign_t1.py`. Tratarlo como "falsificado"
  atribuiría al candidato una derrota empírica que nunca ocurrió.
- **Por qué no corresponde inventar una variante**: diseñar una fórmula de
  "pullback" nueva para eventos de cruce EMA (ej. sobre el rango de la
  vela de cruce o una referencia ATR) dejaría de ser una prueba de
  `A_pullback_50` — sería un candidato de Capa 3 distinto, con su propio
  mecanismo, su propia justificación científica y su propio contrato, no
  una extensión mecánica de lo ya definido. Motivado únicamente por
  completar una celda de la matriz Trigger×Entry, sería exactamente el
  tipo de diseño ad hoc que este programa ha evitado en cada campaña
  anterior (mismo principio que impidió promover candidatos nunca
  validados por gates en H2/I1).
- **Determinación**: Espacio 4 cerrado como espacio experimental bajo el
  contrato/alcance aprobado, con evidencia parcial sobre Entry bajo T1 y
  una incompatibilidad estructural no resuelta de `A_pullback_50`; **no se
  falsifica la hipótesis general sobre Entry**.
- **Implicaciones para el roadmap**: la matriz Trigger×Entry bajo
  `T1_ema_cross` queda con una celda genuinamente vacía (Entry de
  retroceso), no una celda ya explorada y descartada — cualquier interés
  futuro en esa pregunta requeriría diseñar un candidato nuevo desde cero,
  con su propio contrato, no reabrir este cierre. No cambia nada de lo ya
  cerrado en H1/H2/I1/Espacio 3/Espacio 2.
- **Estado**: **CERRADO** (2026-08-10), sin campaña nueva ejecutada —
  cierre basado en auditoría de evidencia histórica ya publicada más un
  hallazgo estructural verificado en código. Este estado significa que el
  espacio tal como fue definido no requiere más trabajo — NO significa que
  "la cuestión de Entry bajo T1 quedó completamente resuelta": la celda de
  Entry de retroceso permanece abierta, fuera del alcance de este cierre.

### `atr_mult` × sesión (extensión residual de H1) — cerrado

Bloque independiente, NO parte de los cuatro espacios de `docs/research/
EXPERIMENTAL_ROADMAP.md` — explícitamente no una reapertura de Espacio 1
(Gestión multivariable) ni de Espacio 2 (`max_hold`, cerrado). Contrato
acordado 2026-08-11, motivado porque H1 (`atr_mult` ∈ {1.0, 1.5(ancla), 2.0,
3.0}, cerrado, `gestion_campaign_atr_mult_results.csv`) solo se había
probado bajo `control_8h`, y el PF máximo de todo el programa hasta esa
fecha (1.567, SOLUSDT/2023, `atr_mult`=3.0) estaba bloqueado
exclusivamente por frecuencia — la única celda de `atr_mult` bajo
`dcv1_activo_15h` que ningún bloque anterior había tocado.

- **Objetivo e hipótesis primaria**: `atr_mult`=3.0 × `dcv1_activo_15h`
  supera los 4 gates de FRAMEWORK.md en 2022 Y 2023 para al menos un
  activo — motivada por el PF=1.567 de H1, no evidencia de edge en sí
  misma. Grid secundario preespecificado, no motivador: `atr_mult` ∈
  {1.0, 1.5, 2.0} × `dcv1_activo_15h`, mismo protocolo y gates.
- **Contrato**: Bias=A/Trigger=`T1_ema_cross`/Entry=`C_market_close`/
  Gestión V3-A única (`be`=1.0R/`activation`=2.0R/`distance`=1.0R)/
  `atr_period`=14/`max_hold`=20/`risk`=0.005 fijos. `control_8h` (24 filas)
  leído directamente de `gestion_campaign_atr_mult_results.csv` (H1), sin
  recomputar. `dcv1_activo_15h` (24 filas) computado con el código de hoy;
  `atr_mult`=1.5 en rol dual (celda de verificación + fila candidata,
  misma función, sin doble cómputo). Implementado en `scripts/
  gestion_campaign_atr_mult_session.py` (commit `a806d38`), resultados en
  `gestion_campaign_atr_mult_session_results.csv`/`_decision.csv`/
  `_deltas.csv` (commit `3630f4d`).
- **Verificación de integridad**: Fase A (12 verificaciones — 6 combos
  activo/año × 2 referencias independientes: `gestion_campaign_session_
  results.csv` y `gestion_campaign_max_hold_session_results.csv`, ambas
  ya coincidentes entre sí) más `assert_trigger_invariant_to_atr_mult`
  (H1, reutilizada literal) sobre el frame de `dcv1_activo_15h`.
  Auditoría independiente completa (2026-08-12): Fase A 12/12 exactas;
  `gate_check` recalculado sobre las 24 filas candidatas, 0 mismatches;
  `summarize_decision` recalculado, 0 mismatches contra las 12 filas de
  `_decision.csv`; `compute_deltas` recalculado, 0 mismatches contra las
  24 filas de `_deltas.csv`; sin contaminación de Bias/Trigger/Entry/
  Gestión/`atr_period`/`max_hold`/`risk` verificada en código; 27/27 tests
  de `research/tests/test_gestion_campaign_atr_mult_session.py` pasan.
  Dictamen de auditoría: **APTO para análisis científico**.
- **Resultados**: **la hipótesis primaria (`atr_mult`=3.0 ×
  `dcv1_activo_15h`) no está respaldada** — 0/6 celdas cumplen los 4
  gates; `max_dd`/`freq` pasan 6/6, `exp_r` 4/6, **`pf`≥1.50 0/6**.
  `ΔPF` (dcv1 − control) negativo en 4/6 celdas. La celda histórica que
  motivó la hipótesis (SOLUSDT/2023) tampoco reproduce el PF requerido
  bajo `dcv1_activo_15h`: 1.408 < 1.50. El grid secundario tampoco
  produce ninguna celda que cumpla los 4 gates (0/18). Sobre las 24 filas
  candidatas completas (los 4 valores de `atr_mult`): **0/24 alcanzan
  `pf`≥1.50** — de hecho, 0 de las 12 combinaciones candidatas
  (4 `atr_mult` × 3 activos) alcanzan `pf`≥1.50 siquiera en un solo año
  aislado. `dcv1_activo_15h` sí resuelve el gate de frecuencia de forma
  consistente: **24/24 filas candidatas dentro de [6,12]**, con `Δfreq`
  positivo en las 24/24 filas (rango +3.2 a +5.0/mes) — efecto
  independiente de `atr_mult`. Ningún activo sobrevive 2022 Y 2023 bajo
  ningún valor de `atr_mult` (`survives_both_years`=False en las 12
  filas de la decisión).
- **Análisis**: cambiar `atr_mult` entre 1.0 y 3.0 bajo `dcv1_activo_15h`
  no produce el salto de PF necesario para cruzar el gate en ninguna
  combinación — el `ΔPF` medio por valor de `atr_mult` (1.0: −0.069; 1.5:
  −0.005; 2.0: −0.017; 3.0: −0.039) no muestra a la hipótesis primaria
  como la de mejor preservación relativa de PF; ese lugar lo ocupa
  `atr_mult`=1.5 (réplica, no la hipótesis primaria). La dirección
  2022→2023 del PF es consistente dentro de cada activo (ETHUSDT baja en
  los 4 valores; SOLUSDT sube en los 4; BTCUSDT sube en 3 de 4, con
  `atr_mult`=3.0 como única excepción) — observación descriptiva, sin
  atribución de causa a `atr_mult` ni a régimen de mercado, mismo
  estándar que el resto del programa.
- **Comparaciones múltiples**: se evaluaron 12 combinaciones candidatas
  (4 `atr_mult` × 3 activos). Este riesgo **existe**, pero **no altera la
  conclusión de esta campaña porque ningún candidato alcanzó el criterio
  de aceptación** (supervivencia 2022+2023) — el mejor resultado
  observado (SOLUSDT/`atr_mult`=3.0/2023, PF=1.408) no se interpreta como
  evidencia confirmatoria aislada; es, dentro de 12 comparaciones
  simultáneas, el máximo esperable por muestreo sobre esa cantidad de
  combinaciones, no una señal validada por `gate_check`/
  `summarize_decision`.
- **Contabilidad de la evidencia**: de las 48 filas totales, 24 son
  lectura histórica de H1 (`control_8h`, sin recómputo, no evidencia
  nueva), 6 son réplica/verificación de una celda ya publicada
  (`atr_mult`=1.5 × `dcv1_activo_15h`, no evidencia nueva) y **18 son
  evidencia genuinamente nueva** (`atr_mult` ∈ {1.0, 2.0, 3.0} ×
  `dcv1_activo_15h` × 3 activos × 2 años) — 6 de esas 18 corresponden a
  la hipótesis primaria, 12 al grid secundario preespecificado.
- **Determinación**: hipótesis primaria (`atr_mult`=3.0 ×
  `dcv1_activo_15h`) **no respaldada bajo el contrato experimental
  evaluado**; grid secundario sin ninguna combinación que cumpla los 4
  gates tampoco. `dcv1_activo_15h` resuelve el gate de frecuencia de
  forma robusta e independiente de `atr_mult`, pero el gate de PF
  permanece universalmente cerrado bajo esta configuración exacta — mismo
  patrón ya visto en I1 y Espacio 2. Esto no generaliza que `atr_mult`
  sea irrelevante en términos absolutos, ni reabre H1, Espacio 1 o
  Espacio 2 — queda fuera del alcance de lo que este contrato evaluó.
- **Estado**: **CERRADO** (2026-08-12). No se continuará explorando esta
  celda residual bajo el contrato actual. Reabrirla bajo otro rango de
  `atr_mult`, otra Gestión, u otro trigger requeriría un contrato nuevo
  explícitamente propuesto y aprobado. Este cierre no reabre ni
  reinterpreta ninguna conclusión de H1, H2, I1, Espacio 2, Espacio 3 o
  Espacio 4.

### Espacio 1 — Gestión multivariable (`distance` × `activation` × `be` simultáneos) — cerrado

Último de los cuatro espacios del orden aprobado (Espacio 3 → Espacio 2 →
Espacio 4 → Espacio 1, `docs/research/EXPERIMENTAL_ROADMAP.md`). Contrato
acordado 2026-08-13 (versión final, tras 2 correcciones metodológicas
explícitas: contabilidad de evidencia nueva vs. réplica, y terminología
del punto V3-A como "ancla/referencia interna" en vez de "control", dado
que esta campaña corre bajo una sola sesión, sin brazo de comparación bajo
otra).

- **Objetivo e hipótesis**: H2.1/H2.2/H2.3 e I1-distance/I1-activation/
  I1-be barrieron `distance`/`activation`/`be` de a uno a la vez (156
  filas candidatas de I1, 0 con `gate_pass`, máximo PF 1.476) — ninguna
  campaña anterior había probado si una combinación *conjunta* de los 3
  parámetros produce una interacción que ninguno muestra por separado.
  Hipótesis de familia, sin combinación motivadora individual (a
  diferencia de `atr_mult`=3.0 en la campaña anterior): existe al menos
  una combinación (`distance`, `activation`, `be`) del grid de 36 que,
  bajo Bias=A/Trigger=`T1_ema_cross`/Entry=`C_market_close`/`atr_mult`=1.5/
  `atr_period`=14 (excluido, Espacio 2)/`max_hold`=20 (fijo, Espacio 2)/
  `risk`=0.005 (excluido, Espacio 2)/sesión=`dcv1_activo_15h` única fijos,
  supera los 4 gates de FRAMEWORK.md en 2022 Y 2023 para al menos un
  activo.
- **Contrato**: grid `distance` ∈ {0.5, 0.75, 1.0, 1.5} (base H2.1) ×
  `activation` ∈ {1.5, 2.0, 2.5} (base H2.2) × `be` ∈ {0.5, 1.0, 1.5}
  (base H2.3) = 36 combinaciones, sin extensiones por contingencia ni el
  conjunto no-dominado de I1 — grid deliberadamente acotado a las grillas
  base de H2 para no ampliar el riesgo de comparaciones múltiples. El
  punto ancla V3-A (`distance`=1.0/`activation`=2.0/`be`=1.0) está dentro
  del grid, con `role="anchor"` (nunca marcado como hipótesis primaria).
  Solo `dcv1_activo_15h` — decisión explícita de no correr también
  `control_8h`, ya caracterizado como estructuralmente incapaz de resolver
  frecuencia; sin brazo de control bajo otra sesión, esta campaña no
  calcula ΔPF/Δfreq. Implementado en `scripts/gestion_campaign_
  multivariable.py` (commit `3b1f843`), resultados en `gestion_campaign_
  multivariable_results.csv`/`_decision.csv` (commit `bf2de24`).
- **Contabilidad de evidencia**: de las 216 filas candidatas físicas (36
  combinaciones × 3 activos × 2 años), 42 (7 combinaciones × 6
  activo/año — el ancla + los 2 bordes univariados de cada uno de los 3
  parámetros) son réplica/verificación, no evidencia nueva; **174 son
  evidencia genuinamente nueva** (29 combinaciones × 6 activo/año). 6
  filas tienen `role="anchor"`, 210 `role="candidate"`.
- **Verificación de integridad (Fase A)**: 48 verificaciones — ancla
  contra 2 referencias independientes (`gestion_campaign_session_
  results.csv` e `integration_campaign_activation_results.csv`, 6×2=12),
  `distance` sola contra `integration_campaign_distance_results.csv`
  (6×2=12), `activation` sola contra `integration_campaign_
  activation_results.csv` (6×2=12), `be` sola contra `integration_
  campaign_be_results.csv` (6×2=12). Reproducida de forma independiente
  antes de aceptar cualquier resultado: **48/48 coincidencias exactas, 0
  mismatches**. `gate_check` recalculado desde métricas crudas sobre las
  216 filas candidatas: 0 mismatches. `summarize_decision` recalculado
  independientemente sobre las 108 filas de decisión: 0 mismatches.
  Integridad de commit verificada por hash: `git hash-object` de ambos CSV
  en el working tree coincide exacto con los blobs de `git ls-tree
  bf2de24` (`gestion_campaign_multivariable_results.csv` =
  `e351a01524d49fc1c25580569948fc916e2b5b4f`, `gestion_campaign_
  multivariable_decision.csv` = `f57a919a46da96ffd92d4fd0ee4837923eeeb8e2`).
  Dictamen de auditoría técnica: **PASS**.
- **Resultados**: de las 216 filas candidatas, **`pf`≥1.50 en 0/216** — el
  gate universalmente vinculante vuelve a ser PF, mismo patrón que I1 y
  Espacio 2. `max_dd`≥-10% pasa en 168/216, `exp_r`>0 en 144/216,
  frecuencia en [6,12] en **216/216** (sesión `dcv1_activo_15h` resuelve
  frecuencia de forma consistente, igual que en toda campaña bajo esta
  sesión). Máximo PF observado en las 216 filas: **1.498** (SOLUSDT,
  2023). Ningún activo sobrevive 2022 Y 2023 bajo ninguna de las 36
  combinaciones (`survives_both_years`=False en las 108 filas de la
  decisión).
- **Determinación**: hipótesis de Espacio 1 (interacción multivariable
  `distance`×`activation`×`be`) **falsificada bajo el contrato
  experimental evaluado** — ninguna de las 36 combinaciones supera los 4
  gates en 2022 Y 2023 para ningún activo, bajo esta configuración exacta
  (Bias=A/Trigger=`T1_ema_cross`/Entry=`C_market_close`/`atr_mult`=1.5/
  `max_hold`=20/sesión=`dcv1_activo_15h` única). Esto no generaliza que
  una interacción de estos 3 parámetros sea imposible en términos
  absolutos, ni bajo otro trigger, sesión o rango de grid — queda fuera
  del alcance de lo que este contrato evaluó.
- **Estado**: **CERRADO** (2026-08-17). No se continuará explorando este
  espacio bajo el contrato actual. Reabrirlo bajo otro grid, otra sesión,
  u otro trigger requeriría un contrato nuevo explícitamente propuesto y
  aprobado. Este cierre no reabre ni reinterpreta ninguna conclusión de
  H1, H2, I1, Espacio 2, Espacio 3, Espacio 4 o `atr_mult` × sesión. **Con
  este cierre, los cuatro espacios del orden aprobado en `docs/research/
  EXPERIMENTAL_ROADMAP.md` (Espacio 3 → Espacio 2 → Espacio 4 → Espacio 1)
  quedan completos.**

### Rama B — Trigger/Entry — cerrado

Línea de investigación posterior a los cuatro espacios de arriba, **no uno
de ellos ni una extensión residual de H1** (a diferencia de `atr_mult` ×
sesión) — surgida de una revisión estratégica global del programa
(2026-08-18) que identificó Trigger/Entry (Capa 2/Capa 3) como la línea de
mayor valor de información esperado entre las alternativas consideradas en
esa revisión. **Nota de trazabilidad**: esa revisión estratégica y su
análisis formal de valor de información no están documentados en ningún
archivo de este repositorio a la fecha de este cierre — la justificación
completa de por qué se priorizó esta línea existe únicamente como decisión
de sesión de trabajo, no como documento versionado. Ver la ambigüedad
señalada en `docs/research/EXPERIMENTAL_ROADMAP.md` sobre cómo esta línea
se relaciona formalmente con Espacio 5/Espacio 6.

- **Objetivo e hipótesis**: evaluar si el techo de PF (~1.0-1.5) observado
  en las líneas experimentales previas del programa (H1, H2.1-H2.3, I1,
  Espacio 3, Espacio 2, `atr_mult`×sesión, Espacio 4, Espacio 1) es
  específico del par Trigger/Entry vigente en la mayoría de ellas
  (`T1_ema_cross`/`C_market_close` — Espacio 3 es la excepción, con
  Trigger=`A_sweep_bos` fijo), o transversal. Dos celdas evaluadas, sin celda
  `D_range_breakout`+`A_pullback_50` — incompatibilidad estructural:
  `entry_A_pullback_50` requiere `event.meta["bos_level"]`, que
  `trigger_D_range_breakout` no produce (`meta={}` siempre), mismo tipo de
  incompatibilidad ya documentado para T1 en el cierre de Espacio 4:
  - `D_range_breakout` (Capa 2, candidato "D" de la lista de arriba, nunca
    implementado hasta esta campaña) + `C_market_close` — aísla el efecto
    de Trigger.
  - `A_sweep_bos` + `A_pullback_50` — aísla el efecto de Entry.
- **Contrato**: Bias=A/Gestión V3-A ancla (`be`=1.0R/`activation`=2.0R/
  `distance`=1.0R)/`atr_mult`=1.5/`atr_period`=14/`max_hold`=20/
  `risk`=0.005/sesión=`dcv1_activo_15h` única fijos, BTCUSDT/ETHUSDT/
  SOLUSDT, 2022+2023 (2024 no ejecutado). Implementado en `scripts/
  trigger_entry_campaign_rama_b.py` (commit `3f07f10`, junto con
  `trigger_D_range_breakout` en `research/layers.py`), resultados en
  `trigger_entry_campaign_rama_b_results.csv`/`_decision.csv` (commit
  `c03a82d6c3d5ef5161f1d6946f958a02b5223911`).
- **Verificación de integridad (Fase A)**: ninguna de las 2 celdas
  objetivo tiene antecedente histórico bajo ninguna sesión — se verificó
  en su lugar el pipeline compartido por ambas, vía la celda auxiliar
  `A_sweep_bos`+`C_market_close` bajo `dcv1_activo_15h`, contra la
  referencia ya publicada de Espacio 3 (`trigger_campaign_sweep_bos_
  session_results.csv`). 6 verificaciones (una por activo/año),
  comparación NaN-consciente (ETHUSDT/2023 no computable en la
  referencia). Auditoría independiente: **PASS** — cardinalidad 12/12
  filas de resultados (2 combinaciones × 3 activos × 2 años), 6/6 filas de
  decisión, sin 2024 en ningún registro, hash de ambos CSV en el working
  tree coincide exacto con `git ls-tree c03a82d6c3d5ef5161f1d6946f958a02b5223911`
  (`trigger_entry_campaign_rama_b_results.csv` =
  `aa4fadfda6ff3e60639253e944a62924a54bcabb`, `trigger_entry_campaign_
  rama_b_decision.csv` = `0da981872f2c722aa3f259a8e2eb18b1c6d91dde`),
  `git status` limpio y `HEAD == origin/main` en el momento de la
  auditoría. `gate_check`/`summarize_decision` reutilizados por identidad
  desde `scripts/bias_campaign.py`, sin reimplementar.
- **Resultados y determinación por combinación**:
  - **`D_range_breakout + C_market_close` → DESCARTADA.** PF entre 0.676
    y 1.250 en las 6 celdas (media 0.938), por debajo del gate en las
    6/6; `exp_r`>0 solo en 2/6; `max_dd`≥-10% solo en 2/6; frecuencia por
    encima del techo de 12/mes en las 6/6 (15.6-17.9/mes). Evidencia
    estadísticamente sólida (1202 trades acumulados, sin celda extrema
    aislada) de calidad de señal insuficiente bajo este contrato.
  - **`A_sweep_bos + A_pullback_50` → CANDIDATA CONGELADA / EVIDENCIA
    INSUFICIENTE.** PF entre 10.293 y 50.935 en las 5 celdas computables
    (`exp_r`>0 y `max_dd`≥-10% en las 5/5), pero frecuencia entre 0.5 y
    1.6/mes — muy por debajo del piso de 6/mes en las 5/5 celdas
    computables, incompatible con el gate de frecuencia. Celda
    `ETHUSDT/2023` no computable (`n_trades`=4, por debajo del piso de 5
    de `backtest.metrics()`) — no cuenta como evidencia a favor ni en
    contra. No se descarta (el patrón de PF alto es consistente y se
    replicó bajo un segundo régimen de sesión distinto de su único
    antecedente previo bajo `control_8h`), pero tampoco se promueve: la
    baja frecuencia se evaluó como estructural (análisis conceptual, sin
    campaña adicional), no resoluble aumentando años o activos dentro del
    contrato actual. **Esta combinación no debe investigarse de nuevo bajo
    el contrato actual únicamente para intentar rescatar su PF o aumentar
    artificialmente su frecuencia** — reabrirla exigiría un contrato
    nuevo (otra sesión, Trigger, Entry o Gestión) explícitamente propuesto
    y aprobado, tratado como experimento distinto, no como extensión de
    este cierre.
- **Gate (Nivel 4)**: **0/12 filas cumplen los 4 gates de FRAMEWORK.md.**
  Ninguna combinación fue elegible para prueba ciega en 2024 —
  `run_blind_test` no fue invocado en ningún momento de esta campaña.
- **Estado**: **CERRADO** (2026-08-18). No se continuará esta línea bajo
  el contrato actual.

El plan experimental completo post-cierre I1 (los cuatro espacios
evaluados en la sesión de planificación de 2026-08-08, el orden de
exploración aprobado y su justificación por valor de información
esperado/costo/riesgo, y el estado vivo del programa) se documenta en
`docs/research/EXPERIMENTAL_ROADMAP.md` — no se repite acá para no
duplicar contenido; este documento mantiene el registro retrospectivo por
campaña cerrada, aquel mantiene el mapa prospectivo de qué sigue.

### Bias B — EMA50+EMA200 4H (cruce) — cerrado

Sub-candidato de Espacio 5 (`docs/research/EXPERIMENTAL_ROADMAP.md`,
"Estado de priorización — Espacio 5"), evaluado con datos reales contra el
comparador Bias A bajo el mismo contrato exacto — mismo diseño que Rama B
(celda objetivo sin antecedente, verificada vía celda auxiliar).

- **Objetivo e hipótesis**: bajo un contrato idéntico en todo lo demás
  (Trigger=`T1_ema_cross`, Entry=`C_market_close`, sesión=`dcv1_activo_15h`,
  Gestión V3-A ancla, `atr_mult`=1.5/`atr_period`=14/`max_hold`=20/
  `risk`=0.005 fijos), ¿el filtro de contexto HTF por cruce de medias
  (`sign(EMA50_4H−EMA200_4H)`, sin zona neutral) produce métricas distintas
  de las del filtro de distancia a un solo nivel de EMA200 con zona neutral
  ±1% (Bias A)? Bias es la única variable experimental.
- **Contrato**: implementado en `scripts/bias_b_campaign.py` (commit
  `1f91b0205aeb6c743b4e00410d8cc998d34843d4`), resultados en
  `bias_b_campaign_results.csv`/`_decision.csv` (commit
  `7edd1914ab5573ecaae6dca385b87e20ae60053f`). BTCUSDT/ETHUSDT/SOLUSDT,
  2022+2023 (2024 no ejecutado).
- **Verificación de integridad (Fase A)**: la celda objetivo (Bias B) no
  tiene antecedente histórico — se verificó el pipeline compartido vía la
  celda auxiliar Bias A bajo este contrato exacto, contra la referencia ya
  publicada (`gestion_campaign_session_results.csv`, `candidate=
  "dcv1_activo_15h"`, `exit_config="V3-A (1R/2R/1R)"`). 6 verificaciones (una
  por activo/año). Ejecutada en el entorno local del usuario al generar
  estos resultados — no reproducida en este sandbox (bloqueado, HTTP 451,
  `data/raw/` no poblado). Hash de los CSV committeados verificado contra
  `git ls-tree 7edd191`: `bias_b_campaign_results.csv` =
  `4bd5e0c68e68421dd4207e8169b8a36421e56ee6`, `bias_b_campaign_decision.csv`
  = `34a820e4f83943f006e167834855dd098347b343`; recómputo independiente de
  `gate_check`/`survives_both_years` celda por celda coincide exacto con lo
  publicado.
- **Resultados por celda** (n_trades / freq mensual / PF / MaxDD / exp_r):

  | Activo | Año | n_trades | freq | PF | MaxDD | exp_r |
  |---|---|---|---|---|---|---|
  | BTCUSDT | 2022 | 125 | 10.5 | 0.683 | -13.46% | -0.179 |
  | BTCUSDT | 2023 | 135 | 11.2 | 1.077 | -9.22% | +0.041 |
  | ETHUSDT | 2022 | 119 | 10.0 | 0.983 | -6.52% | -0.009 |
  | ETHUSDT | 2023 | 144 | 12.0 | 0.674 | -18.36% | -0.190 |
  | SOLUSDT | 2022 | 118 | 9.9 | 1.025 | -6.34% | +0.012 |
  | SOLUSDT | 2023 | 111 | 9.3 | 1.287 | -5.27% | +0.139 |

- **Comparación B vs A (mismo contrato exacto, comparador:
  `gestion_campaign_session_results.csv`)**:
  - Disponibilidad de señal: B produce más entradas que A en las 6/6
    celdas (+10 a +31 entradas/activo-año) — consistente con la ausencia
    de zona neutral en la fórmula de B, a diferencia de la banda ±1% de A.
    Efecto uniforme, no dependiente de activo/régimen.
  - Calidad de señal (PF/exp_r/MaxDD): no mejora de forma consistente pese
    al aumento de disponibilidad. El efecto sobre PF es dependiente del
    activo — mejora marginal y estable en BTCUSDT (ΔPF +0.002/+0.056) y
    SOLUSDT (ΔPF +0.022/+0.015); deterioro consistente y de mayor
    magnitud en ETHUSDT (ΔPF −0.050/−0.108), incluyendo el peor MaxDD del
    conjunto comparado (ETHUSDT/2023, −18.36% bajo B frente a −12.44% bajo
    A).
  - Ninguno de los dos Bias produce ninguna celda con PF≥1.50 bajo este
    contrato — PF es el gate limitante en ambos, sin excepción.
- **Gate (Nivel 4)**: **0/6 filas cumplen los 4 gates de FRAMEWORK.md.**
  Ningún activo sobrevive 2022 Y 2023 (`survives_both_years=False` en las
  3 filas de `bias_b_campaign_decision.csv`). Ninguna combinación fue
  elegible para prueba ciega en 2024 — `run_blind_test` no fue invocado.
- **Interpretación (alcance limitado a este contrato)**: no hay evidencia
  suficiente, bajo el contrato evaluado, para sostener que sustituir Bias
  A por Bias B mejore estructuralmente el sistema — el único efecto
  uniforme observado (mayor disponibilidad de señal) no viene acompañado
  de una mejora uniforme de calidad. El resultado es consistente con —
  sin demostrarlo de forma aislada, dado que es una sola línea de
  evidencia — la hipótesis de que Bias no es el cuello de botella
  dominante del framework bajo el Trigger/Entry/Gestión evaluados hasta
  ahora, y que PF/calidad de señal sí lo es.
- **Estado**: **CERRADO** (evidencia real, 2022+2023). No se continuará
  esta celda bajo el contrato actual. Bias C (Espacio 5, empatado con
  Bias B en el criterio de priorización de 2026-08-19) permanece sin
  evaluar.

### Trigger C — BOS-only — cerrado

Sub-candidato de Espacio 5, priorizado #1 en el checkpoint de
2026-08-19 por criterios exclusivamente ex ante (`docs/research/
EXPERIMENTAL_ROADMAP.md`, "Estado de priorización — Espacio 5") —
evaluado con datos reales contra el comparador `A_sweep_bos` bajo el
mismo contrato exacto. Mismo diseño que Rama B y Bias B (celda objetivo
sin antecedente, verificada vía celda auxiliar).

- **Objetivo e hipótesis**: bajo un contrato idéntico en todo lo demás
  (Bias=A, Entry=`C_market_close`, sesión=`dcv1_activo_15h`, Gestión
  V3-A ancla, `atr_mult`=1.5/`atr_period`=14/`max_hold`=20/`risk`=0.005
  fijos), ¿eliminar el requisito de Liquidity Sweep y usar únicamente
  BOS como Trigger (`trigger_C_bos_only`, ablación demostrable de
  `trigger_A_sweep_bos` — Eventos(A) ⊆ Eventos(C)) permite aumentar la
  disponibilidad de señales sin destruir la calidad de la señal?
  Trigger es la única variable experimental.
- **Contrato**: implementado en `research/layers.py`
  (`trigger_C_bos_only`) y `scripts/trigger_c_campaign.py` (commit
  `bbd4409a22453fce989b447a00570b011ad02077`), resultados en
  `trigger_c_campaign_results.csv`/`_decision.csv` (commit
  `787c91ad2de0d0f0b72600f331358386b5d8a75e`). BTCUSDT/ETHUSDT/SOLUSDT,
  2022+2023. **2024/prueba ciega NO ejecutada** — `run_blind_test` no
  fue invocado en ningún momento de esta campaña.
- **Comparador**: `A_sweep_bos` + `C_market_close` bajo el mismo
  contrato exacto (referencia ya publicada de Espacio 3,
  `trigger_campaign_sweep_bos_session_results.csv`, `candidate=
  "dcv1_activo_15h"`). `T1_ema_cross` y `D_range_breakout` son contexto
  únicamente, no comparadores válidos para esta hipótesis (familias de
  mecanismo distintas).
- **Verificación de integridad (Fase A)**: la celda objetivo (Trigger
  C) no tiene antecedente histórico bajo ninguna sesión — se verificó
  el pipeline compartido vía la celda auxiliar `A_sweep_bos`+
  `C_market_close` bajo `dcv1_activo_15h`, contra la referencia ya
  publicada de Espacio 3. 6 verificaciones (una por activo/año),
  comparación NaN-consciente. Hash de los CSV committeados verificado
  contra `git ls-tree 787c91a`: `trigger_c_campaign_results.csv` =
  `b168aa3663c038c96979bb0cc09ccf47e0db3e58`,
  `trigger_c_campaign_decision.csv` =
  `978edf0e5f98ea12456b17811d4c0c6ce69d6cc4`; recómputo independiente
  de `gate_check`/`survives_both_years` celda por celda coincide exacto
  con lo publicado.
- **Resultados por celda 2022+2023** (n_trades / freq mensual / PF /
  MaxDD / exp_r):

  | Activo | Año | n_trades | freq | PF | MaxDD | exp_r |
  |---|---|---|---|---|---|---|
  | BTCUSDT | 2022 | 307 | 25.4 | 0.893 | -13.41% | -0.056 |
  | BTCUSDT | 2023 | 276 | 22.8 | 1.408 | -4.76% | +0.213 |
  | ETHUSDT | 2022 | 297 | 24.6 | 1.138 | -7.86% | +0.067 |
  | ETHUSDT | 2023 | 278 | 23.2 | 0.990 | -11.57% | -0.005 |
  | SOLUSDT | 2022 | 284 | 23.7 | 1.125 | -8.58% | +0.055 |
  | SOLUSDT | 2023 | 289 | 24.0 | 0.944 | -12.94% | -0.028 |

- **Disponibilidad de señal y contraste con el comparador**: eliminar
  el requisito de sweep multiplica los eventos crudos ~80-100x
  (1067-1228 entradas/celda, frente a 4-17 bajo `A_sweep_bos`) y con
  ello la frecuencia efectiva — pero la dispara muy por encima del
  techo de 12/mes (22.8-25.4/mes) en las 6/6 celdas, en vez de resolver
  el déficit de frecuencia que motivaba la hipótesis. El PF del
  comparador (`A_sweep_bos`), estimado sobre n=4-17 trades por celda,
  no es una referencia estadísticamente fiable; el PF de Trigger C, ya
  sobre una muestra bien powered (276-307 trades/celda), converge al
  mismo rango 0.89-1.41 observado en el resto del programa.
- **Gate (Nivel 4)**: **0/6 filas cumplen los 4 gates de FRAMEWORK.md.**
  PF<1.50 en las 6/6 celdas (máximo 1.408); frecuencia por encima del
  techo de 12/mes en las 6/6 celdas (fallo por exceso, no por déficit —
  patrón inverso al de `A_sweep_bos`); `exp_r`>0 en 3/6; `max_dd`≥-10%
  en 2/6. Ningún activo sobrevive 2022 Y 2023
  (`survives_both_years=False` en las 3 filas de
  `trigger_c_campaign_decision.csv`). Ninguna combinación fue elegible
  para prueba ciega en 2024.
- **Interpretación (alcance limitado a este contrato)**: no hay
  evidencia, bajo el contrato evaluado, de que eliminar el requisito de
  sweep resuelva el problema de PF — lo desplaza de un fallo de
  frecuencia por defecto a uno por exceso, sin acercar el PF al gate.
  Constituye una cuarta línea de evidencia independiente (junto con
  Espacio 1, Espacio 2 y Bias B) consistente con — sin demostrarlo de
  forma aislada — la hipótesis de que el techo de PF observado (~0.9-1.5)
  es una propiedad del armazón de Gestión/ejecución bajo prueba, no de
  qué candidato específico de Bias o Trigger se utilice.
- **Estado**: **CERRADO** (evidencia real, 2022+2023). No se continuará
  esta celda bajo el contrato actual. Trigger B (Espacio 5, variación
  fina del mismo mecanismo de BOS) permanece sin evaluar.

### Espacio 6 — Experimento 1 — TP fijo 2.5R — cerrado

Primer experimento de Espacio 6 (pausa y reconsideración del armazón
completo, `docs/research/EXPERIMENTAL_ROADMAP.md`) — a diferencia de
Bias B/Trigger C (que varían Capa 1/2), este experimento aísla el
**mecanismo de Gestión/Exit Management** como única variable, manteniendo
Bias/Trigger/Entry/sesión/parámetros en su ancla ya usada en todo el
programa.

- **Objetivo e hipótesis**: bajo un contrato idéntico en todo lo demás
  (Bias=A/Trigger=`T1_ema_cross`/Entry=`C_market_close`/
  sesión=`dcv1_activo_15h`/`atr_mult`=1.5/`atr_period`=14/`max_hold`=20/
  `risk`=0.005 fijos), ¿el techo de PF (~0.9-1.5) observado en H1/H2/I1/
  Espacio 1/Bias B/Trigger C se debe al mecanismo de salida V3-A (SL
  inicial + breakeven + trailing + timeout), o persiste cuando se
  sustituye por un mecanismo genuinamente distinto? Variable
  experimental: el mecanismo de salida — TP fijo en 2.5R (SL inicial
  idéntico, sin breakeven, sin trailing, sin activación, timeout a
  `max_hold` sin cambios; precedencia intrabar conservadora: si SL y TP
  caen en la misma vela, gana SL). `TP_R`=2.5 es la especificación
  histórica de este mismo documento (sección "Gestión"), reutilizada
  como valor no arbitrario — explícitamente **no** una restauración de
  esa Gestión como mecanismo vigente (ver contrato formal, §0).
- **Contrato**: implementado en `scripts/gestion_espacio6_tp_fijo_
  campaign.py` (commit `d8223364cf814828420ee1a188684abb03221b60`),
  resultados en `gestion_espacio6_tp_fijo_campaign_results.csv`/
  `_decision.csv` (commit `550c21690fb63f26886dcb101b15b4a8c4aa602a`).
  BTCUSDT/ETHUSDT/SOLUSDT, 2022+2023 (2024 no ejecutado).
- **Fase A**: reproducción completa de V3-A (mismas entradas,
  `backtest.EXIT_CONFIGS["V3-A (1R/2R/1R)"]` sin modificar) verificada
  **6/6** contra `gestion_campaign_session_results.csv` (`candidate=
  "dcv1_activo_15h"`, `exit_config="V3-A (1R/2R/1R)"`) — coincidencia
  exacta en `n_entries`/`n_trades`/`pf`/`wr`/`exp_r`/`max_dd`/`freq` en
  las 6 combinaciones (activo, año); solo entonces se reutilizó el mismo
  objeto de entradas para TP fijo (Fase B).
- **Resultados por celda 2022+2023** (n_trades / freq / PF / MaxDD /
  exp_r):

  | Activo | Año | n_trades | freq | PF | MaxDD | exp_r |
  |---|---|---|---|---|---|---|
  | BTCUSDT | 2022 | 115 | 9.6 | 0.878 | -8.33% | -0.075 |
  | BTCUSDT | 2023 | 108 | 9.2 | 1.241 | -4.60% | +0.144 |
  | ETHUSDT | 2022 | 107 | 9.0 | 1.108 | -3.55% | +0.060 |
  | ETHUSDT | 2023 | 112 | 9.4 | 0.860 | -11.24% | -0.093 |
  | SOLUSDT | 2022 | 103 | 8.6 | 1.174 | -4.31% | +0.094 |
  | SOLUSDT | 2023 | 97 | 8.1 | 1.015 | -7.85% | +0.009 |

- **Comparación contra V3-A (deltas, mismo contrato exacto)**:

  | Activo/Año | ΔPF | ΔMaxDD (pp) | Δexp_r |
  |---|---|---|---|
  | BTCUSDT 2022 | +0.197 | +3.94 | +0.102 |
  | BTCUSDT 2023 | +0.220 | +2.28 | +0.132 |
  | ETHUSDT 2022 | +0.075 | +3.19 | +0.044 |
  | ETHUSDT 2023 | +0.078 | +1.20 | +0.026 |
  | SOLUSDT 2022 | +0.171 | +1.13 | +0.093 |
  | SOLUSDT 2023 | -0.257 | -2.63 | -0.123 |

  PF, MaxDD y exp_r mejoran simultáneamente en **5 de 6 celdas** (todo
  2022, más BTCUSDT/ETHUSDT 2023), con magnitud consistente entre
  celdas. La única excepción es SOLUSDT 2023 — la mejor celda jamás
  observada bajo V3-A en este contrato (PF=1.272) — que TP fijo arrastra
  al mismo rango que el resto. `Δfreq`/`Δn_trades` son prácticamente
  nulos: el mecanismo no cambia cuántas operaciones ocurren, solo cómo
  se cierran.
- **Distribución de razones de salida** (sin mezclar categorías): TP
  fijo produce `stop`/`tp`/`timeout` (48-55% / 17-29% / 23-33% de los
  trades por celda); V3-A produce únicamente `stop`/`timeout` (78-86% /
  14-22%). El "stop" de V3-A es heterogéneo (incluye salidas por
  trailing ya movido a favor, no solo pérdidas de -1R), mientras que el
  "stop" de TP fijo es homogéneo por construcción (siempre exactamente
  -1R bruto) — los porcentajes no son directamente comparables en
  magnitud pese a compartir el nombre de categoría.
- **Gate (Nivel 4)**: **0/6 filas cumplen los 4 gates de FRAMEWORK.md.**
  PF<1.50 en las 6/6 celdas (máximo 1.241, BTCUSDT 2023 — 0.259 por
  debajo del umbral); MaxDD≥-10% en 5/6 (falla solo ETHUSDT 2023);
  exp_r>0 en 4/6 (falla BTCUSDT 2022, ETHUSDT 2023); freq en rango en
  6/6. **0/3 activos sobreviven 2022 Y 2023**
  (`survives_both_years=False` en las 3 filas de
  `gestion_espacio6_tp_fijo_campaign_decision.csv`). Ninguna
  combinación fue elegible para prueba ciega en 2024.
- **"Mejora respecto de V3-A" vs. "PASS" (distinción explícita, no
  intercambiable)**: TP fijo mejora PF/MaxDD/exp_r de forma consistente
  en 5/6 celdas — una señal direccional real, no ruido disperso. Esto
  **no equivale** a pasar los gates: 0/6 celdas los cumple, 0/3 activos
  sobreviven ambos años. Mejora relativa y PASS son preguntas distintas
  con respuestas distintas en este experimento.
- **Interpretación (alcance limitado a este contrato, sin inferencia
  causal más allá de lo observado)**: el resultado no es compatible con
  "el mecanismo de salida es irrelevante" (H0 en su forma fuerte) — se
  observa una diferencia consistente y de magnitud estable en 5/6
  celdas al sustituir V3-A. Tampoco confirma que cambiar el mecanismo
  resuelva el problema (H1 fuerte) — ningún activo sobrevive ambos
  años. No se concluye que el breakeven/trailing de V3-A sea la causa
  del techo de PF — sería una inferencia causal no respaldada por un
  solo experimento comparativo; solo se documenta la asociación
  observada. La señal direccional consistente (a diferencia del
  resultado plano de Bias B y de la falla amplia de Trigger C) es
  evidencia de que la hipótesis de Espacio 6 —que el mecanismo de
  Gestión pueda importar— **no queda descartada por este resultado**;
  justifica mantener abierta esta línea, no cerrarla.
- **Veredicto**: **EVIDENCIA INSUFICIENTE** — 0/6 gate_pass, pero el
  patrón de falla es específico (en 4/6 celdas solo PF falla, con los
  otros 3 gates ya pasando) y no amplio (solo 2/6 celdas tienen más de
  un gate fallando) — no cumple el criterio contractual de FAIL ("varios
  gates fallando simultáneamente en la mayoría de las celdas").
- **Estado**: **CERRADO** (evidencia real, 2022+2023). Espacio 6
  permanece **abierto** — este resultado no cierra la hipótesis de
  Gestión. Un segundo experimento de Espacio 6 queda como posible
  siguiente paso, **no autorizado ni diseñado todavía**.

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
