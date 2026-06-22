"""
Universe constituent loaders with persistent local caching.

This module fetches dynamic universe constituents (where available),
caches results to data/universe_cache.json, and falls back gracefully.
"""

from __future__ import annotations

import json
import logging
import os
import re
from io import StringIO
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "universe_cache.json")
CACHE_VERSION = 1

# Best-effort public sources for dynamic constituents.
UNIVERSE_SOURCES = {
    "russell2000": [
        # Primary source: iShares IWM holdings via product-data API.
        # Uses fund product id 239710 (iShares Russell 2000 ETF).
        "ishares-product-api://239710",
        "https://en.wikipedia.org/wiki/Russell_2000_Index",
    ],
    "midcap": [
        "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    ],
    # iShares Core S&P 500 ETF (IVV) product id 239726 → ~508 holdings weight-ordered
    "largecap": [
        "ishares-product-api://239726",
    ],
    # Same source as largecap; max_constituents cap in config trims to top-50 mega caps
    "xlargecap": [
        "ishares-product-api://239726",
    ],
}

# Common column labels seen on public index constituent tables.
TICKER_COLUMNS = [
    "Symbol",
    "Ticker",
    "Ticker symbol",
    "Ticker Symbol",
]


def get_dynamic_universe(
    universe_name: str,
    fallback: Optional[List[str]] = None,
    ttl_hours: int = 24 * 7,
    max_constituents: Optional[int] = None,
    yahoo_prefilter: bool = False,
) -> List[str]:
    """
    Return dynamic constituents for universe_name using persistent cache.

    Falls back to provided list if fetch fails or source is unavailable.
    """
    fallback = fallback or []
    name = (universe_name or "").strip().lower()

    if name not in UNIVERSE_SOURCES:
        return _apply_constituent_limit(fallback, max_constituents, name)

    cached = _read_cache()
    if _is_cache_fresh(cached.get(name), ttl_hours=ttl_hours):
        entry = cached[name]
        tickers = _sanitize_tickers(entry.get("tickers", []))
        if tickers:
            if yahoo_prefilter and entry.get("validation") != "yahoo":
                tickers = _prefilter_yahoo_symbols(tickers)
                cached[name] = {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "tickers": tickers,
                    "validation": "yahoo",
                }
                _write_cache(cached)
            return _apply_constituent_limit(tickers, max_constituents, name)

    tickers = _fetch_from_sources(UNIVERSE_SOURCES[name])
    if tickers and yahoo_prefilter:
        tickers = _prefilter_yahoo_symbols(tickers)

    if tickers:
        cached[name] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tickers": tickers,
            "validation": "yahoo" if yahoo_prefilter else None,
        }
        _write_cache(cached)
        return _apply_constituent_limit(tickers, max_constituents, name)

    # stale cache is still better than no data
    stale = _sanitize_tickers(cached.get(name, {}).get("tickers", []))
    if stale:
        logger.warning("Using stale cached constituents for %s", name)
        if yahoo_prefilter:
            stale = _prefilter_yahoo_symbols(stale)
        return _apply_constituent_limit(stale, max_constituents, name)

    logger.warning("Falling back to static universe for %s", name)
    return _apply_constituent_limit(fallback, max_constituents, name)


