"""Live public data loader with on-disk cache and full provenance.

Primary: Yahoo Finance via yfinance (no key, public).
Symbols used in study (all public, verifiable):
  DAX  -> ^GDAXI (Xetra DAX performance index, proxy for FDAX)
  WTI  -> CL=F  (WTI crude front-month, proxy for oil trading)
  Brent-> BZ=F
  ES   -> ES=F  (S&P500 front-month)
  NQ   -> NQ=F  (Nasdaq-100 front-month)
  Gold -> GC=F

Design rules (from online best-practice synthesis):
- never forward-fill into the future; cache key includes symbol+interval+range
- record download timestamp, source, rows, NaN rate into manifest.json
- intraday 15m limited by Yahoo to ~60d; daily covers 2000-present for regime tests
- all experiments log exact Yahoo query so anyone can reproduce with `download_data.py`
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

SYMBOLS = {
    "DAX": "^GDAXI",
    "WTI": "CL=F",
    "BRENT": "BZ=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "GOLD": "GC=F",
}

def _cache_key(symbol: str, interval: str, period: str) -> str:
    h = hashlib.md5(f"{symbol}|{interval}|{period}".encode()).hexdigest()[:10]
    safe = symbol.replace("^", "").replace("=", "")
    return f"{safe}_{interval}_{period}_{h}.parquet"

def download(symbol: str, interval: str = "1d", period: str = "max",
             data_dir: str | Path = "data", force: bool = False) -> pd.DataFrame:
    """Download OHLCV from Yahoo, cache to parquet, return tz-naive UTC-indexed df."""
    import yfinance as yf
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    ck = _cache_key(symbol, interval, period)
    fp = data_dir / ck
    if fp.exists() and not force:
        df = pd.read_parquet(fp)
        return df
    t = yf.Ticker(symbol)
    df = t.history(interval=interval, period=period, auto_adjust=False, back_adjust=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"Yahoo returned 0 rows for {symbol} {interval} {period}")
    df = df.copy()
    # normalise columns
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    # index to UTC naive
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    df = df.sort_index()
    df.to_parquet(fp)
    manifest = {
        "symbol": symbol, "interval": interval, "period": period,
        "rows": int(len(df)), "start": str(df.index[0]), "end": str(df.index[-1]),
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "cache_file": ck,
        "nan_close_pct": float(df["close"].isna().mean()),
    }
    with open(data_dir / (ck + ".manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return df

def load_all(data_dir: str | Path = "data", interval: str = "1d",
             period: str = "max") -> dict[str, pd.DataFrame]:
    out = {}
    for name, sym in SYMBOLS.items():
        try:
            out[name] = download(sym, interval=interval, period=period, data_dir=data_dir)
        except Exception as e:
            print(f"[data] WARN {name} {sym}: {e}")
    return out

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add ATR, returns, range proxies. No look-ahead: all trailing only."""
    df = df.copy()
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    df["tr"] = tr
    df["atr14"] = tr.rolling(14, min_periods=1).mean()
    df["atr50"] = tr.rolling(50, min_periods=1).mean()
    df["ret1"] = c.pct_change()
    df["logret1"] = (c / prev_c).apply(lambda x: __import__("math").log(x) if x > 0 else float("nan"))
    df["body"] = (c - df["open"]).abs()
    df["range"] = h - l
    df["range_atr"] = df["range"] / df["atr14"].replace(0, float("nan"))
    return df
