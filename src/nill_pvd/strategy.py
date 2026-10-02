"""Three Nill-style setups as fully specified, backtestable rules.

S1 RANGE-FADE (counter-trend, Nill's favourite feel):
  trigger: valid base (3 touches) + close in extreme third, no breakout.
  entry next bar open at/near extreme (limit proxy = extreme).
  stop: beyond opposite? No — beyond entry extreme by k*ATR (default 0.5) or
        beyond structural swing (rolling 5-bar extreme), whichever is larger,
        then enforce RR>=min_rr (default 3) else skip.
  target: opposite extreme (fair-value to fair-value). No partials by default.

S2 BREAKOUT-PULLBACK (trend-follow, "better trade"):
  trigger: close outside base (breakout bar) + confirmation bar:
     (a) next close further outside, OR (b) dip back into range then close back outside.
  entry next bar open.
  stop: beyond false-break extreme (low of sweep) or 0.5*ATR beyond base edge.
  targets: TP1 = prior base far edge (for shorts from upside breakout: upside of
     prior zone), TP2 = mid/decision, TP3 = impulse origin (base_start open).
     Partial 30% at TP1 (breakeven after), rest to TP3. Trail option: move stop
     under newly formed fair value (implemented as trailing base edge).

S3 SWEEP-RECLAIM (failed-breakout, best RR):
  trigger: wick beyond base by >=0.25*ATR but close back inside, then next
     close beyond sweep-bar extreme in reclaim direction.
  entry next bar open. Stop beyond sweep extreme + buffer.
  target: full impulse (origin) — holds through range top (does NOT exit at top).

Filters (all from transcript):
  - NEWS blackout: skip if |ret| > news_thresh*ATR-based (proxy for headline shock) on trigger day
  - LATE filter: skip last `late_bars` of sample if base formed in evening (proxy for overnight gap risk)
  - TIME-OF-DAY: optional session flag; US-open (14:00 CET proxy) handled in analysis not entry
  - RR floor: require expected RR >= min_rr else skip (Nill: waits for RR 3-8)

Position sizing: risk `risk_pct` of equity per trade (default 1% private; 2.5% championship variant).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def build_signals(df: pd.DataFrame, bases: pd.DataFrame,
                  min_rr: float = 3.0, atr_stop_mult: float = 0.5,
                  sweep_mult: float = 0.25) -> pd.DataFrame:
    n = len(df)
    idx = df.index
    out = pd.DataFrame(index=idx)
    out["sig_S1_long"] = False
    out["sig_S1_short"] = False
    out["sig_S2_long"] = False
    out["sig_S2_short"] = False
    out["sig_S3_long"] = False
    out["sig_S3_short"] = False
    # params stored for backtest
    out["entry_px"] = np.nan
    out["stop_px"] = np.nan
    out["tp1_px"] = np.nan
    out["tp3_px"] = np.nan
    out["direction"] = 0
    out["setup"] = ""

    highs = df["high"].to_numpy(); lows = df["low"].to_numpy()
    opens = df["open"].to_numpy(); closes = df["close"].to_numpy()
    atr = df["atr14"].to_numpy()
    # Use last-valid-base carried forward up to 20 bars so breakouts/sweeps
    # occurring just AFTER a base ends are still testable (causal ffill).
    _bhi_raw = bases["base_hi"].copy()
    _blo_raw = bases["base_lo"].copy()
    _bstart_raw = bases["base_start"].copy()
    _valid_raw = bases["base_valid_3t"].copy()
    _last_hi = _bhi_raw.ffill(limit=20)
    _last_lo = _blo_raw.ffill(limit=20)
    _last_start = _bstart_raw.ffill(limit=20)
    _last_valid = _valid_raw.ffill(limit=20).fillna(False).to_numpy()
    bhi = _last_hi.to_numpy(); blo = _last_lo.to_numpy()
    valid = _last_valid
    bstart = _last_start.to_numpy()
    raw_hi = bases["base_hi"].to_numpy()
    raw_active = ~__import__("numpy").isnan(raw_hi)

    for t in range(2, n - 1):
        if np.isnan(bhi[t]) or not valid[t]:
            continue
        a = atr[t] if atr[t] and not np.isnan(atr[t]) and atr[t] > 0 else (bhi[t] - blo[t] if bhi[t] > blo[t] else np.nan)
        if np.isnan(a) or a <= 0:
            continue
        rng = bhi[t] - blo[t]
        if rng <= 0:
            continue
        up_thr = bhi[t] - rng / 3
        lo_thr = blo[t] + rng / 3
        c = closes[t]
        # ---- S1 fade ---- (only when base still active; ffill is for S2/S3 only)
        # long at lower extreme
        if raw_active[t] and c <= lo_thr and closes[t - 1] > blo[t] - a:  # inside, not broken
            # ensure no breakout close outside
            if not (c < blo[t] - 0.2 * a or c > bhi[t] + 0.2 * a):
                entry = blo[t]
                swing = np.nanmin(lows[max(0, t - 5):t + 1])
                stop = min(swing, blo[t] - atr_stop_mult * a)
                # structural fallback: if stop too tight (<0.25a) widen to 0.5a
                if entry - stop < 0.25 * a:
                    stop = entry - atr_stop_mult * a
                target = bhi[t]
                rr = (target - entry) / max(1e-9, entry - stop)
                if rr >= min_rr:
                    out.iat[t + 1, out.columns.get_loc("sig_S1_long")] = True
        if raw_active[t] and c >= up_thr and closes[t - 1] < bhi[t] + a:
            if not (c < blo[t] - 0.2 * a or c > bhi[t] + 0.2 * a):
                entry = bhi[t]
                swing = np.nanmax(highs[max(0, t - 5):t + 1])
                stop = max(swing, bhi[t] + atr_stop_mult * a)
                if stop - entry < 0.25 * a:
                    stop = entry + atr_stop_mult * a
                target = blo[t]
                rr = (entry - target) / max(1e-9, stop - entry)
                if rr >= min_rr:
                    out.iat[t + 1, out.columns.get_loc("sig_S1_short")] = True
        # ---- S2 breakout-pullback ----
        # upside breakout at t-1 confirmed at t
        if t >= 2:
            prev_out_up = closes[t - 1] > bhi[t - 1] + 0.05 * a if not np.isnan(bhi[t - 1]) else False
            if prev_out_up:
                cond_a = c > closes[t - 1]  # closes higher
                dipped = lows[t] <= bhi[t - 1] if not np.isnan(bhi[t - 1]) else False
                cond_b = dipped and (c > bhi[t - 1])
                if cond_a or cond_b:
                    entry = c  # market proxy next open handled in backtest; store c
                    stop = min(np.nanmin(lows[t - 1:t + 1]), bhi[t - 1] - atr_stop_mult * a) if not np.isnan(bhi[t - 1]) else c - atr_stop_mult * a
                    # targets
                    tp1 = bhi[t - 1]
                    s = int(bstart[t - 1]) if not np.isnan(bstart[t - 1]) and bstart[t - 1] >= 0 else max(0, t - 20)
                    tp3 = opens[s] if s < n else c + rng
                    # measured-move extension for ATH case: 1x risk beyond entry
                    risk = max(1e-9, entry - stop)
                    if tp3 <= entry:
                        tp3 = entry + risk * 3.0
                    rr = (tp3 - entry) / risk
                    if rr >= 2.0:  # allow slightly lower for breakout (trend-follow)
                        out.iat[t + 1, out.columns.get_loc("sig_S2_long")] = True
            prev_out_dn = closes[t - 1] < blo[t - 1] - 0.05 * a if not np.isnan(blo[t - 1]) else False
            if prev_out_dn:
                cond_a = c < closes[t - 1]
                peaked = highs[t] >= blo[t - 1] if not np.isnan(blo[t - 1]) else False
                cond_b = peaked and (c < blo[t - 1])
                if cond_a or cond_b:
                    entry = c
                    stop = max(np.nanmax(highs[t - 1:t + 1]), blo[t - 1] + atr_stop_mult * a) if not np.isnan(blo[t - 1]) else c + atr_stop_mult * a
                    tp1 = blo[t - 1]
                    s = int(bstart[t - 1]) if not np.isnan(bstart[t - 1]) and bstart[t - 1] >= 0 else max(0, t - 20)
                    tp3 = opens[s] if s < n else c - rng
                    risk = max(1e-9, stop - entry)
                    if tp3 >= entry:
                        tp3 = entry - risk * 3.0
                    rr = (entry - tp3) / risk
                    if rr >= 2.0:
                        out.iat[t + 1, out.columns.get_loc("sig_S2_short")] = True
        # ---- S3 sweep-reclaim (favourite long) ----
        # sweep below then reclaim
        if lows[t - 1] < blo[t - 1] - sweep_mult * a and closes[t - 1] > blo[t - 1] if not np.isnan(blo[t - 1]) else False:
            if c > closes[t - 1] and c > blo[t - 1]:
                entry = c
                stop = np.nanmin(lows[t - 1:t + 1]) - 0.1 * a
                s = int(bstart[t - 1]) if not np.isnan(bstart[t - 1]) and bstart[t - 1] >= 0 else max(0, t - 20)
                tp3 = opens[s]
                if tp3 <= entry:
                    tp3 = entry + (entry - stop) * 3.0
                rr = (tp3 - entry) / max(1e-9, entry - stop)
                if rr >= min_rr:
                    out.iat[t + 1, out.columns.get_loc("sig_S3_long")] = True
        if highs[t - 1] > bhi[t - 1] + sweep_mult * a and closes[t - 1] < bhi[t - 1] if not np.isnan(bhi[t - 1]) else False:
            if c < closes[t - 1] and c < bhi[t - 1]:
                entry = c
                stop = np.nanmax(highs[t - 1:t + 1]) + 0.1 * a
                s = int(bstart[t - 1]) if not np.isnan(bstart[t - 1]) and bstart[t - 1] >= 0 else max(0, t - 20)
                tp3 = opens[s]
                if tp3 >= entry:
                    tp3 = entry - (stop - entry) * 3.0
                rr = (entry - tp3) / max(1e-9, stop - entry)
                if rr >= min_rr:
                    out.iat[t + 1, out.columns.get_loc("sig_S3_short")] = True
    return out
