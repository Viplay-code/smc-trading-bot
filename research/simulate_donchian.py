"""research/simulate_donchian.py — Fase 4 (DCH-EXIT, 2026-09-11): motor de
simulación del mecanismo de Gestión "salida por canal Donchian opuesto",
implementado conforme al Protocol v2 FINAL pre-registrado.

AISLADO POR DISEÑO: este módulo NO modifica `research/simulate.py` —
`simulate_v3` (y con él V3-A/V3-B/Raw) permanece intacto, byte a byte. Es
la misma disciplina de "mecanismo con función de simulación propia" que el
precedente `scripts/gestion_espacio6_tp_fijo_campaign.py::simulate_tp_fixed`
(Espacio 6), pero ubicado en `research/` porque acá sí se registra en
`research.runner.MANAGEMENT_LAYERS` como mecanismo canónico.

SEMÁNTICA PRE-REGISTRADA (Protocol v2, seccion 6) — literal, no
reinterpretable:

  Posición abierta en `i0` (close de la vela de ruptura, vía
  `entry_C_market_close`). Para cada vela `k` en
  `[i0+1, min(i0+max_hold, n-1)]`, EN ESTE ORDEN ESTRICTO:

    1. ATR STOP (prioridad absoluta): `sl0` FIJO, nunca reasignado —
       sin breakeven, sin trailing, a diferencia de V3-A/V3-B.
         LONG : low[k]  <= sl0  -> salida AL NIVEL sl0, reason="stop"
         SHORT: high[k] >= sl0  -> salida AL NIVEL sl0, reason="stop"

    2. CANAL DE SALIDA, sobre velas ESTRICTAMENTE ANTERIORES a `k`
       (la vela `k` está EXCLUIDA de su propio canal — misma convención
       causal que `research.layers::trigger_D_range_breakout`, que usa
       `df1h.iloc[i - range_lookback : i]`):
         LONG : exit_channel_low  = min(low[k-N_exit : k])
                dispara si low[k]  <= exit_channel_low
                -> salida AL NIVEL exit_channel_low
         SHORT: exit_channel_high = max(high[k-N_exit : k])
                dispara si high[k] >= exit_channel_high
                -> salida AL NIVEL exit_channel_high
         reason = "donchian_exit"

    3. Sin disparo en toda la ventana -> reason="timeout", salida al
       `close` de la vela `min(i0+max_hold, n-1)`.

PROPIEDADES DECLARADAS EN EL PROTOCOLO (no accidentes de implementación):

  - NO ES UN TRAILING MONÓTONO. `min(low[k-N:k])` es un estadístico de
    ventana deslizante: puede ALEJARSE del precio, a diferencia del
    ratchet de V3. El único nivel monótono es `sl0`, que acá es fijo.
    Esta diferencia semántica respecto de V3 ES el mecanismo bajo prueba.

  - EL CANAL PUEDE USAR VELAS ANTERIORES A LA ENTRADA. En `k=i0+1` la
    ventana `i0-N+1 ... i0` es íntegramente pre-entrada (formulación
    Turtle clásica). Consecuencia declarada: para un long generado por
    una ruptura alcista de `range_lookback` velas, el mínimo de las
    `N_exit` velas previas está por construcción cerca del nivel de
    ruptura, así que la salida puede dispararse ante un pullback menor
    en los primeros bares. Es el mecanismo, no un defecto.

  - PRECEDENCIA STOP > DONCHIAN en la misma vela: garantizada
    estructuralmente por el orden de evaluación (paso 1 antes que paso
    2, con `break`). Además es causalmente correcta — los extremos
    intrabar ocurren en o antes del close — y es la MISMA convención
    conservadora ya explícita en `simulate_v3` y `simulate_tp_fixed`
    ("gana el STOP, precedencia conservadora explícita, no un accidente
    de orden de evaluación"). Nótese que cuando el nivel del canal queda
    por DEBAJO del stop (long), `low[k] <= level < sl0` implica que el
    paso 1 ya disparó: la precedencia se cumple sin ningún chequeo extra.

  - FILL ANTE GAP: si la vela abre más allá del nivel, el fill se asume
    AL NIVEL. Convención HEREDADA de `simulate_v3` (que sale a `stop`
    aunque la vela lo haya cruzado de golpe), CONGELADA para controles y
    tratamiento, NO modificada en Fase 4, y NO constituye una ventaja
    específica de DCH-EXIT — es simétrica entre todos los mecanismos
    (Protocol v2 seccion 6, decisión D4).

  - SUFICIENCIA DEL CANAL, DEMOSTRADA (no asumida):
    `trigger_D_range_breakout` itera desde `range_lookback` (=10 en Fase
    4), luego `i0 >= 10` y `k >= 11`, de donde `k - N_exit >= 11 - 5 = 6
    >= 0`. El canal SIEMPRE tiene `N_exit` velas completas dentro de un
    slice de período. Aun así, si alguna vez `k - N_exit < 0`, esta
    función LANZA `ValueError` — nunca trunca la ventana en silencio
    (regla defensiva pre-registrada, Protocol v2 seccion 6).

  - FIN DE DATASET: `end = min(i0 + cfg.max_hold + 1, n)` — heredado sin
    cambios de `simulate_v3`; el timeout cierra al close de la última
    vela evaluable.

  - COSTES: `cost_r = (entry * backtest.COST_PER_TRADE) / risk_pts`,
    función del precio de ENTRADA (no del de salida) — idéntico a
    `simulate_v3`/`simulate_tp_fixed`, sin ningún cambio.

`exit_price` SÍ se incluye en el dict de salida (a diferencia de
`simulate_v3`, que no lo produce y por eso deja `TradeRecord.exit_price`
en None) — mismo criterio que `simulate_tp_fixed`: este mecanismo sale a
niveles conocidos y explícitos, así que no fabricarlo sería perder
información realmente disponible. `research.schema.TradeRecord.from_raw`
lo recoge vía `raw.get("exit_price")` sin ningún cambio.

Import LOCAL a la función de `backtest` (para `COST_PER_TRADE`): misma
razón anti-import-circular ya documentada en `research/simulate.py`.
"""
from __future__ import annotations

