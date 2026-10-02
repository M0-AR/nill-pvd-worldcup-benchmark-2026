"""Download all public Yahoo data for the study (verifiable provenance)."""
import yaml
from pathlib import Path
from nill_pvd.data import SYMBOLS, download

cfg = yaml.safe_load(open("configs/experiment.yaml"))
data_dir = Path("data")
for name, sym in SYMBOLS.items():
    if name in cfg.get("universe", list(SYMBOLS.keys())):
        print(f"[dl] {name} {sym} daily...")
        try:
            df = download(sym, interval="1d", period=cfg.get("daily_period", "max"), data_dir=data_dir)
            print(f"  -> {len(df)} rows {df.index[0]}..{df.index[-1]}")
        except Exception as e:
            print(f"  FAIL {e}")
        print(f"[dl] {name} {sym} intraday {cfg.get('intraday_interval')}...")
        try:
            df2 = download(sym, interval=cfg.get("intraday_interval", "15m"),
                           period=cfg.get("intraday_period", "60d"), data_dir=data_dir)
            print(f"  -> {len(df2)} rows {df2.index[0]}..{df2.index[-1]}")
        except Exception as e:
            print(f"  FAIL intraday {e}")
print("[dl] done.")
