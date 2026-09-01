# Roadmap experimental post-cierre I1

Documento vivo — a diferencia de `FRAMEWORK.md` (log de cierre por campaña,
retrospectivo), este documento registra el **plan prospectivo**: qué
espacios experimentales quedan abiertos tras el cierre de la Fase de
Integración (I1), en qué orden se acordó explorarlos, y por qué. Se
actualiza cada vez que un espacio se cierra o el orden se revisita — no es
un contrato congelado como los de cada campaña individual (esos viven en
`FRAMEWORK.md` una vez cerrados con datos reales).

Acordado en sesión de planificación metodológica, 2026-08-08, inmediatamente
después del cierre de la Fase I1 (commit `d4ea3ca`, ver `FRAMEWORK.md`).

## Estado actual del programa (2026-08-12)

| Fase/espacio | Estado |
|---|---|
| H1 (`atr_mult`) | Cerrado con datos reales, documentado en `FRAMEWORK.md` |
| `atr_mult` × sesión (extensión residual de H1, NO uno de los 4 espacios) | **Cerrado con datos reales** (2026-08-12), documentado en `FRAMEWORK.md` — hipótesis primaria (`atr_mult`=3.0 × `dcv1_activo_15h`) **no respaldada**; grid secundario tampoco produce sobrevivientes (commits `a806d38` implementación, `3630f4d` resultados). No cambia el orden de exploración aprobado ni reabre Espacio 1/Espacio 2 — ver nota en "Orden de exploración aprobado" |
| H2 (familia: `distance`/`activation`/`be` aislados) | Cerrado con datos reales, documentado en `FRAMEWORK.md` |
| I1 (Integración: sesión × un parámetro H2) | Cerrado con datos reales, documentado en `FRAMEWORK.md` |
| Espacio 3 (`A_sweep_bos` bajo `dcv1_activo_15h`) | Cerrado con datos reales, documentado en `FRAMEWORK.md` — hipótesis **falsificada bajo el contrato evaluado** (commits `31a58ab` implementación, `76980f0` resultados, `38fa696` cierre) |
| **Espacio 2** (`max_hold`, sesión × parámetro; `risk` y `atr_period` excluidos del objetivo principal) | **Cerrado con datos reales** (2026-08-10), documentado en `FRAMEWORK.md` — hipótesis **falsificada bajo el contrato evaluado** (commits `f467f50` implementación, `a9f1dbd` resultados) |
| Iniciativa pendiente — ATR de período arbitrario en el pipeline de investigación | Identificada 2026-08-08 durante el diseño de Espacio 2, **sigue sin implementarse** — separada del cierre de Espacio 2, no reabierta por él |
| Espacio 4 (Entry bajo `T1_ema_cross`) | **Cerrado sin campaña nueva** (2026-08-10), documentado en `FRAMEWORK.md` — evidencia histórica ya publicada (`C_market_close` vs `D_next_candle_open`, 2026-07-27) reauditada y formalizada; `A_pullback_50` **no computable** bajo T1 (incompatibilidad estructural, NO resultado negativo ni hipótesis falsificada). **La celda "Entry de retroceso bajo T1" permanece genuinamente abierta** — este cierre NO significa que la cuestión de Entry bajo T1 quedó completamente resuelta, solo que el espacio tal como estaba definido no requiere más trabajo |
| **Espacio 1** (Gestión multivariable, `distance`×`activation`×`be` simultáneos) | **Cerrado con datos reales** (2026-08-17), documentado en `FRAMEWORK.md` — hipótesis **falsificada bajo el contrato evaluado** (0/216 filas candidatas con `pf`≥1.50; commits `3b1f843` implementación, `bf2de24` resultados). Con este cierre, los cuatro espacios del orden aprobado quedan completos — ver "Orden de exploración aprobado" |
| Rama B (Trigger/Entry: `D_range_breakout`, `A_sweep_bos`+`A_pullback_50`) | **Cerrado** (2026-08-18), documentado en `FRAMEWORK.md` — `D_range_breakout`+`C_market_close` **descartada**; `A_sweep_bos`+`A_pullback_50` **candidata congelada / evidencia insuficiente** (0/12 filas cumplen los 4 gates; ninguna combinación elegible para ciego 2024). **No es uno de los 4 espacios de este roadmap** ni una extensión residual de H1 (a diferencia de `atr_mult`×sesión) — línea surgida de una revisión estratégica posterior a estos 4 espacios, no documentada formalmente en este archivo hasta ahora. Ver nota de ambigüedad en "Espacios explícitamente fuera del orden" sobre su relación con Espacio 5/Espacio 6 |
| **Próxima línea de investigación** | **Sin decidir** — los 4 espacios del orden aprobado y Rama B están cerrados; la elección de qué sigue queda pendiente de una decisión explícita posterior, no determinada por este documento en su estado actual (ver ambigüedades señaladas abajo) |
| Espacio 5 (candidatos de Capa 1/2/3 nunca implementados) | Fuera del orden — **sigue sin ejecutarse como espacio completo**. `D` de Trigger ya evaluado vía Rama B (no cuenta como pendiente). **`Bias B` evaluado con datos reales y cerrado** (2026-08-24) — evidencia insuficiente para sostener que mejora el sistema respecto de Bias A bajo el contrato comparado; ver `FRAMEWORK.md`, sección "Bias B — EMA50+EMA200 4H (cruce) — cerrado". **`Trigger C` evaluado con datos reales y cerrado** (2026-08-22, resultados publicados antes del cierre de Bias B pero documentados recién ahora) — 0/6 celdas cumplen los 4 gates; ver `FRAMEWORK.md`, sección "Trigger C — BOS-only — cerrado". Criterio de priorización **parcial** definido (2026-08-19) para los sub-candidatos restantes: `Bias C` empatado con `Bias B` sin desempate ex ante, `Trigger B`/`Entry B` relegados — ver sección "Estado de priorización — Espacio 5". **`Bias C`/`Trigger B`/`Entry B` sin evaluar, ninguno autorizado a ejecutarse** |
| Espacio 6 (pausa/reconsideración del armazón completo) | Meta-decisión, no paramétrica — no forma parte de este orden. **Experimento 1 (TP fijo 2.5R) ejecutado con datos reales 2022+2023 y cerrado** — **EVIDENCIA INSUFICIENTE**: 0/6 celdas cumplen los 4 gates, 0/3 activos sobreviven ambos años, pero PF/MaxDD/expectancy mejoran respecto de V3-A en 5/6 celdas; ver `FRAMEWORK.md`, sección "Espacio 6 — Experimento 1 — TP fijo 2.5R — cerrado". **Experimento 2 (BE-only 1.0R, sin trailing, sin TP) ejecutado con datos reales 2022+2023 y cerrado** (2026-08-31) — **FAIL**: 1/6 celdas cumple los 4 gates (SOLUSDT 2023), 0/3 activos sobreviven ambos años, y PF empeora respecto de V3-A en 4/6 celdas (patrón inverso al Experimento 1); 4/6 celdas tienen más de un gate fallando simultáneamente — cumple el criterio contractual de FAIL definido al cerrar el Experimento 1. No reproduce la mejora del Experimento 1 ni identifica si esa mejora se debe a quitar breakeven o a agregar TP (ninguno aislado todavía); ver `FRAMEWORK.md`, sección "Espacio 6 — Experimento 2 — BE-only 1.0R (sin trailing, sin TP) — cerrado". **Espacio 6 permanece abierto** — ninguno de los dos experimentos lo cierra. Un Experimento 3 queda como posible siguiente paso, sin autorizar ni diseñar todavía |

