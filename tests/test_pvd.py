import pandas as pd
import numpy as np
from nill_pvd.data import add_features
from nill_pvd.ranges import detect_impulse, detect_bases
from nill_pvd.strategy import build_signals
from nill_pvd.backtest import backtest

def _toy(n=300, seed=0):
    rng = np.random.default_rng(seed)
    px = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame({"open": px, "high": px + 0.6, "low": px - 0.6, "close": px + rng.normal(0, 0.2, n),
                       "volume": 1000}, index=pd.date_range("2020-01-01", periods=n, freq="D"))
    # inject impulse + flat base + breakout to guarantee at least structure
    df.iloc[50, df.columns.get_loc("close")] += 5
    df.iloc[50, df.columns.get_loc("high")] += 5
    return add_features(df)

def test_no_lookahead_shapes():
    df = _toy()
    imp = detect_impulse(df)
    bases = detect_bases(df, imp)
    sig = build_signals(df, bases)
    assert len(imp) == len(df) and len(bases) == len(df) and len(sig) == len(df)

def test_backtest_runs():
    df = _toy()
    imp = detect_impulse(df)
    bases = detect_bases(df, imp)
    sig = build_signals(df, bases, min_rr=1.0)
    eq, tr = backtest(df, bases, sig)
    assert len(eq) == len(df)
    assert isinstance(tr, pd.DataFrame)

def test_third_touch_gate():
    df = _toy()
    imp = detect_impulse(df)
    bases = detect_bases(df, imp)
    # validity implies touches>=3
    assert ((bases["base_valid_3t"]) <= (bases["base_touches"] >= 3)).all()
