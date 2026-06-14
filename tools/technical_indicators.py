"""
Technical indicator calculations and Weinstein/Prehn stage analysis.
All functions accept a pandas DataFrame with columns: Open, High, Low, Close, Volume.
"""

import logging
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a DataFrame with technical indicators.
    Requires at least ~50 rows for meaningful results; 200+ for stage analysis.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]

    # ── Moving Averages ──────────────────────────────────────────────────────
    for n in [10, 21, 50, 150, 200]:
        df[f"MA{n}"] = close.rolling(n).mean()

    # Exponential MAs
    df["EMA9"]  = close.ewm(span=9, adjust=False).mean()
    df["EMA21"] = close.ewm(span=21, adjust=False).mean()

    # ── RSI (14) ─────────────────────────────────────────────────────────────
    df["RSI"] = _rsi(close, 14)

    # ── MACD (12, 26, 9) ─────────────────────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

    # ── Bollinger Bands (20, 2σ) ─────────────────────────────────────────────
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["BB_Upper"]  = bb_mid + 2 * bb_std
    df["BB_Lower"]  = bb_mid - 2 * bb_std
    df["BB_Middle"] = bb_mid
    df["BB_Width"]  = (df["BB_Upper"] - df["BB_Lower"]) / bb_mid * 100  # %

    # ── ATR (14) ──────────────────────────────────────────────────────────────
    df["ATR"] = _atr(high, low, close, 14)

    # ── Volume ───────────────────────────────────────────────────────────────
    df["Vol_MA20"]   = vol.rolling(20).mean()
    df["Vol_Ratio"]  = vol / df["Vol_MA20"]  # >1 = above-average volume

    # ── Stochastic (14, 3) ───────────────────────────────────────────────────
    lowest14  = low.rolling(14).min()
    highest14 = high.rolling(14).max()
    range14   = (highest14 - lowest14).replace(0, np.nan)
    df["Stoch_K"] = ((close - lowest14) / range14) * 100
    df["Stoch_D"] = df["Stoch_K"].rolling(3).mean()

    return df


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ─────────────────────────────────────────────────────────────────────────────
# WEINSTEIN / PREHN STAGE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def get_stage(df: pd.DataFrame) -> int:
    """
    Return the Weinstein/Prehn market stage (1–4) based on MA200 trend and price.

    Stage 1 – Basing:   price near flat MA200, no clear trend
    Stage 2 – Advancing: price above rising MA200  ← Felix buys here
    Stage 3 – Topping:  price below but MA200 still rising (distribution)
    Stage 4 – Declining: price below falling MA200
    Returns 0 if insufficient data.
    """
    if df is None or "MA200" not in df.columns:
        return 0

    ma200 = df["MA200"].dropna()
    if len(ma200) < 20:
        return 0

    last_close = df["Close"].iloc[-1]
    last_ma200 = ma200.iloc[-1]

    # MA200 direction: compare last 20 days
    ma200_trend = ma200.iloc[-1] - ma200.iloc[-20]

    above = last_close > last_ma200
    rising = ma200_trend > 0

    if above and rising:
        return 2
    elif not above and not rising:
        return 4
    elif above and not rising:
        return 3   # price held up but MA200 starting to roll over
    else:
        return 1   # price below but MA200 flattening / potential base


# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def get_technical_snapshot(df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Return a flat dict of the most recent technical readings for a stock.
    benchmark_df: optional S&P 500 / index OHLCV for relative-strength calc.
    """
    if df is None or df.empty:
        return {"error": "no data"}

    if "MA200" not in df.columns:
        df = add_indicators(df)

    last = df.iloc[-1]
    close = df["Close"]
    n = len(close)

    # 52-week stats
    w52 = close.tail(252)
    high52 = w52.max()
    low52  = w52.min()

    # Returns
    def ret(days):
        idx = max(0, n - days)
        return round((close.iloc[-1] / close.iloc[idx] - 1) * 100, 2)

    # Relative strength vs benchmark (1-year)
    rs_vs_bench = None
    if benchmark_df is not None and not benchmark_df.empty:
        try:
            bench_ret = (benchmark_df["Close"].iloc[-1] / benchmark_df["Close"].iloc[0] - 1) * 100
            stock_ret = ret(252)
            rs_vs_bench = round(stock_ret - bench_ret, 2)
        except Exception:
            pass

    snap = {
        "last_close":          round(float(last["Close"]), 4),
        "52w_high":            round(float(high52), 4),
        "52w_low":             round(float(low52), 4),
        "pct_from_52w_high":   round((last["Close"] / high52 - 1) * 100, 2),
        "pct_from_52w_low":    round((last["Close"] / low52  - 1) * 100, 2),
        "ret_1w":  ret(5),
        "ret_1m":  ret(21),
        "ret_3m":  ret(63),
        "ret_6m":  ret(126),
        "ret_1y":  ret(252),

        # Moving averages
        "ma50":   round(float(last["MA50"]),  4) if not pd.isna(last.get("MA50", float("nan")))  else None,
        "ma150":  round(float(last["MA150"]), 4) if not pd.isna(last.get("MA150", float("nan"))) else None,
        "ma200":  round(float(last["MA200"]), 4) if not pd.isna(last.get("MA200", float("nan"))) else None,
        "above_ma50":   bool(not pd.isna(last.get("MA50"))  and last["Close"] > last["MA50"]),
        "above_ma150":  bool(not pd.isna(last.get("MA150")) and last["Close"] > last["MA150"]),
        "above_ma200":  bool(not pd.isna(last.get("MA200")) and last["Close"] > last["MA200"]),

        # MA trend (MA200 slope)
        "ma200_rising": _ma_trending_up(df["MA200"]) if "MA200" in df.columns else None,

        # Oscillators
        "rsi":        round(float(last["RSI"]), 1)         if not pd.isna(last.get("RSI", float("nan")))  else None,
        "macd":       round(float(last["MACD"]), 4)        if not pd.isna(last.get("MACD", float("nan"))) else None,
        "macd_hist":  round(float(last["MACD_Hist"]), 4)   if not pd.isna(last.get("MACD_Hist", float("nan"))) else None,
        "macd_bullish": (
            not pd.isna(last.get("MACD", float("nan"))) and
            not pd.isna(last.get("MACD_Signal", float("nan"))) and
            last["MACD"] > last["MACD_Signal"]
        ),
        "stoch_k":    round(float(last["Stoch_K"]), 1)    if not pd.isna(last.get("Stoch_K", float("nan"))) else None,

        # Volume
        "vol_ratio":  round(float(last["Vol_Ratio"]), 2)  if not pd.isna(last.get("Vol_Ratio", float("nan"))) else None,

        # Stage
        "stage": get_stage(df),

        # Relative strength
        "rs_vs_benchmark": rs_vs_bench,

        # ATR for position sizing
        "atr":    round(float(last["ATR"]), 4)             if not pd.isna(last.get("ATR", float("nan"))) else None,
    }

    return snap


def _ma_trending_up(ma_series: pd.Series, lookback: int = 20) -> Optional[bool]:
    clean = ma_series.dropna()
    if len(clean) < lookback:
        return None
    return bool(clean.iloc[-1] > clean.iloc[-lookback])