## Los cuatro espacios experimentales

### Espacio 1 — Gestión multivariable (`distance` × `activation` × `be` simultáneos)

- **Objetivo/hipótesis**: ¿existe una combinación *conjunta* de `distance`, `activation` y `be` (no un solo parámetro a la vez) que, bajo alguna sesión, supere los 4 gates de FRAMEWORK.md para algún activo?
- **Variable(s) que cambia**: los 3 parámetros de Gestión de la familia H2 variando simultáneamente (no univariable, a diferencia de H2.1-H2.3/I1).
- **Pregunta científica**: si existe una solución puramente de Gestión — una interacción de segundo orden entre estos 3 parámetros — capaz de cerrar el gate de PF, no capturable variando un parámetro a la vez.
- **Evidencia que respalda**: I1 demostró en sus 3 bloques que variar un parámetro solo nunca acerca el PF al gate (máximo 1.476 de 156 filas candidatas), pero ninguno de esos experimentos varió más de un parámetro a la vez.
- **Evidencia que contradice**: los 3 parámetros mostraron trade-offs mecánicos consistentes (WR↑ con `be`↑/`activation`↑) que nunca se tradujeron en dirección de PF estable ni variando uno solo — no hay señal previa de sinergia esperable.
- **Costo experimental**: Alto (grilla combinatoria hasta 3×5×5=75 combos × 2 sesiones × 3 activos × 2 años; exige reglas de contingencia nuevas).
- **Riesgo metodológico**: Medio-Alto (expansión combinatoria sobre la misma muestra fija; riesgo de comparaciones múltiples).
- **Estado**: **CERRADO** (2026-08-17), hipótesis falsificada bajo el
  contrato evaluado — 0/216 filas candidatas con `pf`≥1.50, ningún activo
  sobrevive 2022 Y 2023 bajo ninguna de las 36 combinaciones evaluadas
  (grid final: `distance`×`activation`×`be`, bajo sesión `dcv1_activo_15h`
  única, sin extensiones por contingencia — más acotado que el costo
  "Alto"/75 combos estimado arriba al momento del diseño original de esta
  sección). Resultados, verificación y análisis completos: **`FRAMEWORK.md`,
  sección "Espacio 1"** (no repetidos acá, para evitar una segunda fuente
  de los mismos números). Con este cierre, los cuatro espacios del orden
  aprobado quedan completos.

### Espacio 2 — Parámetros de Gestión nunca variados (`max_hold`)

**Alcance y diseño resueltos en sesión de planificación metodológica,
2026-08-08.** Tres decisiones de diseño quedaron fijadas explícitamente, no
como supuestos heredados de H2:

- **`risk` excluido del objetivo científico principal** — no como "hipótesis
  no explorada", sino como exclusión justificada por el propio diseño del
  sistema bajo estudio. Verificado en código (`research/metrics.py:19-43`,
  `backtest.py:254-282`): `pf`/`wr`/`exp_r`/`total_r`/`freq` se calculan
  sobre `pnl_r` sin que `risk` intervenga; `risk` solo entra en la curva de
  equity (`eq[-1]*(1+cfg.risk*r)`), afectando únicamente `max_dd`/`ret`.
  Confirmado empíricamente (`research.compute_core_metrics` sobre la misma
  secuencia sintética de `pnl_r`, barriendo `risk` de 0.0025 a 0.04):
  `pf`/`exp_r`/`total_r` exactamente invariantes; `max_dd` monótono en
  `risk`. Escaneados los 12 CSV de resultados ya publicados del programa
  completo (H1, H2.1-H2.3, I1×3, Espacio 3): **cero filas** bloqueadas
  *exclusivamente* por `max_dd` (con `pf`/`exp_r`/`freq` ya en regla) — hoy
  no existe ninguna configuración que un ajuste de `risk` pudiera rescatar.
  Esta conclusión es válida para la arquitectura actual del backtest
  (sizing por `risk` fijo aplicado geométricamente a una curva de equity
  simple); si el modelo de sizing o gestión monetaria cambia en el futuro,
  la exclusión debe revisarse, no darse por heredada.
