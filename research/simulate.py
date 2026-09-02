"""research/simulate.py — Fase 4 (C2, extracción del motor de simulación,
2026-09-02): ubicación canónica de `simulate_v3`/`EXIT_CONFIGS`, MOVIDOS
desde `backtest.py` sin cambiar una sola línea de su lógica — el
comportamiento de `simulate_v3` es evidencia histórica (FRAMEWORK.md,
Espacio 6 y todo el programa anterior), no se reinterpreta ni se mejora
acá.

QUÉ SE MOVIÓ y QUÉ NO (decisión de diseño explícita, resultado de la
auditoría previa a esta fase — ver informe de Fase 4):

  - `simulate_v3`, `EXIT_CONFIGS`: MOVIDOS acá, cuerpo idéntico.
  - `run_config` NO se movió — permanece en `backtest.py`. Motivo: llama a
    `simulate_v3` como NOMBRE LIBRE, resuelto en el namespace del módulo
    donde `run_config` está *definida* (Python resuelve nombres libres en
    `__globals__` de la función, no en el módulo que la invoca). Varios
    tests ya existentes (`research/tests/test_gestion_espacio6_raw_
    campaign.py`, `test_gestion_espacio6_experimento2_be_solo_
    campaign.py`) hacen `backtest.simulate_v3 = _contador; backtest.
    run_config(...)` para verificar que el motor real se invoca — esto
    SOLO funciona porque `run_config` vive en `backtest.py`. Si
    `run_config` se moviera acá, ese mismo monkeypatch dejaría de tener
    efecto SILENCIOSAMENTE (la búsqueda de `simulate_v3` caería en
    `research.simulate.__dict__`, no en `backtest.__dict__`) — se decidió
    NO mover `run_config` para no romper esa garantía ya verificada.
  - `COST_PER_TRADE` NO se movió — permanece en `backtest.py` como única
    fuente autoritativa. Motivo: múltiples scripts YA COMMITTEADOS
    (`scripts/gestion_espacio6_costo_cero_diagnostico.py`,
    `research/runner.py`) parchean `backtest.COST_PER_TRADE`
    temporalmente para controlar el costo simulado — si la constante
    canónica se moviera acá, esos monkeypatches dejarían de tener efecto
    SILENCIOSAMENTE (idéntico problema al de `run_config` arriba, pero
    para una constante en vez de una función). `simulate_v3` sigue
    leyendo el costo real desde `backtest.COST_PER_TRADE`, vía un import
    LOCAL A LA FUNCIÓN (ver dentro de `simulate_v3`) — nunca a nivel de
    módulo.

POR QUÉ EL IMPORT DE `backtest` ES LOCAL A LA FUNCIÓN, NO A NIVEL DE
MÓDULO (hallazgo de la auditoría previa, verificado por trazado manual de
ambos órdenes de import): si este módulo importara `backtest` a nivel de
módulo, Y `backtest.py` importara este módulo (`research.simulate`) para
re-exportar `simulate_v3` accediendo a su atributo TAMBIÉN a nivel de
módulo, cualquier código que haga `import research.simulate` (o
`import research`, si este módulo se expone desde `research/__init__.py`)
ANTES de que `backtest.py` se haya cargado alguna vez dispara una cadena
`research.simulate -> backtest -> research.simulate` donde el segundo
tramo intenta leer `research.simulate.simulate_v3` mientras ese mismo
módulo TODAVÍA SE ESTÁ CARGANDO (pausado en su propio `import backtest`)
— `AttributeError` real, no hipotético, verificado con ambos órdenes de
arranque posibles antes de escribir este archivo. Un import LOCAL A LA
FUNCIÓN se ejecuta únicamente en el momento de la LLAMADA, momento en el
que ambos módulos ya terminaron de cargar sin importar el orden de
arranque — elimina el ciclo por completo, sin tocar la firma de
`simulate_v3` (que debía permanecer exactamente `(df, entry, exit_cfg,
cfg)`, sin agregar un parámetro de costo — habría sido un cambio
semántico, prohibido por el principio de esta fase).
"""
from __future__ import annotations

