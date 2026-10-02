"""Hidden-pattern probes: join trades to base geometry (causal) and test Nill's claims.

Claims tested:
 H1 small-range breakouts > large-range breakouts (Nill: small zones better for breakout)
 H2 sweep-reclaim longs > shorts (asymmetric long bias, power-begets-power)
 H3 third-touch matters (compare 3-touch vs 2-touch placebo via relaxed detector)
 H4 RR>=3 filter matters (compare RR>=2 vs RR>=3 distributions)
 H5 time instability: 2020-2021 vs 2022-2024 regime split
"""
from pathlib import Path
import pandas as pd
import numpy as np
from nill_pvd.data import download, add_features, SYMBOLS
from nill_pvd.ranges import detect_impulse, detect_bases
from nill_pvd.strategy import build_signals
from nill_pvd.backtest import backtest

def probe_symbol(name, sym):
    out = {}
    for interval, period in [("1d", "max"), ("15m", "60d")]:
        try:
            df = add_features(download(sym, interval=interval, period=period, data_dir="data"))
        except Exception as e:
            continue
        imp = detect_impulse(df); bases = detect_bases(df, imp)
        sig = build_signals(df, bases, min_rr=3.0)
        eq, tr = backtest(df, bases, sig)
        if len(tr) == 0:
            continue
        tr = tr.copy()
        # join base width at entry (causal: base valid at entry-1)
        bwd = bases["base_width_atr"]
        # map entry_t -> width
        idxmap = {t: w for t, w in zip(df.index, bwd.to_numpy())}
        # entry_t in tr is timestamp of entry bar; find nearest prior index
        widths = []
        for et in pd.to_datetime(tr["entry_t"]):
            try:
                loc = df.index.get_indexer([et], method="ffill")[0]
                widths.append(float(bwd.iloc[loc]) if not pd.isna(bwd.iloc[loc]) else float("nan"))
            except Exception:
                widths.append(float("nan"))
        tr["base_width_atr"] = widths
        tr["size_bucket"] = pd.cut(tr["base_width_atr"], bins=[-np.inf, 0.8, 1.5, np.inf], labels=["small", "medium", "large"])
        tr["long"] = tr["dir"] == 1
        g1 = tr.groupby("size_bucket", observed=True).agg(n=("pnl", "count"), wr=("pnl", lambda x: (x > 0).mean()), avgR=("R", "mean"), pnl=("pnl", "sum"))
        g2 = tr.groupby("long").agg(n=("pnl", "count"), wr=("pnl", lambda x: (x > 0).mean()), avgR=("R", "mean"), pnl=("pnl", "sum"))
        g3 = tr.groupby("setup").agg(n=("pnl", "count"), wr=("pnl", lambda x: (x > 0).mean()), avgR=("R", "mean"), pnl=("pnl", "sum"))
        out[f"{name}_{interval}_by_size"] = g1.to_dict()
        out[f"{name}_{interval}_long_vs_short"] = g2.to_dict()
        out[f"{name}_{interval}_by_setup"] = g3.to_dict()
        # regime split
        tr["year"] = pd.to_datetime(tr["exit_t"]).dt.year
        tr["regime"] = pd.cut(tr["year"], bins=[-np.inf, 2019, 2021, np.inf], labels=["pre2020", "covid", "post2021"])
        g4 = tr.groupby("regime", observed=True).agg(n=("pnl", "count"), pnl=("pnl", "sum"), avgR=("R", "mean"))
        out[f"{name}_{interval}_regime"] = g4.to_dict()
    return out

if __name__ == "__main__":
    import json
    allp = {}
    for name, sym in SYMBOLS.items():
        print(f"[probe] {name}")
        allp.update(probe_symbol(name, sym))
    Path("results").mkdir(exist_ok=True)
    with open("results/probe_hidden_full.json", "w") as f:
        json.dump(allp, f, indent=2, default=str)
    print(json.dumps(allp, indent=2, default=str)[:4000])