- **`atr_period` excluido de Espacio 2 (decisión 2026-08-08, tras verificación
  empírica adicional al aprobar el contrato)** — no por "sin efecto", sino
  porque el pipeline de investigación actual (`bias_campaign.to_backtest_frame`
  + `trigger_campaign.find_entries_for_trigger`, el que usan todas las
  campañas de este programa) no puede medir su efecto. Verificado en código:
  `to_backtest_frame` fija `out["atr"] = df["atr14"]` — la columna ATR14 ya
  calculada por `dc_v1` (período 14, pin ratificado en
  `DC-v1_Precisiones_Implementacion.md` P-7, deliberado para que el esquema
  3×3 sea determinista). `find_entries_for_trigger` construye `risk_pts` de
  cada entrada leyendo esa columna fija, nunca `cfg.atr_period`; `simulate_v3`
  solo consume `entry["risk_pts"]` ya congelado. `cfg.atr_period` sí llega a
  `research.TRIGGER_LAYERS["T1_ema_cross"]`, pero únicamente alimenta el
  chequeo interno de descarte por SL degenerado — no la condición del cruce
  ni el `risk_pts` real. Confirmado empíricamente sobre datos sintéticos:
  `n_entries`/`n_trades`/`pf`/`freq`/`risk_pts` bit-idénticos barriendo
  `atr_period` ∈ {7, 14, 21, 28}, todo lo demás fijo. La causa raíz es una
  decisión de gobernanza deliberada a nivel del contrato `dc_v1` (P-7, no
  revisada acá) combinada con una laguna no examinada del adaptador de
  investigación (nunca declaró que `atr_period` quedaba sin efecto). Estudiar
  `atr_period` de forma válida requeriría una evolución acotada del pipeline
  de investigación — recalcular ATR de período arbitrario sobre la serie
  **continua** (antes del corte de período, disciplina P-3), reutilizando
  `dc_v1.atr()` (ya genérica y validada desde la Iniciativa B del backlog
  post-Fase-B), marcada explícitamente como auxiliar de investigación fuera
  del contrato `dc_v1`, con su propio test de equivalencia en `atr_period`=14
  contra la columna `atr14` publicada y su propio test de disciplina P-3 —
  fuera del alcance de Espacio 2. Se propone como **iniciativa de
  infraestructura independiente**, con su propio contrato, antes de que
  `atr_period` pueda reabrirse como sub-bloque experimental futuro.
- **Patrón de sesión: sesión × parámetro (protocolo I1)** — no el patrón "un
  solo `control_8h`" que usó H2. La precondición que permitió a H2 correr
  solo bajo `control_8h` sin perder información — que las entradas no
  dependen del parámetro que se varía, verificada explícitamente en cada uno
  de sus 3 bloques — se reverifica acá para `max_hold` y **no se cumple**:
  `run_config` bloquea nuevas entradas hasta `busy_until = exit_idx` de la
  operación abierta, y `simulate_v3` limita el timeout a
  `min(i0+cfg.max_hold+1, n)`: reducir `max_hold` solo puede adelantar o
  igualar el `exit_time` de cada trade, nunca atrasarlo, por lo que puede
  aumentar `freq` por un mecanismo estructural distinto al de cualquier
  parámetro de H2. El freq base bajo `control_8h`/`T1_ema_cross`
  (`gestion_campaign_trailing_distance_results.csv`) es 4.0-5.6/mes — cerca
  del piso de 6, no un orden de magnitud por debajo como en Espacio 3 — lo
  que hace plausible que `max_hold` por sí solo mueva algún combo por
  encima del piso. Probar `max_hold` solo bajo una sesión fija arriesgaba
  subestimar su efecto (`control_8h` sin margen para observarlo si nunca
  cruza 6) o enmascararlo (`dcv1_activo_15h` ya resuelve freq por sí sola,
  sin poder aislar el aporte de `max_hold`) — se aplica sesión × parámetro,
  reutilizando el protocolo de I1 ya validado 3 veces sin desviaciones.
- **Objetivo/hipótesis**: ¿`max_hold` —fijo en 20 velas en absolutamente
  todas las campañas hasta ahora— tiene efecto sobre PF, bajo sesión
  `control_8h` o `dcv1_activo_15h`?
- **Variable(s) que cambia**: `max_hold` × sesión (`control_8h`/
  `dcv1_activo_15h`), mismo aislamiento univariable que H2/I1. `risk` y
  `atr_period` fuera del alcance (ver arriba).
- **Pregunta científica**: si este parámetro "periférico" de Gestión importa
  en absoluto para el PF — hoy es una laguna total, ni siquiera indiferencia
  demostrada.
- **Evidencia que respalda**: `reason_timeout` representa 14-17% de todos
  los trades en los tres bloques de I1 (511/2997, 834/4995, 718/5007) —
  mecanismo activo, nunca variado; `max_hold` además tiene, a diferencia de
  `distance`/`activation`/`be`, un mecanismo estructural verificado de
  interacción con `freq` (ver arriba).
