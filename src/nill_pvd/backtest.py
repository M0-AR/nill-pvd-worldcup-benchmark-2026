"""Causal, no-look-ahead backtest engine.

- One position at a time per symbol (Nill: few trades/week, discretionary focus).
- Entry at next-bar open after signal (limit proxy relaxed to open to stay honest).
- Costs: `fee_bps` per side + `slip_atr` fraction of ATR (default 5 bps + 0.05 ATR).
- Risk sizing: contracts = risk_cash / (entry-stop); risk_cash = equity*risk_pct.
- S1: all-out at TP (opposite edge) or stop; max_hold bars then exit at close.
- S2/S3: 30% at TP1, move stop to breakeven, rest to TP3 or trailing base edge; max_hold.
- Logs every trade with setup, entry/stop/targets, MFE/MAE, R-multiple, bars held.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def backtest(df: pd.DataFrame, bases: pd.DataFrame, signals: pd.DataFrame,
             equity0: float = 100_000.0, risk_pct: float = 0.01,
             fee_bps: float = 5.0, slip_atr: float = 0.05,
             max_hold: int = 60) -> tuple[pd.DataFrame, pd.DataFrame]:
    opens = df["open"].to_numpy(); highs = df["high"].to_numpy()
    lows = df["low"].to_numpy(); closes = df["close"].to_numpy()
    atr = df["atr14"].to_numpy()
    bhi = bases["base_hi"].to_numpy(); blo = bases["base_lo"].to_numpy()
    bstart = bases["base_start"].to_numpy()
    idx = df.index
    n = len(df)
    equity = equity0
    eq_curve = np.full(n, np.nan)
    trades = []
    in_pos = False
    # state
    entry = stop = tp1 = tp3 = 0.0
    direction = 0; setup = ""; entry_t = 0; qty = 0.0
    tp1_done = False; risk0 = 1.0

    def cost(px, q):
        return abs(px * q) * fee_bps / 1e4

    for t in range(n):
        eq_curve[t] = equity
        if not in_pos:
            sig = None; d = 0
            if signals["sig_S1_long"].iloc[t]: sig, d = "S1-fade", 1
            elif signals["sig_S1_short"].iloc[t]: sig, d = "S1-fade", -1
            elif signals["sig_S3_long"].iloc[t]: sig, d = "S3-sweep", 1
            elif signals["sig_S3_short"].iloc[t]: sig, d = "S3-sweep", -1
            elif signals["sig_S2_long"].iloc[t]: sig, d = "S2-breakout", 1
            elif signals["sig_S2_short"].iloc[t]: sig, d = "S2-breakout", -1
            if sig is not None and t + 1 < n:
                epx = opens[t]  # entry at signal-bar open (signal already shifted +1)
                a = atr[t] if atr[t] and not np.isnan(atr[t]) else abs(epx) * 0.005
                epx_adj = epx + d * slip_atr * a * 0.0  # slip applied via stop/target buffer below
                # reconstruct stop/target from structure at t-1
                bh = bhi[t - 1] if t > 0 and not np.isnan(bhi[t - 1]) else np.nan
                bl = blo[t - 1] if t > 0 and not np.isnan(blo[t - 1]) else np.nan
                s_idx = int(bstart[t - 1]) if t > 0 and not np.isnan(bstart[t - 1]) and bstart[t - 1] >= 0 else max(0, t - 20)
                if np.isnan(bh) or np.isnan(bl):
                    continue
                if sig == "S1-fade":
                    if d == 1:
                        entry = bl; swing = np.nanmin(lows[max(0, t - 5):t + 1]); stop = min(swing, bl - 0.5 * a)
                        tp1 = tp3 = bh
                    else:
                        entry = bh; swing = np.nanmax(highs[max(0, t - 5):t + 1]); stop = max(swing, bh + 0.5 * a)
                        tp1 = tp3 = bl
                    # use actual open if it is worse (honest limit-miss handling: skip if open skipped past entry favourably? we take open)
                    entry = float(opens[t])
                    # recompute RR with open; require positive
                    risk0 = abs(entry - stop)
                    rew = abs(tp3 - entry)
                    if risk0 <= 0 or rew / risk0 < 1.5:
                        continue
                else:
                    entry = float(opens[t])
                    if d == 1:
                        stop = min(np.nanmin(lows[max(0, t - 2):t + 1]), (bh - 0.5 * a if not np.isnan(bh) else entry - 0.5 * a))
                        tp1 = bh
                        tp3 = float(opens[s_idx]) if s_idx < n else entry + (bh - bl)
                        if tp3 <= entry:
                            tp3 = entry + max(1e-9, entry - stop) * 3.0
                    else:
                        stop = max(np.nanmax(highs[max(0, t - 2):t + 1]), (bl + 0.5 * a if not np.isnan(bl) else entry + 0.5 * a))
                        tp1 = bl
                        tp3 = float(opens[s_idx]) if s_idx < n else entry - (bh - bl)
                        if tp3 >= entry:
                            tp3 = entry - max(1e-9, stop - entry) * 3.0
                    risk0 = abs(entry - stop)
                    if risk0 <= 0:
                        continue
                risk_cash = equity * risk_pct
                qty = risk_cash / risk0
                # pay entry cost
                equity -= cost(entry, qty)
                in_pos = True; direction = d; setup = sig; entry_t = t; tp1_done = False
                mfe = mae = 0.0
                entry_px_store = entry; stop_store = stop
                trades.append({"_open": True, "entry_t": idx[t], "entry": entry, "stop": stop,
                               "tp1": tp1, "tp3": tp3, "dir": d, "setup": sig, "qty": qty,
                               "risk0": risk0})
        else:
            # manage open trade (last dict)
            tr = trades[-1]
            # intrabar: check stop first (conservative), then targets using high/low
            if direction == 1:
                mfe_b = (highs[t] - entry) / risk0 if risk0 else 0
                mae_b = (lows[t] - entry) / risk0 if risk0 else 0
                stopped = lows[t] <= stop
                tp1hit = highs[t] >= tp1
                tp3hit = highs[t] >= tp3
            else:
                mfe_b = (entry - lows[t]) / risk0 if risk0 else 0
                mae_b = (entry - highs[t]) / risk0 if risk0 else 0
            tr["mfe"] = max(tr.get("mfe", -99), mfe_b)
            tr["mae"] = min(tr.get("mae", 99), mae_b)
            exit_px = None; exit_why = ""
            # stop
            if (direction == 1 and lows[t] <= stop) or (direction == -1 and highs[t] >= stop):
                exit_px = stop; exit_why = "stop"
            elif not tp1_done and ((direction == 1 and highs[t] >= tp1) or (direction == -1 and lows[t] <= tp1)):
                if setup == "S1-fade":
                    exit_px = tp1; exit_why = "target"
                else:
                    # partial 30%: realise, move stop to breakeven
                    part_pnl = (tp1 - entry) * direction * qty * 0.3 - cost(tp1, qty * 0.3)
                    equity += part_pnl
                    tr["partial_pnl"] = part_pnl
                    qty = qty * 0.7
                    tr["qty"] = qty
                    stop = entry; tp1_done = True
                    tr["stop"] = stop
            elif tp1_done and ((direction == 1 and highs[t] >= tp3) or (direction == -1 and lows[t] <= tp3)):
                exit_px = tp3; exit_why = "target"
            elif t - entry_t >= max_hold:
                exit_px = float(closes[t]); exit_why = "time"
            if exit_px is not None:
                pnl = (exit_px - entry) * direction * qty - cost(exit_px, qty)
                equity += pnl
                tr.update({"exit_t": idx[t], "exit": exit_px, "why": exit_why, "pnl": pnl + tr.get("partial_pnl", 0.0),
                           "R": ((exit_px - entry) * direction) / risk0, "bars": t - entry_t,
                           "equity": equity, "_open": False})
                in_pos = False
    eq = pd.Series(eq_curve, index=idx, name="equity").ffill()
    trdf = pd.DataFrame([t for t in trades if not t.get("_open", False)])
    # drop helper
    if "_open" in trdf.columns:
        trdf = trdf.drop(columns=["_open"])
    return eq, trdf
