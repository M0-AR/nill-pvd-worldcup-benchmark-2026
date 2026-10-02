"""Performance + statistical validity metrics (best-practice set)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252

def equity_metrics(eq: pd.Series) -> dict:
    eq = eq.dropna()
    if len(eq) < 2:
        return {"n": 0}
    rets = eq.pct_change().dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1)
    yrs = max(1e-9, (eq.index[-1] - eq.index[0]).days / 365.25)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) if yrs > 0 else 0.0
    vol = float(rets.std() * np.sqrt(TRADING_DAYS)) if len(rets) > 1 else 0.0
    sharpe = float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS)) if rets.std() > 0 else 0.0
    downside = rets[rets < 0].std()
    sortino = float(rets.mean() / downside * np.sqrt(TRADING_DAYS)) if downside and downside > 0 else 0.0
    roll_max = eq.cummax()
    dd = (eq / roll_max - 1)
    maxdd = float(dd.min())
    calmar = float(cagr / abs(maxdd)) if maxdd < 0 else 0.0
    return {"n_bars": int(len(eq)), "total_ret": tot, "CAGR": cagr, "vol": vol,
            "Sharpe": sharpe, "Sortino": sortino, "MaxDD": maxdd, "Calmar": calmar,
            "years": float(yrs), "final_equity": float(eq.iloc[-1])}

def trade_metrics(tr: pd.DataFrame) -> dict:
    if tr is None or len(tr) == 0:
        return {"n_trades": 0}
    pnl = tr["pnl"].to_numpy(dtype=float)
    wins = (pnl > 0).sum()
    n = len(pnl)
    wr = float(wins / n)
    gp = float(pnl[pnl > 0].sum()); gl = float(-pnl[pnl < 0].sum())
    pf = float(gp / gl) if gl > 0 else float("inf") if gp > 0 else 0.0
    exp = float(pnl.mean())
    avgR = float(tr["R"].mean()) if "R" in tr else 0.0
    # t-stat of mean R / mean pnl vs 0
    t, p = (float("nan"), float("nan"))
    if n >= 3 and np.std(pnl, ddof=1) > 0:
        t, p = stats.ttest_1samp(pnl, 0.0)
        t, p = float(t), float(p)
    by_setup = tr.groupby("setup")["pnl"].agg(["count", "mean", "sum"]).to_dict(orient="index") if "setup" in tr else {}
    return {"n_trades": int(n), "win_rate": wr, "profit_factor": pf,
            "expectancy": exp, "avg_R": avgR, "gross_profit": gp, "gross_loss": gl,
            "t_stat": t, "t_pvalue": p, "by_setup": by_setup,
            "avg_bars": float(tr["bars"].mean()) if "bars" in tr else float("nan")}

def permutation_pvalue(daily_pnl: pd.Series, n_perm: int = 2000, seed: int = 7) -> float:
    """Two-sided permutation test: is mean(daily_pnl) > 0 beyond luck?"""
    x = daily_pnl.dropna().to_numpy(dtype=float)
    if len(x) < 10:
        return float("nan")
    obs = x.mean()
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_perm):
        s = rng.choice([-1.0, 1.0], size=len(x))
        if (x * s).mean() >= obs:
            cnt += 1
    return float((cnt + 1) / (n_perm + 1))

def walk_forward_summary(folds: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(folds)