- **Evidencia que contradice/matiza**: "mecanismo activo" no equivale a
  "relevante para PF" — `distance`/`activation`/`be` son mecanismos *más*
  activos (WR/`avg_win`/`avg_loss` verificados 12/12-18/18 en sus
  respectivas campañas) y aun así solo 0-1 de 3 mostraron señal de PF
  estable entre años — tasa base interna del programa desfavorable.
  Correlación adicional verificada entre `timeout_frac` y PF sobre las 156
  filas de I1: global 0.13, `control_8h`≈0.003, `dcv1_activo_15h`≈0.27 —
  débil y además confundida (subproducto de variar `distance`/`activation`/
  `be`, no de `max_hold` en sí — esta correlación es de I1, no de Espacio 2,
  y no se hereda como evidencia directa).
- **Costo experimental**: Medio (1 sub-bloque univariable × 2 sesiones,
  protocolo Fase A/B completo de I1 — más caro que el patrón de H2 de un
  solo `control_8h`, pero del mismo orden que cada bloque individual de I1,
  ya ejecutado 3 veces sin problemas).
- **Riesgo metodológico**: Bajo en ejecución (protocolo más probado del
  programa junto con H2). El riesgo de "no independiente del trigger
  vigente" identificado en el análisis original queda mitigado, no
  eliminado, por el diseño sesión × parámetro: cubre ambos regímenes de
  sesión para el trigger vigente (`T1_ema_cross`), pero sigue sin decir
  nada sobre un trigger distinto si este cambiara en el futuro.
- **Estado**: CERRADO (2026-08-10), hipótesis falsificada bajo el contrato
  evaluado — 47/47 filas candidatas computables, 0/47 alcanzó PF≥1.50, el
  gate vinculante volvió a ser PF (mismo patrón que los 3 bloques de I1).
  El mecanismo estructural sobre `freq` se confirmó en dirección (12/12
  contextos) pero su magnitud fue insuficiente para cruzar el gate bajo
  `control_8h`. `atr_period` permanece sin caracterizar — separado como
  iniciativa de infraestructura pendiente, no reabierto por este cierre.
  Resultados, verificación y análisis completos: **`FRAMEWORK.md`, sección
  "Espacio 2"** (no repetidos acá, para evitar una segunda fuente de los
  mismos números).

### Espacio 3 — `A_sweep_bos` revisitado bajo `dcv1_activo_15h`

- **Objetivo/hipótesis**: ¿el trigger SMC original (`A_sweep_bos`), cuya frecuencia bajo `control_8h` fue insuficiente para generar evidencia utilizable, produce una muestra suficiente y un PF sostenido bajo la sesión que sí resuelve el gate de frecuencia?
- **Variable(s) que cambia**: sesión (`control_8h` → `dcv1_activo_15h`), con Trigger=`A_sweep_bos` fijo.
- **Pregunta científica**: si los PF extremos observados en 2022 bajo `control_8h` (con muestra insuficiente) eran señal real o ruido de sobreajuste sobre pocos trades.
- **Evidencia que respalda**: PF extremos en 2022 en tres activos distintos (8.2-106.6 con `A_pullback_50`; 3.2-4.3 con `C_market_close`/`D_next_candle_open`) bajo `control_8h` — la única señal de PF alto observada en todo el programa. Se describen como tres activos *distintos* que muestran una señal consistente dentro del *mismo período de mercado* — no como réplicas estadísticamente independientes, porque comparten el mismo régimen temporal de 2022.
- **Evidencia que contradice**: la muestra insuficiente en 2023 (2-4 trades, por debajo del piso de 5 de `backtest.metrics()` — no ausencia total de operaciones) sugiere que el evento base podría ser intrínsecamente escaso, no solo restringido por sesión.
- **Costo experimental**: Bajo-Medio (reutiliza directamente `trigger_campaign.py` y `entry_campaign_sweep_bos.py`, solo cambia la sesión fija).
- **Riesgo metodológico**: Medio (posible que la frecuencia siga siendo insuficiente incluso bajo `dcv1_activo_15h`).
- **Estado**: CERRADO (2026-08-07), hipótesis falsificada bajo el contrato evaluado — el gate vinculante resultó ser frecuencia, no PF (a diferencia de I1). El trigger vigente (`T1_ema_cross`) se mantiene sin cambios, por lo que los Espacios 1/2/4 no requieren rediseño por este motivo. Resultados, interpretación y conclusión completos: **`FRAMEWORK.md`, sección "Espacio 3"** (no repetidos acá, para evitar una segunda fuente de los mismos números).

### Espacio 4 — Entry (Capa 3) bajo `T1_ema_cross` — CERRADO (2026-08-10)

Planteado originalmente como "`A_pullback_50` bajo `T1_ema_cross`". Cerrado
sin ejecutar ninguna campaña nueva, mediante auditoría de evidencia
histórica ya publicada (`scripts/entry_campaign_t1.py`, 2026-07-27) más un
hallazgo estructural verificado en código. Detalle completo, verificación
independiente y determinación exacta: **`FRAMEWORK.md`, sección "Espacio
4"** (no repetidos acá).

