"""
Validacion barra-a-barra de V3 — T1 Momentum
Dos configuraciones en paralelo:
  V3-A (primaria, pre-registrada): BE 1.0R / activacion 2.0R / distancia 1.0R
  V3-B (secundaria, optimo barrido): BE 0.75R / activacion 1.5R / distancia 0.75R

Gestion V3 (sin TP fijo — la salida la decide el trailing o el SL):
  - SL inicial = min(estructura, entry - ATR*1.5)  [long]
  - Break-even: cuando el avance favorable alcanza BE_trigger*R, mover SL a entry
  - Trailing:   cuando el avance alcanza activation*R, activar trailing a
                (max_favorable - distance*R), solo ratchet a favor
  - Timeout: 20 velas; si sigue abierta, cierre a mercado (close de la vela)

Convencion intrabar CONSERVADORA:
  En cada vela se testea PRIMERO el stop vigente contra el extremo adverso
  (low en long, high en short) usando el stop del INICIO de la vela.
  Solo si no hay stop-out se actualiza el maximo favorable y se sube el stop
  (BE/trailing) con efecto para las velas SIGUIENTES. Asi el movimiento
  favorable intrabar nunca "protege" dentro de la misma vela — modela el whipsaw.

Periodos: 2022 (in-sample) y 2023 (validacion). 2024 permanece CIEGO.
"""

import time
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from binance.client import Client

import research

COST_PER_TRADE = 0.0009   # 0.04% comision + 0.05% slippage, en fraccion del precio

@dataclass
class Config:
    atr_period: int    = 14
    atr_mult: float    = 1.5
    risk: float        = 0.005
    ema_neutral: float = 0.01
    max_hold: int      = 20
    sessions: list     = field(default_factory=lambda: [(7, 11), (13, 17)])

# Configuraciones de salida a comparar
EXIT_CONFIGS = {
    "V3-A (1R/2R/1R)":       {"be": 1.0,  "activation": 2.0, "distance": 1.0},
    "V3-B (0.75R/1.5R/0.75R)": {"be": 0.75, "activation": 1.5, "distance": 0.75},
}


def download(symbol, interval, start, end):
    client = Client()
    raw = client.futures_historical_klines(symbol, interval, start, end)
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open","high","low","close"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    return df


def build_features(df1h_raw, df4h_raw, cfg):
    df   = df1h_raw.copy()
    df4h = df4h_raw.copy()

    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h-l, (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1)
    df["atr"]  = tr.ewm(alpha=1/cfg.atr_period, adjust=False).mean()
    df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    h_idx = df.index.hour
    df["in_session"] = [any(s <= hh < e for s, e in cfg.sessions) for hh in h_idx]

    # Bias NO se enruta por research.BIAS_LAYERS["A_ema200_neutral"] (decision
    # explicita, Tarea 7): esa funcion clasifica una vez por vela 4H (cierre
    # 4H vs su propio EMA200 4H, replica fiel de bot.py::htf_bias), mientras
    # que esta formula reclasifica cada hora comparando el cierre 1H (que
    # cambia) contra un nivel de EMA200 4H sostenido fijo (shift+ffill) —
    # son dos formulas de Capa 1 distintas bajo el mismo nombre de candidato,
    # no una y su transcripcion. Migrarla habria cambiado el comportamiento
    # observable de backtest.py (ver hallazgo registrado en memoria post-
    # Fase-B). Se deja igual que antes de la Tarea 7.
    df4h["ema200"] = df4h["close"].ewm(span=200, adjust=False).mean()
    df4h_s = df4h[["ema200","close"]].shift(1)
    df4h_s.columns = ["ema200_4h","close_4h"]
    df = df.join(df4h_s, how="left")
    df[["ema200_4h","close_4h"]] = df[["ema200_4h","close_4h"]].ffill()

    dist = (df["close"] - df["ema200_4h"]) / df["ema200_4h"]
    df["bias"] = np.where(dist >  cfg.ema_neutral, "long",
                 np.where(dist < -cfg.ema_neutral, "short", "neutral"))
    return df


