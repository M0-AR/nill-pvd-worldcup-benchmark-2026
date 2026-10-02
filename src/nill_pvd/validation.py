"""Walk-forward, friction-sensitivity, year-stability, null controls."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .ranges import detect_impulse, detect_bases
from .strategy import build_signals
from .backtest import backtest
from .metrics import equity_metrics, trade_metrics

def expanding_walk_forward(df: pd.DataFrame, n_splits: int = 4, min_rr: float = 3.0,
                           risk_pct: float = 0.01, fee_bps: float = 5.0) -> list[dict]:
    n = len(df)
    folds = []
    # expanding: train 50%, then step through rest
    edges = np.linspace(int(n * 0.5), n, n_splits + 1, dtype=int)
    for i in range(n_splits):
        te0, te1 = int(edges[i]), int(edges[i + 1])
        sub = df.iloc[:te1].copy()  # expanding history (detector sees all history, but OOS pnl only on window)
        imp = detect_impulse(sub)
        bases = detect_bases(sub, imp)
        sig = build_signals(sub, bases, min_rr=min_rr)
        eq, tr = backtest(sub, bases, sig, risk_pct=risk_pct, fee_bps=fee_bps)
        # OOS slice
        oos_tr = tr[pd.to_datetime(tr["exit_t"]) >= df.index[te0]] if len(tr) else tr
        em = equity_metrics(eq)
        tm = trade_metrics(oos_tr)
        folds.append({"fold": i, "test_from": str(df.index[te0]), "test_to": str(df.index[te1 - 1]),
                      "n_oos": tm.get("n_trades", 0), "win_rate": tm.get("win_rate", float("nan")),
                      "profit_factor": tm.get("profit_factor", float("nan")),
                      "avg_R": tm.get("avg_R", float("nan")), "t_stat": tm.get("t_stat", float("nan"))})
    return folds

def friction_ladder(df: pd.DataFrame, fees: tuple = (0, 5, 10, 20), min_rr: float = 3.0) -> list[dict]:
    from .ranges import detect_impulse, detect_bases
    from .strategy import build_signals
    imp = detect_impulse(df); bases = detect_bases(df, imp); sig = build_signals(df, bases, min_rr=min_rr)
    rows = []
    for f in fees:
        eq, tr = backtest(df, bases, sig, fee_bps=float(f))
        from .metrics import equity_metrics, trade_metrics
        rows.append({"fee_bps": f, **equity_metrics(eq), **trade_metrics(tr)})
    return rows

def year_stability(tr: pd.DataFrame) -> pd.DataFrame:
    if tr is None or len(tr) == 0:
        return pd.DataFrame()
    tr = tr.copy()
    tr["year"] = pd.to_datetime(tr["exit_t"]).dt.year
    g = tr.groupby("year").agg(n=("pnl", "count"), pnl=("pnl", "sum"), win_rate=("pnl", lambda x: (x > 0).mean()), avg_R=("R", "mean"))
    return g