- **Objetivo/hipótesis original**: ¿el candidato de Entry `A_pullback_50` (nunca probado junto con `T1_ema_cross`, solo junto con `A_sweep_bos`) tiene comportamiento distinto de `C_market_close`/`D_next_candle_open` bajo el trigger de mayor muestra?
- **Variable(s) que cambia**: candidato de Entry (`A_pullback_50` agregado bajo Trigger=`T1_ema_cross`).
- **Pregunta científica**: si la elección del punto de entrada exacto importa bajo el trigger de mayor muestra — completa la matriz Trigger×Entry que quedó parcialmente vacía.
- **Evidencia que respalda**: ninguna directa — hueco de diseño puro.
- **Evidencia que contradice**: `C_market_close` y `D_next_candle_open` ya mostraron indiferencia casi exacta bajo `T1_ema_cross` (PF idéntico a 2-3 decimales) — sugiere que el precio exacto de entrada podría no ser palanca relevante bajo este trigger.
- **Costo experimental**: Bajo (el más barato del mapa) — en la práctica, costo final CERO: se cerró con evidencia ya existente, sin campaña nueva.
- **Riesgo metodológico**: subestimado en el diseño original ("mismo patrón que Espacio 2") — la auditoría de 2026-08-10 encontró que `A_pullback_50` no es computable bajo `T1_ema_cross` con su definición vigente (`event.meta["bos_level"]`/`swing_low`/`swing_high`, que solo produce `trigger_A_sweep_bos`), un riesgo estructural no identificado al escribir esta sección originalmente.
- **IMPORTANTE — alcance del cierre**: "CERRADO" significa que el espacio tal como fue definido no requiere más trabajo, NO que la cuestión de Entry bajo `T1_ema_cross` quedó completamente resuelta. La celda "Entry de retroceso bajo T1" (esperar un retroceso antes de entrar, un mecanismo cualitativamente distinto de `C_market_close`/`D_next_candle_open`) permanece **genuinamente abierta** — no forma parte de ningún espacio experimental actualmente aprobado, y reabrirla exigiría diseñar un candidato nuevo desde cero con su propio contrato, no reinterpretar este cierre.

## Orden de exploración aprobado

**Espacio 3 → Espacio 2 → Espacio 4 → Espacio 1**

(Espacio 5 y Espacio 6 quedan explícitamente fuera de este orden — ver tabla de estado.)

**Actualización tras el cierre de Espacio 3 (2026-08-07)**: el resultado
confirmó que `T1_ema_cross` se mantiene como trigger vigente (ver tabla de
estado) — el riesgo de segundo orden que motivó explorar Espacio 3 primero
(que su resultado obligara a rediseñar los Espacios 1/2/4 bajo un trigger
distinto) no se materializó. El orden aprobado no cambia por este motivo.

**Actualización tras el cierre de Espacio 2 (2026-08-10)**: hipótesis
falsificada bajo el contrato evaluado (ver tabla de estado y `FRAMEWORK.md`,
sección "Espacio 2") — `max_hold` no produjo ninguna combinación que
superara los 4 gates, y el mecanismo de `freq` que motivó el diseño
sesión × parámetro se confirmó en dirección pero no en magnitud suficiente.
El orden aprobado no cambia por este motivo.

**Actualización tras el cierre de Espacio 4 (2026-08-10)**: cerrado sin
campaña nueva, mediante auditoría de evidencia histórica ya publicada
(`entry_campaign_t1`) más un hallazgo estructural (`A_pullback_50` no
computable bajo `T1_ema_cross`) — ver tabla de estado y `FRAMEWORK.md`,
sección "Espacio 4". Este cierre NO resuelve la cuestión de Entry bajo T1
en general, solo el espacio tal como estaba definido; la celda "Entry de
retroceso bajo T1" permanece abierta, fuera de cualquier espacio
actualmente aprobado. El orden aprobado no cambia por este motivo; el
siguiente paso era, en ese momento, **Espacio 1** — cerrado desde el
2026-08-17, ver actualización más abajo.

**Nota tras el cierre de `atr_mult` × sesión (2026-08-12)**: campaña
independiente, NO uno de los cuatro espacios de este roadmap — extensión
residual de H1 hacia `dcv1_activo_15h`, explícitamente no una reapertura
de Espacio 1 ni de Espacio 2. Hipótesis primaria (`atr_mult`=3.0) no
respaldada; grid secundario sin sobrevivientes. No cambia el orden
aprobado ni el siguiente paso, que en ese momento era Espacio 1 — cerrado
desde el 2026-08-17, ver actualización más abajo. Detalle completo:
`FRAMEWORK.md`, sección "`atr_mult` × sesión" (no repetido acá).

**Actualización tras el cierre de Espacio 1 (2026-08-17)**: hipótesis
falsificada bajo el contrato evaluado (ver tabla de estado y `FRAMEWORK.md`,
sección "Espacio 1") — ninguna de las 36 combinaciones de `distance`×
`activation`×`be` superó los 4 gates. **Con este cierre, los cuatro
espacios del orden aprobado (Espacio 3 → Espacio 2 → Espacio 4 →
Espacio 1) quedan completos.** Este documento, en su estado actual, no
declara cuál es la siguiente línea de investigación — esa decisión queda
pendiente, fuera del alcance de esta actualización.

**Nota tras el cierre de Rama B (2026-08-18)**: línea de investigación
sobre Trigger/Entry (Capa 2/Capa 3), ejecutada y cerrada **después** de
completarse el orden aprobado de los cuatro espacios de arriba —
**no es uno de esos cuatro espacios, ni una extensión residual de H1**
(a diferencia de `atr_mult`×sesión). Detalle completo: `FRAMEWORK.md`,
sección "Rama B — Trigger/Entry". `D_range_breakout`+`C_market_close`
descartada; `A_sweep_bos`+`A_pullback_50` candidata congelada/evidencia
insuficiente; ninguna combinación elegible para prueba ciega 2024. Su
relación formal con Espacio 5/Espacio 6 de este documento no está resuelta
— ver ambigüedad señalada en "Espacios explícitamente fuera del orden",
abajo. Este documento tampoco declara, a partir de este cierre, cuál es la
siguiente línea de investigación.

