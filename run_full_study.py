"""End-to-end study runner: daily regime + intraday execution, benchmarks, hidden patterns.

Outputs (all under results/):
  manifest.json, daily_summary.csv, intraday_summary.csv,
  walk_forward.csv, friction.csv, year_stability.csv, benchmarks.csv,
  hidden_patterns.md, figures/*.png
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from nill_pvd.data import SYMBOLS, download, add_features
from nill_pvd.ranges import detect_impulse, detect_bases
from nill_pvd.strategy import build_signals
from nill_pvd.backtest import backtest
from nill_pvd.metrics import equity_metrics, trade_metrics, permutation_pvalue
from nill_pvd.validation import expanding_walk_forward, friction_ladder, year_stability
from nill_pvd import benchmarks as BM


def run_symbol(name, sym, interval, period, cfg, data_dir, results_dir):
    df = download(sym, interval=interval, period=period, data_dir=data_dir)
    df = add_features(df)
    imp = detect_impulse(df)
    bases = detect_bases(df, imp)
    sig = build_signals(df, bases, min_rr=cfg["min_rr"])
    eq, tr = backtest(df, bases, sig, risk_pct=cfg["risk_pct_private"],
                      fee_bps=cfg["fee_bps"], max_hold=cfg["max_hold"])
    em = equity_metrics(eq); tm = trade_metrics(tr)
    # daily pnl for permutation
    if len(tr):
        d = tr.copy(); d["day"] = pd.to_datetime(d["exit_t"]).dt.date
        daily = d.groupby("day")["pnl"].sum()
        p_perm = permutation_pvalue(pd.Series(daily))
    else:
        p_perm = float("nan")
    wf = expanding_walk_forward(df, n_splits=cfg["walk_forward_splits"],
                                min_rr=cfg["min_rr"], risk_pct=cfg["risk_pct_private"],
                                fee_bps=cfg["fee_bps"])
    fr = friction_ladder(df, min_rr=cfg["min_rr"])
    ys = year_stability(tr)
    # benchmarks on same df
    bench_rows = []
    for bname, fn in BM.BENCHMARKS.items():
        beq, _ = fn(df, fee_bps=cfg["fee_bps"])
        bem = equity_metrics(beq)
        bench_rows.append({"symbol": name, "interval": interval, "benchmark": bname, **bem})
    return {"df": df, "bases": bases, "sig": sig, "eq": eq, "tr": tr,
            "em": em, "tm": tm, "p_perm": p_perm, "wf": wf, "fr": fr, "ys": ys,
            "bench": bench_rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/experiment.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    data_dir = Path("data"); results_dir = Path("results"); figdir = results_dir / "figures"
    data_dir.mkdir(exist_ok=True); results_dir.mkdir(exist_ok=True); figdir.mkdir(exist_ok=True)

    daily_rows, intra_rows, wf_all, fr_all, bench_all = [], [], [], [], []
    hidden = {}
    for name in cfg["universe"]:
        sym = SYMBOLS[name]
        print(f"\n===== {name} {sym} DAILY =====")
        try:
            r = run_symbol(name, sym, "1d", cfg["daily_period"], cfg, data_dir, results_dir)
        except Exception as e:
            print(f"FAIL daily {name}: {e}")
            continue
        row = {"symbol": name, "interval": "1d", **r["em"], **{k: v for k, v in r["tm"].items() if k != "by_setup"}, "perm_p": r["p_perm"]}
        daily_rows.append(row)
        wf_all += [{**{"symbol": name}, **x} for x in r["wf"]]
        fr_all += [{**{"symbol": name}, **x} for x in r["fr"]]
        bench_all += r["bench"]
        if len(r["ys"]):
            r["ys"].to_csv(results_dir / f"year_stability_{name}_1d.csv")
        r["eq"].to_csv(results_dir / f"equity_{name}_1d.csv")
        r["tr"].to_csv(results_dir / f"trades_{name}_1d.csv", index=False)
        # hidden-pattern probes on daily
        tr = r["tr"]; bases = r["bases"]
        if len(tr):
            by_setup = tr.groupby("setup").agg(n=("pnl", "count"), wr=("pnl", lambda x: (x > 0).mean()), avgR=("R", "mean"), pnl=("pnl", "sum"))
            hidden[name + "_daily_by_setup"] = by_setup.to_dict()
            # S3 vs S1/S2
            for s in tr["setup"].unique():
                sub = tr[tr["setup"] == s]
                print(f"  {s}: n={len(sub)} wr={(sub['pnl'] > 0).mean():.2f} avgR={sub['R'].mean():.2f} pnl={sub['pnl'].sum():.0f}")
        # equity plot
        plt.figure(figsize=(8, 3.5))
        r["eq"].plot(title=f"{name} PVD equity (1d, RR>=3, 1% risk)")
        plt.tight_layout(); plt.savefig(figdir / f"equity_{name}_1d.png"); plt.close()

        print(f"===== {name} {sym} INTRADAY {cfg['intraday_interval']} =====")
        try:
            r2 = run_symbol(name, sym, cfg["intraday_interval"], cfg["intraday_period"], cfg, data_dir, results_dir)
        except Exception as e:
            print(f"FAIL intraday {name}: {e}")
            continue
        row2 = {"symbol": name, "interval": cfg["intraday_interval"], **r2["em"], **{k: v for k, v in r2["tm"].items() if k != "by_setup"}, "perm_p": r2["p_perm"]}
        intra_rows.append(row2)
        r2["eq"].to_csv(results_dir / f"equity_{name}_intraday.csv")
        r2["tr"].to_csv(results_dir / f"trades_{name}_intraday.csv", index=False)
        plt.figure(figsize=(8, 3.5))
        r2["eq"].plot(title=f"{name} PVD equity ({cfg['intraday_interval']})")
        plt.tight_layout(); plt.savefig(figdir / f"equity_{name}_intraday.png"); plt.close()
        if len(r2["tr"]):
            by_setup2 = r2["tr"].groupby("setup").agg(n=("pnl", "count"), wr=("pnl", lambda x: (x > 0).mean()), avgR=("R", "mean"), pnl=("pnl", "sum"))
            hidden[name + "_intraday_by_setup"] = by_setup2.to_dict()

    pd.DataFrame(daily_rows).to_csv(results_dir / "daily_summary.csv", index=False)
    pd.DataFrame(intra_rows).to_csv(results_dir / "intraday_summary.csv", index=False)
    pd.DataFrame(wf_all).to_csv(results_dir / "walk_forward.csv", index=False)
    pd.DataFrame(fr_all).to_csv(results_dir / "friction.csv", index=False)
    pd.DataFrame(bench_all).to_csv(results_dir / "benchmarks.csv", index=False)
    with open(results_dir / "hidden_patterns.json", "w") as f:
        json.dump(hidden, f, indent=2, default=str)
    manifest = {"config": cfg, "symbols": SYMBOLS, "note": "All data public Yahoo Finance; see data/*.manifest.json for provenance."}
    with open(results_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    # hidden_patterns.md synthesis
    with open(results_dir / "hidden_patterns.md", "w") as f:
        f.write("# Hidden-pattern probes (auto-generated, verify before citing)\n\n")
        for k, v in hidden.items():
            f.write(f"## {k}\n```json\n{json.dumps(v, indent=2, default=str)}\n```\n\n")
        f.write("\nInterpretation is in README/PAPER; numbers above are raw outputs.\n")
    print("\n[done] results/ written. See daily_summary.csv, intraday_summary.csv, benchmarks.csv, walk_forward.csv")

if __name__ == "__main__":
    main()
