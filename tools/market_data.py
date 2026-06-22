"""
Market data fetching layer – thin wrappers around yfinance with
in-memory + disk caching and graceful error handling.
"""

import logging
import os
import re
import time
from typing import Dict, Any, Optional, List

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Simple runtime cache: ticker → (timestamp, data)
_OHLCV_CACHE: Dict[str, tuple] = {}
_INFO_CACHE:  Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour

# Persistent cache on disk to reduce Yahoo API calls across runs.
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_CACHE_ROOT = os.path.join(_BASE_DIR, "data", "market_cache")
_OHLCV_DIR = os.path.join(_CACHE_ROOT, "ohlcv")
_INFO_DIR = os.path.join(_CACHE_ROOT, "info")

OHLCV_DISK_TTL_SECONDS = 6 * 3600
INFO_DISK_TTL_SECONDS = 24 * 3600

_CACHE_STATS: Dict[str, int] = {
    # OHLCV counters
    "ohlcv_memory_hits": 0,
    "ohlcv_disk_hits": 0,
    "ohlcv_yahoo_requests": 0,
    "ohlcv_yahoo_success": 0,
    "ohlcv_yahoo_empty": 0,
    "ohlcv_errors": 0,
    "ohlcv_disk_writes": 0,
    # INFO counters
    "info_memory_hits": 0,
    "info_disk_hits": 0,
    "info_yahoo_requests": 0,
    "info_yahoo_success": 0,
    "info_errors": 0,
    "info_disk_writes": 0,
}


def _bump_stat(key: str, n: int = 1) -> None:
    _CACHE_STATS[key] = _CACHE_STATS.get(key, 0) + n


def get_cache_summary() -> Dict[str, Any]:
    """Return a lightweight snapshot of cache usage for reporting/debugging."""
    ohlcv_hits = _CACHE_STATS.get("ohlcv_memory_hits", 0) + _CACHE_STATS.get("ohlcv_disk_hits", 0)
    ohlcv_total = ohlcv_hits + _CACHE_STATS.get("ohlcv_yahoo_requests", 0)
    info_hits = _CACHE_STATS.get("info_memory_hits", 0) + _CACHE_STATS.get("info_disk_hits", 0)
    info_total = info_hits + _CACHE_STATS.get("info_yahoo_requests", 0)

    return {
        "ttl": {
            "memory_seconds": CACHE_TTL_SECONDS,
            "ohlcv_disk_seconds": OHLCV_DISK_TTL_SECONDS,
            "info_disk_seconds": INFO_DISK_TTL_SECONDS,
        },
        "ohlcv": {
            "memory_hits": _CACHE_STATS.get("ohlcv_memory_hits", 0),
            "disk_hits": _CACHE_STATS.get("ohlcv_disk_hits", 0),
            "hits": ohlcv_hits,
            "yahoo_requests": _CACHE_STATS.get("ohlcv_yahoo_requests", 0),
            "yahoo_success": _CACHE_STATS.get("ohlcv_yahoo_success", 0),
            "yahoo_empty": _CACHE_STATS.get("ohlcv_yahoo_empty", 0),
            "errors": _CACHE_STATS.get("ohlcv_errors", 0),
            "disk_writes": _CACHE_STATS.get("ohlcv_disk_writes", 0),
            "hit_rate_pct": round((ohlcv_hits / ohlcv_total * 100), 1) if ohlcv_total else 0.0,
        },
        "info": {
            "memory_hits": _CACHE_STATS.get("info_memory_hits", 0),
            "disk_hits": _CACHE_STATS.get("info_disk_hits", 0),
            "hits": info_hits,
            "yahoo_requests": _CACHE_STATS.get("info_yahoo_requests", 0),
            "yahoo_success": _CACHE_STATS.get("info_yahoo_success", 0),
            "errors": _CACHE_STATS.get("info_errors", 0),
            "disk_writes": _CACHE_STATS.get("info_disk_writes", 0),
            "hit_rate_pct": round((info_hits / info_total * 100), 1) if info_total else 0.0,
        },
        "cache_root": _CACHE_ROOT,
    }


def _ensure_cache_dirs() -> None:
    os.makedirs(_OHLCV_DIR, exist_ok=True)
    os.makedirs(_INFO_DIR, exist_ok=True)


def _safe_cache_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _ohlcv_cache_path(cache_key: str) -> str:
    _ensure_cache_dirs()
    return os.path.join(_OHLCV_DIR, f"{_safe_cache_key(cache_key)}.pkl")


def _info_cache_path(ticker: str) -> str:
    _ensure_cache_dirs()
    return os.path.join(_INFO_DIR, f"{_safe_cache_key(ticker.upper())}.json")


def _load_ohlcv_disk(cache_key: str, ttl_seconds: int = OHLCV_DISK_TTL_SECONDS) -> Optional[pd.DataFrame]:
    path = _ohlcv_cache_path(cache_key)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl_seconds:
        return None
    try:
        df = pd.read_pickle(path)
        if df is None or df.empty:
            return None
        return df
    except Exception as exc:
        logger.debug("Could not read OHLCV disk cache %s: %s", path, exc)
        return None


def _save_ohlcv_disk(cache_key: str, df: pd.DataFrame) -> None:
    path = _ohlcv_cache_path(cache_key)
    try:
        df.to_pickle(path)
        _bump_stat("ohlcv_disk_writes")
    except Exception as exc:
        logger.debug("Could not write OHLCV disk cache %s: %s", path, exc)


