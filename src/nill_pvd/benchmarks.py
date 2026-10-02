"""Benchmarks run on identical data/costs so PVD is judged fairly."""
from __future__ import annotations
import numpy as np
import pandas as pd

def _to_trades_from_positions(df: pd.DataFrame, pos: pd.Series, fee_bps=5.0, equity0=100_000.0) -> tuple[pd.Series, pd.DataFrame]:
    # pos in {-1,0,1}, trade at next open, fixed fractional? use buy-hold style equity
    rets = df["close"].pct_change().fillna(0)
    strat_rets = pos.shift(1).fillna(0) * rets
    # costs: turnover * fee
    turnover = pos.diff().abs().fillna(0)
    costs = turnover * fee_bps / 1e4
    net = strat_rets - costs
    eq = (1 + net).cumprod() * equity0
    eq.index = df.index
    # pseudo-trades: segments
    return eq, pd.DataFrame({"note": ["benchmark path; see equity"]})

def buy_hold(df, **k):
    pos = pd.Series(1, index=df.index)
    return _to_trades_from_positions(df, pos, fee_bps=k.get("fee_bps", 5.0))

def sma_trend(df, fast=20, slow=100, **k):
    sma_f = df["close"].rolling(fast).mean()
    sma_s = df["close"].rolling(slow).mean()
    pos = pd.Series(np.where(sma_f > sma_s, 1, -1), index=df.index)
    return _to_trades_from_positions(df, pos, fee_bps=k.get("fee_bps", 5.0))

def bollinger_fade(df, win=20, z=2.0, **k):
    m = df["close"].rolling(win).mean(); s = df["close"].rolling(win).std()
    up = m + z * s; lo = m - z * s
    pos = pd.Series(0, index=df.index)
    pos[df["close"] > up] = -1
    pos[df["close"] < lo] = 1
    # hold 5 bars
    pos = pos.replace(0, np.nan).ffill(limit=5).fillna(0)
    return _to_trades_from_positions(df, pos, fee_bps=k.get("fee_bps", 5.0))

def orb(df, n=20, **k):
    # opening-range proxy on daily bars: prior n-day high/low breakout
    hi = df["high"].rolling(n).max().shift(1); lo = df["low"].rolling(n).min().shift(1)
    pos = pd.Series(0, index=df.index)
    pos[df["close"] > hi] = 1
    pos[df["close"] < lo] = -1
    pos = pos.replace(0, np.nan).ffill(limit=10).fillna(0)
    return _to_trades_from_positions(df, pos, fee_bps=k.get("fee_bps", 5.0))

def random_trades(df, seed=0, p=0.02, **k):
    rng = np.random.default_rng(seed)
    r = rng.random(len(df))
    pos = pd.Series(0, index=df.index)
    pos[r < p / 2] = 1
    pos[(r >= p / 2) & (r < p)] = -1
    pos = pos.replace(0, np.nan).ffill(limit=5).fillna(0)
    return _to_trades_from_positions(df, pos, fee_bps=k.get("fee_bps", 5.0))

BENCHMARKS = {"buy_hold": buy_hold, "sma_trend": sma_trend, "bollinger_fade": bollinger_fade, "orb": orb, "random": random_trades}