def find_entries(df, cfg):
    """Devuelve lista de dicts con la señal de entrada T1 (sin gestionar salida).

    Capa 2 (research.TRIGGER_LAYERS["T1_ema_cross"]) y Capa 3
    (research.ENTRY_LAYERS["C_market_close"]) reemplazan la deteccion de
    cruce y el precio de entrada que vivian inline aca (Tarea 7). El trigger
    no filtra por bias/sesion (ver nota de composicion en research/layers.py)
    asi que ese filtro se reaplica aca, comparando el bias ya resuelto en
    build_features contra la direccion del evento — exactamente el chequeo
    "bias == long y no hay cross_up -> descartar" que hacia el codigo
    original, solo que expresado como una comparacion de igualdad.

    El SL/risk_pts sigue siendo "Gestion" (FRAMEWORK.md) y no vive en el
    registro: se recalcula aca igual que antes, con la misma formula que
    trigger_T1_ema_cross ya replica internamente solo para decidir si el
    evento existe (ver su docstring) — es una redundancia de calculo
    aceptada, no eliminada, porque research/layers.py no se modifica en
    esta tarea.
    """
    raw_events = research.TRIGGER_LAYERS["T1_ema_cross"](
        df, atr_period=cfg.atr_period, atr_mult=cfg.atr_mult,
    )
    entry_fn = research.ENTRY_LAYERS["C_market_close"]

    entries = []
    for ev in raw_events:
        row = df.iloc[ev.entry_idx]
        if not row["in_session"] or row["bias"] != ev.direction:
            continue

        entry = entry_fn(df, ev).price
        atr   = row["atr"]
        if ev.direction == "long":
            sl = min(row["low"], entry - cfg.atr_mult*atr)
        else:
            sl = max(row["high"], entry + cfg.atr_mult*atr)
        risk_pts = abs(entry - sl)
        if risk_pts < 1e-9: continue

        entries.append({
            "entry_idx": ev.entry_idx, "direction": ev.direction,
            "entry": entry, "sl0": sl, "risk_pts": risk_pts,
        })
    return entries


def simulate_v3(df, entry, exit_cfg, cfg):
    """
    Simula una entrada con gestion V3 barra-a-barra, convencion conservadora.
    Devuelve pnl_r neto (con costos) y metadatos.
    """
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
    cost_r      = (e * COST_PER_TRADE) / risk_pts
    pnl_r_net   = pnl_r_gross - cost_r

    return {
        "entry_time": df.index[i0],
        "exit_time":  df.index[exit_idx],
        "direction":  direction,
        "reason":     reason,
        "pnl_r":      round(pnl_r_net, 4),
        "duration_h": exit_idx - i0,
    }


def run_config(df, entries, exit_cfg, cfg):
    """Ejecuta una config de salida respetando 'una posicion a la vez'."""
    trades = []
    busy_until = -1
    for ent in entries:
        if ent["entry_idx"] <= busy_until:
            continue  # ya hay posicion abierta
        res = simulate_v3(df, ent, exit_cfg, cfg)
        trades.append(res)
        # bloquear nuevas entradas hasta que cierre esta
        exit_idx = df.index.get_loc(res["exit_time"])
        busy_until = exit_idx
    return pd.DataFrame(trades)


def metrics(trades, cfg, initial_equity=500.0):
    if trades.empty or len(trades) < 5:
        return None
    pnl = trades["pnl_r"]
    total = len(pnl)
    wins  = (pnl > 0).sum()
    losses= (pnl < 0).sum()
    be    = (pnl == 0).sum()
    wr    = round(wins/total*100, 1)
    gp    = pnl[pnl > 0].sum()
    gl    = pnl[pnl < 0].abs().sum()
    pf    = round(gp/gl, 3) if gl > 0 else float("inf")
    exp_r = round(pnl.mean(), 3)
    total_r = round(pnl.sum(), 2)
    avg_win  = round(pnl[pnl > 0].mean(), 3) if wins > 0 else 0
    avg_loss = round(pnl[pnl < 0].mean(), 3) if losses > 0 else 0

    eq = [initial_equity]
    for r in pnl:
        eq.append(eq[-1]*(1 + cfg.risk*r))
    eq_s = pd.Series(eq)
    max_dd = round(((eq_s-eq_s.cummax())/eq_s.cummax()).min()*100, 2)
    ret    = round((eq[-1]-initial_equity)/initial_equity*100, 2)

    months = max(1, (trades["entry_time"].max()-trades["entry_time"].min()).days/30)
    freq   = round(total/months, 1)

    # desglose por razon de salida
    reasons = trades["reason"].value_counts().to_dict()

    return {"trades":total, "wins":wins, "losses":losses, "be":be, "wr":wr,
            "pf":pf, "exp_r":exp_r, "avg_win":avg_win, "avg_loss":avg_loss,
            "total_r":total_r, "max_dd":max_dd, "ret":ret, "freq":freq,
            "reasons":reasons, "eq_final":round(eq[-1],2)}