# Configuraciones de salida a comparar — MOVIDO desde backtest.py, sin
# cambiar un solo valor.
EXIT_CONFIGS = {
    "V3-A (1R/2R/1R)":       {"be": 1.0,  "activation": 2.0, "distance": 1.0},
    "V3-B (0.75R/1.5R/0.75R)": {"be": 0.75, "activation": 1.5, "distance": 0.75},
}


def simulate_v3(df, entry, exit_cfg, cfg):
    """
    Simula una entrada con gestion V3 barra-a-barra, convencion conservadora.
    Devuelve pnl_r neto (con costos) y metadatos.

    MOVIDO desde backtest.py (Fase 4, C2) — cuerpo idéntico, sin cambiar
    reglas, precedencia intrabar, SL, BE, trailing, timeout, sizing,
    tratamiento de entradas, ni outputs. Única diferencia mecánica: el
    import local de `backtest` (ver docstring del módulo) para leer
    COST_PER_TRADE, que permanece definido en backtest.py.
    """
    # Import LOCAL a la función — ver docstring del módulo para el
    # análisis completo de por qué NO puede ser un import a nivel de
    # módulo (dependencia circular real con backtest.py, verificada por
    # trazado manual antes de escribir este archivo).
    import backtest

    i0        = entry["entry_idx"]
    direction = entry["direction"]
    e         = entry["entry"]
    risk_pts  = entry["risk_pts"]
    stop      = entry["sl0"]

    be_lvl    = exit_cfg["be"]         # en R
    act_lvl   = exit_cfg["activation"] # en R
    dist_r    = exit_cfg["distance"]   # en R

    n = len(df)
    max_fav_pts = 0.0     # maximo avance favorable en puntos
    trailing_on = False
    be_done     = False

    exit_idx   = None
    exit_price = None
    reason     = None

    end = min(i0 + cfg.max_hold + 1, n)
    for k in range(i0 + 1, end):
        c = df.iloc[k]

        # ── 1. Test de stop-out contra extremo ADVERSO, con stop del inicio de vela
        if direction == "long":
            if c["low"] <= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break
        else:
            if c["high"] >= stop:
                exit_idx, exit_price, reason = k, stop, "stop"
                break

        # ── 2. Actualizar maximo favorable con el extremo FAVORABLE de esta vela
        if direction == "long":
            fav_pts = c["high"] - e
        else:
            fav_pts = e - c["low"]
        if fav_pts > max_fav_pts:
            max_fav_pts = fav_pts

        fav_r = max_fav_pts / risk_pts

        # ── 3. Break-even (efecto para velas siguientes)
        if not be_done and fav_r >= be_lvl:
            if direction == "long":
                stop = max(stop, e)
            else:
                stop = min(stop, e)
            be_done = True

        # ── 4. Activacion de trailing
        if not trailing_on and fav_r >= act_lvl:
            trailing_on = True

        # ── 5. Trailing ratchet (solo a favor)
        if trailing_on:
            if direction == "long":
                trail_stop = e + (max_fav_pts - dist_r * risk_pts)
                stop = max(stop, trail_stop)
            else:
                trail_stop = e - (max_fav_pts - dist_r * risk_pts)
                stop = min(stop, trail_stop)

    # ── Timeout: cierre a mercado en la ultima vela evaluada
    if exit_idx is None:
        last = min(end - 1, n - 1)
        exit_idx   = last
        exit_price = df.iloc[last]["close"]
        reason     = "timeout"

    # ── PnL en R (neto de costos)
    if direction == "long":
        pnl_pts = exit_price - e
    else:
        pnl_pts = e - exit_price
    pnl_r_gross = pnl_pts / risk_pts
    cost_r      = (e * backtest.COST_PER_TRADE) / risk_pts
    pnl_r_net   = pnl_r_gross - cost_r

    return {
        "entry_time": df.index[i0],
        "exit_time":  df.index[exit_idx],
        "direction":  direction,
        "reason":     reason,
        "pnl_r":      round(pnl_r_net, 4),
        "duration_h": exit_idx - i0,
    }