def _load_info_disk(ticker: str, ttl_seconds: int = INFO_DISK_TTL_SECONDS) -> Optional[Dict[str, Any]]:
    import json

    path = _info_cache_path(ticker)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl_seconds:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        info = data.get("info") if isinstance(data, dict) else None
        return info if isinstance(info, dict) else None
    except Exception as exc:
        logger.debug("Could not read info disk cache %s: %s", path, exc)
        return None


def _save_info_disk(ticker: str, info: Dict[str, Any]) -> None:
    import json

    path = _info_cache_path(ticker)
    payload = {"saved_at": int(time.time()), "info": info}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        _bump_stat("info_disk_writes")
    except Exception as exc:
        logger.debug("Could not write info disk cache %s: %s", path, exc)


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
        _bump_stat("ohlcv_memory_hits")
        return cached

    disk_cached = _load_ohlcv_disk(cache_key)
    if disk_cached is not None:
        _bump_stat("ohlcv_disk_hits")
        _OHLCV_CACHE[cache_key] = (time.time(), disk_cached)
        return disk_cached

    try:
        _bump_stat("ohlcv_yahoo_requests")
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=True, timeout=15)
        if df is None or df.empty:
            _bump_stat("ohlcv_yahoo_empty")
            logger.warning("No OHLCV data: %s", ticker)
            _OHLCV_CACHE[cache_key] = (time.time(), None)
            return None
        df.index = pd.to_datetime(df.index)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        _OHLCV_CACHE[cache_key] = (time.time(), df)
        _bump_stat("ohlcv_yahoo_success")
        _save_ohlcv_disk(cache_key, df)
        return df
    except Exception as exc:
        _bump_stat("ohlcv_errors")
        logger.error("fetch_ohlcv %s: %s", ticker, exc)
        return None


def fetch_ohlcv_batch(tickers: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
    """Download multiple tickers in one yfinance call and split."""
    if not tickers:
        return {}
    result: Dict[str, pd.DataFrame] = {}
    to_fetch: List[str] = []

    for ticker in tickers:
        cache_key = f"{ticker}_{period}_1d"
        ts, cached = _OHLCV_CACHE.get(cache_key, (0, None))
        if cached is not None and time.time() - ts < CACHE_TTL_SECONDS:
            _bump_stat("ohlcv_memory_hits")
            result[ticker] = cached
            continue

        disk_cached = _load_ohlcv_disk(cache_key)
        if disk_cached is not None:
            _bump_stat("ohlcv_disk_hits")
            _OHLCV_CACHE[cache_key] = (time.time(), disk_cached)
            result[ticker] = disk_cached
            continue

        to_fetch.append(ticker)

    if not to_fetch:
        return result

    try:
        _bump_stat("ohlcv_yahoo_requests", len(to_fetch))
        yahoo_success_in_batch = 0
        raw = yf.download(
            to_fetch,
            period=period,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=30,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            for t in to_fetch:
                try:
                    df = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    if not df.empty:
                        cache_key = f"{t}_{period}_1d"
                        _OHLCV_CACHE[cache_key] = (time.time(), df)
                        _save_ohlcv_disk(cache_key, df)
                        result[t] = df
                        _bump_stat("ohlcv_yahoo_success")
                        yahoo_success_in_batch += 1
                except Exception:
                    pass
        else:
            # Single ticker returned as flat DataFrame
            if len(to_fetch) == 1:
                df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                if not df.empty:
                    cache_key = f"{to_fetch[0]}_{period}_1d"
                    _OHLCV_CACHE[cache_key] = (time.time(), df)
                    _save_ohlcv_disk(cache_key, df)
                    result[to_fetch[0]] = df
                    _bump_stat("ohlcv_yahoo_success")
                    yahoo_success_in_batch += 1

        if yahoo_success_in_batch < len(to_fetch):
            _bump_stat("ohlcv_yahoo_empty", len(to_fetch) - yahoo_success_in_batch)

        return result
    except Exception as exc:
        _bump_stat("ohlcv_errors")
        logger.error("fetch_ohlcv_batch: %s", exc)
        # Fall back to individual fetches
        for t in to_fetch:
            df = fetch_ohlcv(t, period)
            if df is not None:
                result[t] = df
        return result


# ─────────────────────────────────────────────────────────────────────────────
# FUNDAMENTAL INFO
# ─────────────────────────────────────────────────────────────────────────────

def fetch_info(ticker: str) -> Dict[str, Any]:
    """
    Return the yfinance .info dict. Returns {} on failure.
    """
    ts, cached = _INFO_CACHE.get(ticker, (0, None))
    if cached is not None and time.time() - ts < CACHE_TTL_SECONDS:
        _bump_stat("info_memory_hits")
        return cached

    disk_cached = _load_info_disk(ticker)
    if disk_cached is not None:
        _bump_stat("info_disk_hits")
        _INFO_CACHE[ticker] = (time.time(), disk_cached)
        return disk_cached

    try:
        _bump_stat("info_yahoo_requests")
        t = yf.Ticker(ticker)
        info = t.info or {}
        _INFO_CACHE[ticker] = (time.time(), info)
        _bump_stat("info_yahoo_success")
        _save_info_disk(ticker, info)
        return info
    except Exception as exc:
        _bump_stat("info_errors")
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