## Justificación metodológica del orden (VoI, costo, riesgo)

El criterio central es una descomposición explícita del valor de
información en dos componentes:

- **VoI de primer orden**: cuánto reduce el experimento la incertidumbre
  sobre su propia pregunta.
- **VoI de segundo orden**: cuánto cambia el resultado el diseño óptimo de
  los experimentos pendientes (valor de información sobre decisiones de
  diseño futuras, no solo sobre el objeto de estudio inmediato).

1. **Espacio 3 primero**: mayor VoI total. De primer orden, por tener una
   señal direccional (aunque no constituye réplicas estadísticamente
   independientes) más una pregunta de medibilidad barata de resolver. De
   segundo orden — el argumento decisivo — por ser **upstream de todo lo
   demás**: Trigger es la decisión arquitectónica de la que dependen
   sesión, Gestión y Entry en cascada; su resultado puede invalidar el
   diseño de los Espacios 1, 2 y 4 si reemplaza a `T1_ema_cross` como
   trigger vigente.
2. **Espacio 2 segundo**: VoI de primer orden más bajo que Espacio 3 (tasa
   base interna del programa de 0-1/3 para "mecanismo activo → señal de PF
   estable"; correlación adicional débil y confundida). Su VoI de segundo
   orden también se corrigió a la baja durante el análisis — no es tan
   independiente del trigger vigente como se planteó inicialmente. Aun
   así, precede a los Espacios 4 y 1 por ser el patrón de menor riesgo de
   ejecución de todo el programa (protocolo probado 6 veces) y cerrar una
   laguna total de evidencia.
3. **Espacio 4 tercero**: el más barato de ejecutar, pero de valor
   científico esperado más bajo que 2 y 3 (ya hay indicios de indiferencia
   en Entry bajo `T1_ema_cross`); tiene sentido como cierre rápido,
   preferentemente después de confirmar si `T1_ema_cross` sigue vigente
   tras el Espacio 3, para no correrlo dos veces bajo triggers distintos.
4. **Espacio 1 último**: mayor valor científico esperado *si acierta*,
   pero el mayor costo y riesgo metodológico del mapa, y su diseño (qué
   sesión/trigger anclar) depende directamente del resultado del Espacio
   3 — ejecutarlo antes arriesga tener que rediseñarlo por completo.

## Espacios explícitamente fuera del orden

- **Espacio 5** (candidatos de Bias/Trigger/Entry nunca implementados: B/C
  de Bias, B/C/D de Trigger, B de Entry): sin evidencia en ningún sentido,
  y sin un criterio de priorización no-arbitrario entre sus 6
  sub-candidatos (análogo al Paso 0 de dominación Pareto que congeló el
  espacio experimental de I1) — ejecutar cualquiera ahora repetiría el
  patrón de barrido sin justificación que el programa ha evitado en cada
  campaña anterior.

  **Nota de reconciliación con Rama B (2026-08-18)**: `D` de Trigger
  (`D_range_breakout`, "ruptura y cierre fuera de rango de 10 velas") — uno
  de los 6 sub-candidatos listados arriba como "nunca implementados" — fue
  implementado y evaluado con datos reales en Rama B (`FRAMEWORK.md`,
  sección "Rama B — Trigger/Entry"), en la combinación
  `D_range_breakout`+`C_market_close`, bajo un contrato específico (Bias=A,
  Gestión V3-A ancla, sesión `dcv1_activo_15h` única). Por lo tanto, ese
  sub-candidato concreto **ya no está "sin evaluar"** en el sentido literal
  de la frase de arriba. Esto **no significa que Espacio 5 como espacio
  completo haya sido ejecutado, desbloqueado, ni que su bloqueo (falta de
  criterio de priorización no-arbitrario entre los 6 sub-candidatos) haya
  sido resuelto** — Rama B no pasó por ningún mecanismo de priorización
  formal de Espacio 5 (ni un Paso 0 de dominación Pareto ni ningún criterio
  equivalente); su justificación para elegir específicamente `D` de
  Trigger y `A` de Entry vino de una revisión estratégica externa a este
  espacio (ver nota siguiente). Los otros 5 sub-candidatos (B/C de Bias,
  B/C de Trigger, B de Entry) permanecen exactamente en el estado que este
  espacio ya documentaba: sin evidencia, sin evaluar, bloqueados por la
  misma falta de criterio de priorización.

  **Ambigüedad señalada, no resuelta**: este documento no contiene un
  criterio explícito para clasificar qué significa que un espacio quede
  "parcialmente" tocado por una línea de investigación ejecutada fuera de
  su propio mecanismo de priorización. No determino acá si Espacio 5 debe
  considerarse "5 de 6 sub-candidatos pendientes", "sin cambios en su
  estado formal (bloqueado en su totalidad, con una nota informativa)", o
  alguna otra clasificación — queda como pregunta abierta para una decisión
  explícita posterior, no resuelta por esta actualización documental.

  **Relación con Rama A/Rama B/Rama C** (nombres usados en la revisión
  estratégica de sesión de trabajo que motivó Rama B, 2026-08-18): esos
  nombres **no tienen, a la fecha, una definición formal en ningún archivo
  de este repositorio** — ni su alcance exacto, ni la matriz de valor de
  información que llevó a priorizar Rama B sobre las otras dos. Este
  documento registra únicamente que Rama B fue una línea ejecutada y
  cerrada (ver arriba), y dejar trazable su origen (candidato `D` de
  Trigger de este mismo Espacio 5) — **no se introduce "Rama A/B/C" como
  una nueva estructura formal de este roadmap** (al mismo nivel que
  Espacio 1-6) sin autorización explícita posterior. Si en el futuro se
  decide formalizar esa estructura o esa matriz de valor de información,
  requiere su propia actualización de este documento, no se asume acá.
- **Espacio 6** (pausa y reconsideración del armazón completo — Bias=A/
  Trigger=T1_ema_cross/Entry=C_market_close): no es un experimento
  paramétrico, es una decisión de asignación de esfuerzo. No es
  falsificable por una sola campaña; se revisita después de agotar los
  espacios de mayor valor informativo por menor costo (2, 3, 4), no antes.

  **Nota (2026-08-18, no resuelta)**: al momento en que se escribió esta
  frase, los espacios 2, 3 y 4 ya estaban cerrados pero el 1 no — la
  condición de habilitación tal como está redactada ("agotar los espacios
  ... (2, 3, 4)") no menciona explícitamente el Espacio 1 ni Rama B, ambos
  cerrados después. No determino acá si esa omisión fue deliberada (el
  Espacio 1 no cuenta para esta condición) o una imprecisión de redacción,
  ni si Rama B —al no ser uno de los cuatro espacios— cuenta o no como
  parte de "agotar los espacios de mayor valor informativo por menor
  costo". Esto no decide si Espacio 6 corresponde ejecutarse ahora — esa
  decisión queda expresamente fuera de esta actualización documental.

  **Actualización (2026-08-27)**: el Experimento 1 de Espacio 6 (TP fijo
  2.5R, aislando el mecanismo de Gestión) fue diseñado, implementado y
  ejecutado con datos reales — ver `FRAMEWORK.md`, sección "Espacio 6 —
  Experimento 1 — TP fijo 2.5R — cerrado". Resultado: EVIDENCIA
  INSUFICIENTE (no pasa los gates, pero muestra una mejora consistente
  de PF/MaxDD/expectancy respecto de V3-A en 5/6 celdas). Esto confirma
  que abrir Espacio 6 fue una decisión con contenido experimental real,
  no solo procedimental — pero un solo experimento no es suficiente
  para determinar si el mecanismo de Gestión es la explicación del
  techo de PF observado en el resto del programa. Espacio 6 sigue
  abierto; no se define acá ningún Experimento 2.

  **Actualización (2026-08-31)**: el Experimento 2 de Espacio 6
  (`BE_solo_1.0R` — sin trailing, breakeven en 1.0R intacto, sin TP,
  aislando el trailing como único componente distinto de V3-A, a
  diferencia del Experimento 1 que cambiaba tres componentes a la vez)
  fue implementado (commit `a6584b9`, 2026-08-27/28) y ejecutado con
  datos reales 2022+2023 (commit `bdfdbdd`, 2026-08-31) — ver
  `FRAMEWORK.md`, sección "Espacio 6 — Experimento 2 — BE-only 1.0R (sin
  trailing, sin TP) — cerrado". Resultado: **FAIL** — 1/6 celdas cumple
  los 4 gates (SOLUSDT 2023), 0/3 activos sobreviven 2022 Y 2023, PF
  empeora respecto de V3-A en 4/6 celdas (patrón inverso al Experimento
  1), y 4/6 celdas tienen más de un gate fallando simultáneamente
  (cumple el criterio contractual de FAIL fijado al cerrar el
  Experimento 1, a diferencia de la EVIDENCIA INSUFICIENTE de ese
  experimento). No reproduce la mejora del Experimento 1 — el trailing
  aislado no parece ser el componente responsable de esa mejora bajo
  este contrato — pero no identifica si esa mejora depende de quitar
  breakeven, de agregar el TP, o de ambos a la vez, ya que ninguno de
  los dos fue aislado todavía por separado. Espacio 6 sigue abierto; no
  se define acá ningún Experimento 3.

## Estado de priorización — Espacio 5 (checkpoint 2026-08-19)

Checkpoint de continuidad entre entornos/sesiones de trabajo — registra el
estado estratégico alcanzado hasta este punto, no una nueva decisión
experimental ni una autorización de ejecución. No modifica ninguna
conclusión ya cerrada de `FRAMEWORK.md`.

**Líneas cerradas hasta este checkpoint** (detalle completo en
`FRAMEWORK.md`, no repetido acá): Espacio 1, Espacio 2, Espacio 3,
Espacio 4, y Rama B — las cinco cerradas. Rama B en particular:
`D_range_breakout`+`C_market_close` → **DESCARTADA**;
`A_sweep_bos`+`A_pullback_50` → **CANDIDATA CONGELADA / EVIDENCIA
INSUFICIENTE**, sin ninguna combinación elegible para prueba ciega 2024,
y sin que deba reabrirse bajo el contrato actual para rescatar su PF ni
para forzar su frecuencia.

**Candidatos pendientes de Espacio 5**: Bias B, Bias C, Trigger B,
Trigger C, Entry B. `D_range_breakout` (el sexto sub-candidato original)
ya fue evaluado vía Rama B y **no cuenta como pendiente**. Esto **no
significa que Espacio 5 esté cerrado, ejecutado ni desbloqueado como
espacio completo** — los otros 5 sub-candidatos permanecen sin evaluar.

**Metodología del criterio de priorización (2026-08-19)**: se evaluó
explícitamente la posibilidad de un sistema de puntuación numérico
ponderado y se descartó — dimensiones como "plausibilidad ex ante" o
"valor informativo" no son convertibles a un peso numérico sin introducir
arbitrariedad. En su lugar se usó una **lógica de 3 filtros no
compensatorios**, aplicados en secuencia (mismo patrón metodológico que
la dominación Pareto del Paso 0 de I1):
1. **Ejecutabilidad inmediata** (¿requiere resolver primero una
   limitación de infraestructura de código?) → excluye **Entry B**: el
   contrato `EntryFn` vigente no soporta llenado no-determinístico.
2. **Independencia mecánica genuina** (¿hipótesis distinta, o variación
   paramétrica de un candidato ya evaluado con datos reales?) → excluye
   **Trigger B**: comparte el 100% del requisito de sweep con
   `A_sweep_bos` (ya evaluado en Espacio 3), solo varía la ventana de
   confirmación del BOS.
3. **Propiedad ex ante lógicamente demostrable** (no empírica, derivada
   de la definición del mecanismo, no de ningún resultado de campaña) →
   solo **Trigger C** la tiene.

**Resultado**: **Bias B / Bias C** quedan elegibles pero **empatados** —
sin un criterio ex ante disponible para desempatarlos sin introducir un
juicio de valor no derivado de la evidencia. **Trigger C queda como
prioridad #1.**

**Fundamento de la prioridad de Trigger C — exclusivamente ex ante**:
- elimina una condición `AND` del mecanismo Sweep+BOS;
- por definición lógica de conjuntos, su número de eventos crudos no
  puede ser menor que el de Sweep+BOS bajo el mismo dataset — verdadero
  por la estructura booleana del candidato, no por ningún resultado
  observado de Espacio 3;
- permite investigar directamente si el requisito de sweep aporta valor
  real o solo restringe frecuencia;
- es una hipótesis conceptualmente distinta, no un ajuste paramétrico;
- alto valor informativo tanto si falla como si tiene éxito.

**No se utilizó** PF, `max_dd`, expectancy, frecuencia observada, ni
ningún resultado de campañas ya cerradas (Espacio 3, Rama B u otra) para
fundamentar esta priorización.

**Actualización (2026-08-24)**: `Bias B` fue evaluado con datos reales
(2022+2023) y cerrado — ver `FRAMEWORK.md`, sección "Bias B —
EMA50+EMA200 4H (cruce) — cerrado". El empate `Bias B`/`Bias C` señalado
arriba no fue resuelto por el criterio ex ante de este checkpoint —
`Bias B` fue simplemente el primero en ejecutarse con datos reales, no el
candidato que el criterio de priorización de 2026-08-19 favorecía (ese
criterio dejó ambos empatados explícitamente, sin desempate disponible).
`Bias C` permanece sin evaluar y sin autorización de ejecución.

**Estado explícito — Trigger C priorizado, NO autorizado a ejecutarse.**
A la fecha de este checkpoint, todavía **no existen**: contrato
experimental aprobado, campaña implementada, Fase A ejecutada, backtest
ejecutado, resultados, ni prueba ciega. El único siguiente paso pendiente
es **diseñar formalmente la campaña de Trigger C y someterla a revisión
antes de cualquier implementación o ejecución** — ese diseño deberá
determinar (en una fase futura, no en este checkpoint): definición exacta
de BOS, Bias/Entry/sesión/Gestión/ATR/`max_hold`/riesgo/activos/años
congelados, baseline, cardinalidad, gates y controles de contaminación
entre capas.

Este checkpoint **no define** grid, baseline, número de celdas,
parámetros concretos, ni archivos a modificar para Trigger C — todo eso
queda para la fase de diseño, sujeta a su propia aprobación explícita.

**Actualización (2026-08-22, documentada 2026-08-24)**: `Trigger C` fue
implementado (`research/layers.py::trigger_C_bos_only`, `scripts/
trigger_c_campaign.py`) y ejecutado con datos reales (2022+2023) —
ver `FRAMEWORK.md`, sección "Trigger C — BOS-only — cerrado". El
resultado (0/6 celdas cumplen los 4 gates; frecuencia dispara muy por
encima del techo de 12/mes; PF converge a 0.89-1.41, el mismo rango
observado en Espacio 1, Espacio 2 y Bias B) se incorpora al diagnóstico
global del cuello de botella de PF como una cuarta línea de evidencia
independiente. Esta actualización queda registrada con retraso respecto
de la ejecución real: los resultados de Trigger C (commit `787c91a`,
2026-08-22) predatan la implementación completa de Bias B (commit
`1f91b02`, 2026-08-22 más tarde) — el checkpoint original de esta
sección, arriba, describe el estado tal como era el 2026-08-19 y no se
reescribe, pero deja de ser el estado vigente a partir de esta
actualización. `Trigger B`/`Entry B`/`Bias C` permanecen sin evaluar y
sin autorización de ejecución.

## Mantenimiento de este documento

Actualizar la tabla de estado y, si corresponde, el orden de exploración
cada vez que:
- Un espacio complete su ciclo (implementación → resultados reales →
  análisis → cierre documentado en `FRAMEWORK.md`).
- La evidencia de un cierre cambie la justificación de prioridad de los
  espacios restantes (ej. si el Espacio 3 revierte el trigger vigente, el
  diseño de los Espacios 1/2/4 debe revisarse antes de ejecutarlos, no
  asumirse transferible).
