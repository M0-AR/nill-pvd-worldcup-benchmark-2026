"""Generate demo visuals: overview PNG, animated GIF/MP4, trade-example chart. Verified by execution."""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path

RESULTS = Path("results")
ASSETS = Path("assets")
ASSETS.mkdir(exist_ok=True)

# 1. Equity overview 2x2
fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=False)
fig.suptitle("PVD transcription — Daily equity ($100k start, 1% risk, R>=3, 5bps)", fontsize=13, fontweight="bold")
for ax, sym in zip(axes.flat, ["DAX", "WTI", "ES", "NQ"]):
    eq = pd.read_csv(RESULTS / f"equity_{sym}_1d.csv", index_col=0, parse_dates=True)
    col = eq.columns[0]
    ax.plot(eq.index, eq[col], linewidth=1.2)
    ax.set_title(sym, fontweight="bold")
    ax.grid(alpha=0.3)
    ax.tick_params(labelrotation=20, labelsize=8)
fig.tight_layout()
fig.savefig(ASSETS / "equity_overview.png", dpi=150)
print("wrote assets/equity_overview.png")

# 2. Trade example: DAX daily price window around first trade
import pandas as pd
trades = pd.read_csv(RESULTS / "trades_DAX_1d.csv", parse_dates=["entry_t", "exit_t"])
print(f"DAX trades: {len(trades)}")
# price data from cache? reconstruct from equity file? use data parquet
from pathlib import Path as P
import glob
parquets = glob.glob("data/GDAXI_1d*.parquet")
print("parquets:", parquets)
if parquets and len(trades):
    px = pd.read_parquet(parquets[0])
    t0 = trades.iloc[0]
    et = pd.to_datetime(t0["entry_t"])
    # window +-60 bars
    try:
        loc = px.index.get_indexer([et], method="ffill")[0]
        w0, w1 = max(0, loc-60), min(len(px), loc+60)
        win = px.iloc[w0:w1]
        fig2, ax2 = plt.subplots(figsize=(10, 4.5))
        ax2.plot(win.index, win["close"], label="DAX close", linewidth=1.4)
        ax2.scatter([et], [t0["entry"]], color="green", s=80, marker="^", label=f"Entry {t0['setup']} dir={t0['dir']}", zorder=5)
        ax2.scatter([pd.to_datetime(t0["exit_t"])], [t0["exit"]], color="red", s=80, marker="v", label=f"Exit {t0['why']} R={t0['R']:.2f}", zorder=5)
        ax2.axhline(t0["stop"], color="red", linestyle="--", alpha=0.7, label="Stop")
        # tp1/tp3 if present
        if "tp1" in t0 and pd.notna(t0["tp1"]):
            ax2.axhline(t0["tp1"], color="green", linestyle=":", alpha=0.7, label="Target")
        ax2.legend(fontsize=8)
        ax2.set_title(f"Trade example — DAX {t0['entry_t']} → {t0['exit_t']} ({t0['setup']})", fontweight="bold")
        ax2.grid(alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(ASSETS / "trade_example.png", dpi=150)
        print("wrote assets/trade_example.png")
    except Exception as e:
        print("trade example failed:", e)

# 3. Animated demo GIF: DAX equity build-up
try:
    eq = pd.read_csv(RESULTS / "equity_DAX_1d.csv", index_col=0, parse_dates=True)
    vals = eq.iloc[:, 0].values
    # downsample to 120 frames
    import numpy as np
    idx = np.linspace(0, len(vals)-1, 120).astype(int)
    fig3, ax3 = plt.subplots(figsize=(8, 4.2))
    line, = ax3.plot([], [], linewidth=1.6)
    ax3.set_xlim(0, len(vals))
    ax3.set_ylim(float(np.min(vals))*0.99, float(np.max(vals))*1.01)
    ax3.set_title("Demo — DAX equity build-up (daily, PVD S1/S2)")
    ax3.set_xlabel("bar")
    ax3.set_ylabel("equity $")
    ax3.grid(alpha=0.3)
    txt = ax3.text(0.02, 0.95, "", transform=ax3.transAxes)
    def upd(i):
        k = idx[i]
        line.set_data(range(k), vals[:k])
        txt.set_text(f"bar {k}/{len(vals)}  equity ${vals[k]:,.0f}")
        return line, txt
    ani = animation.FuncAnimation(fig3, upd, frames=len(idx), interval=80, blit=False)
    ani.save(ASSETS / "demo.gif", writer="pillow", fps=12)
    print("wrote assets/demo.gif")
    # MP4 if ffmpeg available
    try:
        ani.save(ASSETS / "demo.mp4", writer="ffmpeg", fps=12)
        print("wrote assets/demo.mp4")
    except Exception as e:
        print("mp4 skipped (ffmpeg missing?):", e)
except Exception as e:
    print("animation failed:", e)

print("done assets:", list(ASSETS.iterdir()))