def _fetch_from_sources(urls: List[str]) -> List[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for url in urls:
        if url.startswith("ishares-product-api://"):
            try:
                product_id = url.split("://", 1)[1].strip()
                tickers = _fetch_from_ishares_product_api(product_id)
                if len(tickers) >= 20:
                    logger.info("Fetched %d constituents from iShares product API (%s)", len(tickers), product_id)
                    return tickers
            except Exception as exc:
                logger.warning("iShares product API fetch failed for %s: %s", url, exc)
            continue

        tables: List[pd.DataFrame] = []
        try:
            tables = pd.read_html(url)
        except Exception as exc:
            logger.warning("Direct table parse failed for %s: %s", url, exc)

        if not tables:
            try:
                resp = requests.get(url, headers=headers, timeout=20)
                resp.raise_for_status()
                tables = pd.read_html(StringIO(resp.text))
            except Exception as exc:
                logger.warning("Constituent fetch failed for %s: %s", url, exc)
                continue

        for table in tables:
            col = _find_ticker_column(table)
            if not col:
                continue
            tickers = _sanitize_tickers(table[col].tolist())
            if len(tickers) >= 20:
                logger.info("Fetched %d constituents from %s", len(tickers), url)
                return tickers
    return []


def _fetch_from_ishares_product_api(product_id: str) -> List[str]:
    """
    Fetch constituents from the same product-data API used by iShares product pages.
    For Russell 2000 we use IWM (product id 239710).
    """
    endpoint = "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v2/get-product-data?"
    params = {
        "appSubType": "ISHARES",
        "appType": "PRODUCT_PAGE",
        "component": "holdings.all",
        "locale": "en_US",
        "portfolioId": str(product_id),
        "targetSite": "us-ishares",
        "userType": "individual",
        "excludeContent": "true",
        "includeConfig": "true",
    }

    resp = requests.get(
        endpoint,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    holdings = (
        payload.get("componentsByNameMap", {})
        .get("holdings", {})
        .get("containersByNameMap", {})
        .get("all", {})
        .get("dataPointsByNameMap", {})
    )

    tickers_raw = holdings.get("ticker", {}).get("value", [])
    weights_raw = holdings.get("holdingPercent", {}).get("value", [])

    weighted: List[tuple] = []
    for i, raw_ticker in enumerate(tickers_raw):
        cleaned = _sanitize_tickers([raw_ticker])
        if not cleaned:
            continue
        w = _safe_float(weights_raw[i]) if i < len(weights_raw) else None
        weighted.append((cleaned[0], w if w is not None else -1.0))

    # Keep strongest weight per ticker and sort descending as a liquidity proxy.
    best_by_ticker: Dict[str, float] = {}
    for t, w in weighted:
        prev = best_by_ticker.get(t)
        if prev is None or w > prev:
            best_by_ticker[t] = w

    ordered = sorted(best_by_ticker.items(), key=lambda x: (x[1], x[0]), reverse=True)
    return [t for t, _ in ordered]


def _apply_constituent_limit(tickers: List[str], max_constituents: Optional[int], universe_name: str) -> List[str]:
    if not max_constituents or max_constituents <= 0:
        return tickers
    if len(tickers) <= max_constituents:
        return tickers
    logger.info(
        "Applying constituent cap for %s: %d -> %d",
        universe_name,
        len(tickers),
        max_constituents,
    )
    return tickers[:max_constituents]


def _safe_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _prefilter_yahoo_symbols(tickers: List[str], batch_size: int = 80) -> List[str]:
    """
    Keep only symbols that produce at least one recent close in Yahoo data.
    This removes non-tradable/internal tickers that often appear in holdings feeds.
    """
    if not tickers:
        return []

    valid = set()
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i: i + batch_size]
        try:
            raw = yf.download(
                batch,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
                timeout=20,
            )
            if raw is None or raw.empty:
                continue

            if isinstance(raw.columns, pd.MultiIndex):
                for ticker in batch:
                    try:
                        c = raw[ticker]["Close"].dropna()
                        if not c.empty:
                            valid.add(ticker)
                    except Exception:
                        continue
            else:
                # Single ticker shape
                if len(batch) == 1 and "Close" in raw.columns and not raw["Close"].dropna().empty:
                    valid.add(batch[0])
        except Exception:
            continue

    filtered = [t for t in tickers if t in valid]
    logger.info("Yahoo symbol prefilter kept %d / %d tickers", len(filtered), len(tickers))
    return filtered


def _find_ticker_column(df: pd.DataFrame) -> Optional[str]:
    columns = [str(c).strip() for c in df.columns]
    for wanted in TICKER_COLUMNS:
        if wanted in columns:
            return wanted

    # Heuristic fallback for slight naming differences
    for c in columns:
        lowered = c.lower()
        if "symbol" in lowered or "ticker" in lowered:
            return c
    return None


def _sanitize_tickers(raw_values: List[object]) -> List[str]:
    out: List[str] = []
    seen = set()

    for raw in raw_values:
        if raw is None:
            continue
        t = str(raw).strip().upper()
        if not t or t in {"NAN", "NONE"}:
            continue

        # Common wiki footnotes and separators
        t = t.split("[")[0].strip()
        t = t.replace(".", "-")
        t = re.sub(r"[^A-Z0-9\-]", "", t)

        if not t or len(t) > 10:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)

    return out


def _read_cache() -> Dict[str, dict]:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("version") != CACHE_VERSION:
            return {}
        return payload.get("universes", {})
    except Exception as exc:
        logger.warning("Unable to read universe cache: %s", exc)
        return {}


def _write_cache(universes: Dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "universes": universes,
    }
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
    except Exception as exc:
        logger.warning("Unable to write universe cache: %s", exc)


def _is_cache_fresh(entry: Optional[dict], ttl_hours: int) -> bool:
    if not entry:
        return False
    ts = entry.get("updated_at")
    if not ts:
        return False
    try:
        updated = datetime.fromisoformat(ts)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - updated < timedelta(hours=max(1, ttl_hours))
    except Exception:
        return False
