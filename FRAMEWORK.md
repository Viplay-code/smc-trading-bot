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

El plan experimental completo post-cierre I1 (los cuatro espacios
evaluados en la sesión de planificación de 2026-08-08, el orden de
exploración aprobado y su justificación por valor de información
esperado/costo/riesgo, y el estado vivo del programa) se documenta en
`docs/research/EXPERIMENTAL_ROADMAP.md` — no se repite acá para no
duplicar contenido; este documento mantiene el registro retrospectivo por
campaña cerrada, aquel mantiene el mapa prospectivo de qué sigue.

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
