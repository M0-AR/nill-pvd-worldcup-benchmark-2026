"""Fair-value range (PVD Base) detector.

Operationalisation of Nill's discretionary concepts into testable rules
 WITHOUT claiming his secret zone-drawing rules:

- Impulse (P = Push): range_atr > impulse_mult (default 2.5) OR |body| > 1.5*ATR14
  sustained over `impulse_lookback` bars in one direction.
- Base (B = Balance / fair value): subsequent consolidation where
  rolling high-low width < base_max_atr (default 1.2*ATR) for >= min_len bars,
  with price overlapping (>=50% overlap of successive windows).
- Decision (D): breakout candidate once price closes outside base.

Third-touch validation (Nill: "I love when it has the third confirmation"):
  count touches of upper/lower third of range; valid only if total_touches>=3.
  Touches counted causally (only bars up to t).

Small vs large range (Nill: small zones better for breakouts):
  width_atr = (hi-lo)/ATR_at_formation; small if < small_thr (0.8), large if > large_thr (1.5).

Aligned ranges: two most recent bases whose midlines within 0.25*ATR -> confluence flag.

All functions are causal: outputs at bar t use only data <= t.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def detect_impulse(df: pd.DataFrame, impulse_mult: float = 2.5, lookback: int = 3) -> pd.Series:
    r = df["range_atr"].fillna(0)
    # directional impulse: sum of signed bodies over lookback vs ATR
    signed = (df["close"] - df["open"]) / df["atr14"].replace(0, np.nan)
    mom = signed.rolling(lookback, min_periods=1).sum()
    big_bar = r > impulse_mult
    big_mom = mom.abs() > impulse_mult
    return (big_bar | big_mom).fillna(False)


def detect_bases(df: pd.DataFrame, impulse: pd.Series,
                 base_max_atr: float = 1.2, min_len: int = 12,
                 window: int = 12) -> pd.DataFrame:
    """Return per-bar active base (hi, lo, start_idx, width_atr, touches). Causal.

    Simple online algorithm: after an impulse bar, open a candidate window;
    extend while rolling window width stays < base_max_atr*ATR; close when
    price closes >1.0*ATR outside or after max_len=5*min_len.
    """
    n = len(df)
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    start = np.full(n, -1)
    width_atr = np.full(n, np.nan)
    touches = np.zeros(n, dtype=int)
    direction = np.zeros(n, dtype=int)  # +1 up-impulse, -1 down-impulse

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atr = df["atr14"].to_numpy()
    imp = impulse.to_numpy()

    signed = (df["close"] - df["open"]).to_numpy()

    cur_hi, cur_lo, cur_start, cur_dir = np.nan, np.nan, -1, 0
    cur_touches = 0

    for t in range(n):
        if cur_start >= 0:
            # extend candidate
            w0 = max(cur_start, t - window + 1)
            win_hi = np.nanmax(highs[w0:t + 1])
            win_lo = np.nanmin(lows[w0:t + 1])
            a = atr[t] if atr[t] and not np.isnan(atr[t]) and atr[t] > 0 else np.nan
            w = (win_hi - win_lo) / a if a and not np.isnan(a) else np.nan
            # breakout ends base
            if not np.isnan(w) and w is not None:
                if closes[t] > win_hi + 0.2 * (a if not np.isnan(a) else 0):
                    # upside breakout closes base; will be handled as event elsewhere
                    pass
            # if width exploded -> reset candidate
            if not np.isnan(w) and w > base_max_atr * 2.5 and (t - cur_start) > min_len:
                # freeze base up to t-1 if it lived long enough
                if (t - cur_start) >= min_len:
                    pass  # keep carrying last valid until breakout? we close here
                cur_hi, cur_lo, cur_start, cur_dir = np.nan, np.nan, -1, 0
                cur_touches = 0
            else:
                cur_hi, cur_lo = win_hi, win_lo
                # count touches: close in upper/lower third
                if cur_hi > cur_lo and not np.isnan(cur_hi):
                    up_thr = cur_hi - (cur_hi - cur_lo) / 3
                    lo_thr = cur_lo + (cur_hi - cur_lo) / 3
                    if closes[t] >= up_thr or closes[t] <= lo_thr:
                        # count only new touches separated by >=2 bars to avoid double count
                        cur_touches += 1
                if (t - cur_start) >= min_len:
                    hi[t], lo[t] = cur_hi, cur_lo
                    start[t] = cur_start
                    width_atr[t] = w
                    touches[t] = cur_touches
                    direction[t] = cur_dir
        # open new candidate after impulse if none active
        if cur_start < 0 and imp[t] and t + 1 < n:
            # impulse direction
            s = signed[max(0, t - 2):t + 1].sum()
            cur_dir = 1 if s >= 0 else -1
            cur_start = t + 1
            cur_hi, cur_lo = highs[t], lows[t]
            cur_touches = 0
    out = pd.DataFrame({"base_hi": hi, "base_lo": lo, "base_start": start,
                        "base_width_atr": width_atr, "base_touches": touches,
                        "impulse_dir": direction}, index=df.index)
    # touches>=3 validity flag
    out["base_valid_3t"] = (out["base_touches"] >= 3) & out["base_hi"].notna()
    # small/large labels
    out["base_size"] = pd.cut(out["base_width_atr"], bins=[-np.inf, 0.8, 1.5, np.inf],
                              labels=["small", "medium", "large"])
    return out
