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
- A: EMA200 4H con zona neutral ±1%  ← baseline actual
- B: EMA50 + EMA200 4H (cruce de medias)
- C: Precio vs máximo/mínimo de las últimas 20 velas 4H

### Capa 2: Trigger LTF (señal de entrada)
Candidatos a evaluar:
- A: Liquidity Sweep + BOS (3 velas)  ← baseline actual
- B: Liquidity Sweep + BOS (5 velas)
- C: Solo BOS sin sweep previo
- D: Ruptura y cierre fuera de rango de 10 velas

### Capa 3: Entrada (precio exacto)
Candidatos a evaluar:
- A: Orden límite al 50% del rango Sweep→BOS  ← baseline actual
- B: Zona 40%-60% (entrada al tocar la zona)
- C: Cierre de vela BOS (entrada a mercado)
- D: Apertura de vela siguiente al BOS

### Gestión (fija para todas las variantes)
- Stop Loss: mínimo entre estructura y ATR(14) × 1.5
- Take Profit: 2.5R fijo
- Sesiones: Londres 07-11 UTC + Nueva York 13-17 UTC
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