import pandas as pd


def simulate_donchian_exit(df: pd.DataFrame, entry: dict, exit_lookback: int, cfg) -> dict:
    """Simula una entrada con salida por canal Donchian opuesto de
    `exit_lookback` velas, convención intrabar conservadora. Devuelve el
    MISMO shape de dict que `research.simulate.simulate_v3` (más
    `exit_price`, ver docstring del módulo).

    Ver el docstring del módulo para la semántica temporal completa
    pre-registrada; esta función es su transcripción literal."""
    import backtest

    i0 = entry["entry_idx"]
    direction = entry["direction"]
    e = entry["entry"]
    risk_pts = entry["risk_pts"]
    stop = entry["sl0"]   # FIJO — nunca se reasigna (sin BE, sin trailing)

    n = len(df)
    exit_idx = None
    exit_price = None
    reason = None

    end = min(i0 + cfg.max_hold + 1, n)
    for k in range(i0 + 1, end):
        c = df.iloc[k]

        # -- 1. ATR stop (extremo adverso) — precedencia absoluta sobre el
        #       canal si ambos caen en la misma vela.
        if direction == "long":
            if c["low"] <= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break
        else:
            if c["high"] >= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break

        # -- 2. Canal de salida sobre velas ESTRICTAMENTE anteriores a k.
        lo = k - exit_lookback
        if lo < 0:
            raise ValueError(
                f"canal de salida incompleto en k={k} con exit_lookback="
                f"{exit_lookback} (requiere {exit_lookback} velas anteriores, "
                f"disponibles {k}) — la ventana NUNCA se trunca en silencio "
                f"(regla defensiva pre-registrada, Protocol v2)."
            )
        window = df.iloc[lo:k]   # EXCLUYE la vela k

        if direction == "long":
            level = window["low"].min()
            if c["low"] <= level:
                exit_idx, exit_price, reason = k, level, "donchian_exit"
                break
        else:
            level = window["high"].max()
            if c["high"] >= level:
                exit_idx, exit_price, reason = k, level, "donchian_exit"
                break

    # -- Timeout: cierre a mercado en la última vela evaluada — misma regla
    #    que simulate_v3 (cfg.max_hold, close de la vela).
    if exit_idx is None:
        last = min(end - 1, n - 1)
        exit_idx = last
        exit_price = df.iloc[last]["close"]
        reason = "timeout"

    if direction == "long":
        pnl_pts = exit_price - e
    else:
        pnl_pts = e - exit_price
    pnl_r_gross = pnl_pts / risk_pts
    cost_r = (e * backtest.COST_PER_TRADE) / risk_pts   # mismo modelo de costos
    pnl_r_net = pnl_r_gross - cost_r

    return {
        "entry_time": df.index[i0],
        "exit_time": df.index[exit_idx],
        "direction": direction,
        "reason": reason,
        "pnl_r": round(pnl_r_net, 4),
        "duration_h": exit_idx - i0,
        "exit_price": exit_price,
    }


def run_config_donchian(df: pd.DataFrame, entries: list, exit_lookback: int, cfg) -> pd.DataFrame:
    """Ejecuta DCH-EXIT sobre `entries` respetando 'una posición a la vez'.

    Réplica ESTRUCTURAL EXACTA de `backtest.run_config` (mismo bucle,
    misma variable `busy_until`, misma regla de bloqueo, mismo orden de
    recorrido) — no se reutiliza `backtest.run_config` en sí porque esa
    función resuelve `simulate_v3` como nombre libre en SU propio módulo
    (ver docstring de `research/simulate.py`), así que no puede delegar en
    otro motor sin modificar `backtest.py`, explícitamente prohibido en
    Fase 4. `backtest.py` NO se toca."""
    trades = []
    busy_until = -1
    for ent in entries:
        if ent["entry_idx"] <= busy_until:
            continue  # ya hay posicion abierta
        res = simulate_donchian_exit(df, ent, exit_lookback, cfg)
        trades.append(res)
        exit_idx = df.index.get_loc(res["exit_time"])
        busy_until = exit_idx
    return pd.DataFrame(trades)