def passes(m):
    if m is None: return False
    return m["pf"]>=1.5 and m["max_dd"]>=-10 and m["exp_r"]>0 and m["freq"]>=4


def print_metrics(label, m):
    if m is None:
        print(f"  {label}: insuficiente")
        return
    ok = "✓ PASA" if passes(m) else "✗ no pasa"
    r = m["reasons"]
    print(f"  {label}")
    print(f"    Trades={m['trades']} (W={m['wins']} L={m['losses']} BE={m['be']})  "
          f"WR={m['wr']}%  PF={m['pf']}  ExpR={m['exp_r']}")
    print(f"    AvgWin={m['avg_win']}R  AvgLoss={m['avg_loss']}R  TotalR={m['total_r']}  "
          f"MaxDD={m['max_dd']}%  Freq={m['freq']}/mes")
    print(f"    Salidas: {r}")
    print(f"    {ok}")


if __name__ == "__main__":
    cfg = Config()
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    grand = {c: {"2022": [], "2023": []} for c in EXIT_CONFIGS}
    all_trades = []

    for symbol in SYMBOLS:
        print(f"\n{'#'*72}\n  {symbol}\n{'#'*72}")
        print(f"  Descargando {symbol}...")
        df1h = download(symbol, "1h", "1 Jan, 2022", "31 Dec, 2023")
        time.sleep(1)
        df4h = download(symbol, "4h", "1 Jan, 2022", "31 Dec, 2023")
        df = build_features(df1h, df4h, cfg)

        for period, (a, b) in [("2022", ("2022-01-01","2022-12-31")),
                                ("2023", ("2023-01-01","2023-12-31"))]:
            dfp = df.loc[a:b]
            entries = find_entries(dfp, cfg)
            print(f"\n  ── {symbol} {period} — {len(entries)} señales T1 ──")
            for cname, ecfg in EXIT_CONFIGS.items():
                trades = run_config(dfp, entries, ecfg, cfg)
                m = metrics(trades, cfg)
                print_metrics(f"{cname}", m)
                if m: grand[cname][period].append((symbol, m))
                if not trades.empty:
                    all_trades.append(trades.assign(symbol=symbol, periodo=period, config=cname))
        time.sleep(1)

    # ── Agregados por configuracion y periodo ────────────────────────────
    print(f"\n{'='*72}\n  AGREGADO POR CONFIGURACION (todos los activos)\n{'='*72}")
    if all_trades:
        big = pd.concat(all_trades, ignore_index=True)
        for cname in EXIT_CONFIGS:
            for period in ["2022","2023"]:
                sub = big[(big["config"]==cname) & (big["periodo"]==period)]
                m = metrics(sub, cfg)
                print_metrics(f"{cname} — {period} (BTC+ETH+SOL)", m)
                print()

        big.to_csv("v3_barxbar_trades.csv", index=False)
        print(f"Trades exportados a v3_barxbar_trades.csv ({len(big)} trades)")

    # ── Tabla comparativa final ──────────────────────────────────────────
    print(f"\n{'='*72}\n  COMPARATIVA V3-A vs V3-B — PF por activo y periodo\n{'='*72}")
    print(f"  {'Activo':<9}{'Periodo':<8}{'V3-A PF':>9}{'V3-B PF':>9}{'V3-A DD':>9}{'V3-B DD':>9}")
    print("  " + "-"*52)
    for symbol in SYMBOLS:
        for period in ["2022","2023"]:
            ma = next((m for s,m in grand["V3-A (1R/2R/1R)"][period] if s==symbol), None)
            mb = next((m for s,m in grand["V3-B (0.75R/1.5R/0.75R)"][period] if s==symbol), None)
            pa = ma["pf"] if ma else "-"
            pb = mb["pf"] if mb else "-"
            da = ma["max_dd"] if ma else "-"
            db_ = mb["max_dd"] if mb else "-"
            print(f"  {symbol:<9}{period:<8}{str(pa):>9}{str(pb):>9}{str(da):>9}{str(db_):>9}")

    print("\n  Recordatorio: 2024 permanece CIEGO hasta seleccionar configuracion.")
    print("  Pega el output completo.")
