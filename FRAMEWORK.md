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
- D: Apertura de vela siguiente al BOS — generalizado a "apertura de la vela
  siguiente al evento de Capa 2" (mismo criterio que C: no depende de qué
  candidato lo produjo). Implementado en
  `research.layers::entry_D_next_candle_open` (2026-07-27).

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
