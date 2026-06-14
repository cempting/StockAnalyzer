"""
Market data fetching layer – thin wrappers around yfinance with
simple in-memory caching and graceful error handling.
"""

import logging
import time
from functools import lru_cache
from typing import Dict, Any, Optional, List

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Simple runtime cache: ticker → (timestamp, data)
_OHLCV_CACHE: Dict[str, tuple] = {}
_INFO_CACHE:  Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Return a DataFrame with columns Open/High/Low/Close/Volume.
    Returns None on failure.
    """
    cache_key = f"{ticker}_{period}_{interval}"
    ts, cached = _OHLCV_CACHE.get(cache_key, (0, None))
    if cached is not None and time.time() - ts < CACHE_TTL_SECONDS:
        return cached

    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=True, timeout=15)
        if df is None or df.empty:
            logger.warning("No OHLCV data: %s", ticker)
            _OHLCV_CACHE[cache_key] = (time.time(), None)
            return None
        df.index = pd.to_datetime(df.index)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        _OHLCV_CACHE[cache_key] = (time.time(), df)
        return df
    except Exception as exc:
        logger.error("fetch_ohlcv %s: %s", ticker, exc)
        return None


def fetch_ohlcv_batch(tickers: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
    """Download multiple tickers in one yfinance call and split."""
    if not tickers:
        return {}
    try:
        raw = yf.download(
            tickers,
            period=period,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=30,
        )
        result: Dict[str, pd.DataFrame] = {}

        if isinstance(raw.columns, pd.MultiIndex):
            for t in tickers:
                try:
                    df = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    if not df.empty:
                        result[t] = df
                except Exception:
                    pass
        else:
            # Single ticker returned as flat DataFrame
            if len(tickers) == 1:
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                if not df.empty:
                    result[tickers[0]] = df

        return result
    except Exception as exc:
        logger.error("fetch_ohlcv_batch: %s", exc)
        # Fall back to individual fetches
        return {t: fetch_ohlcv(t, period) for t in tickers if fetch_ohlcv(t, period) is not None}


# ─────────────────────────────────────────────────────────────────────────────
# FUNDAMENTAL INFO
# ─────────────────────────────────────────────────────────────────────────────

def fetch_info(ticker: str) -> Dict[str, Any]:
    """
    Return the yfinance .info dict. Returns {} on failure.
    """
    ts, cached = _INFO_CACHE.get(ticker, (0, None))
    if cached is not None and time.time() - ts < CACHE_TTL_SECONDS:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        _INFO_CACHE[ticker] = (time.time(), info)
        return info
    except Exception as exc:
        logger.error("fetch_info %s: %s", ticker, exc)
        return {}


def fetch_info_batch(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch info for many tickers sequentially (yfinance has no batch info endpoint)."""
    result = {}
    for t in tickers:
        result[t] = fetch_info(t)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sector_performance(sector_map: Dict[str, str], periods: List[str] = None) -> pd.DataFrame:
    """
    Given {sector_name: ticker}, return a DataFrame of returns per period.
    periods: list of yfinance period strings, e.g. ['1wk','1mo','3mo','6mo','1y']
    """
    if periods is None:
        periods = ["1wk", "1mo", "3mo", "6mo", "ytd", "1y"]

    rows = []
    for name, etf in sector_map.items():
        row = {"sector": name, "ticker": etf}
        for p in periods:
            df = fetch_ohlcv(etf, period=p)
            if df is not None and len(df) >= 2:
                ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
                row[p] = round(ret, 2)
            else:
                row[p] = None
        rows.append(row)

    return pd.DataFrame(rows).set_index("sector")


# ─────────────────────────────────────────────────────────────────────────────
# MAJOR INDICES
# ─────────────────────────────────────────────────────────────────────────────

def fetch_index_data(index_map: Dict[str, str], period: str = "1y") -> Dict[str, Dict]:
    """
    Return summary stats for each index.
    """
    result = {}
    for name, ticker in index_map.items():
        df = fetch_ohlcv(ticker, period=period)
        if df is None or df.empty:
            result[name] = {"ticker": ticker, "error": "no data"}
            continue

        close = df["Close"]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        ma50  = close.rolling(50).mean().iloc[-1]  if len(close) >= 50  else None

        result[name] = {
            "ticker":       ticker,
            "last":         round(close.iloc[-1], 2),
            "1d_chg":       round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2) if len(close) >= 2 else None,
            "1w_chg":       round((close.iloc[-1] / close.iloc[-5 if len(close) >= 5 else 0] - 1) * 100, 2),
            "1m_chg":       round((close.iloc[-1] / close.iloc[-21 if len(close) >= 21 else 0] - 1) * 100, 2),
            "ytd_chg":      _ytd_return(close),
            "1y_chg":       round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2),
            "52w_high":     round(close.rolling(252).max().iloc[-1], 2) if len(close) >= 252 else round(close.max(), 2),
            "52w_low":      round(close.rolling(252).min().iloc[-1], 2) if len(close) >= 252 else round(close.min(), 2),
            "above_ma50":   bool(ma50 and close.iloc[-1] > ma50),
            "above_ma200":  bool(ma200 and close.iloc[-1] > ma200),
            "ma50":         round(ma50, 2) if ma50 else None,
            "ma200":        round(ma200, 2) if ma200 else None,
        }
    return result


def _ytd_return(close: pd.Series) -> Optional[float]:
    import datetime
    today = datetime.date.today()
    year_start = datetime.date(today.year, 1, 1)
    close.index = pd.to_datetime(close.index)
    ytd_data = close[close.index.date >= year_start]
    if len(ytd_data) < 2:
        return None
    return round((ytd_data.iloc[-1] / ytd_data.iloc[0] - 1) * 100, 2)
