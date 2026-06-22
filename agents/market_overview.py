"""
Agent 1 – Market Overview
Determines the overall market phase, index health, and breadth signals.
Writes results into the shared AnalysisContext.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from tools.market_data import fetch_index_data, fetch_ohlcv

logger = logging.getLogger(__name__)


def run(ctx: "AnalysisContext") -> None:
    """Entry point called by the orchestrator."""
    logger.info("▶ MarketOverviewAgent starting")

    index_data = fetch_index_data(config.MAJOR_INDICES, period="1y")

    # Determine overall market phase
    sp500 = index_data.get("S&P 500", {})
    dax   = index_data.get("DAX 40", {})

    phase = _assess_phase(sp500)
    eu_phase = _assess_phase(dax)

    # Count how many indices are in uptrend
    uptrend_count = sum(
        1 for d in index_data.values()
        if d.get("above_ma200") and d.get("above_ma50")
    )
    total = len(index_data)

    breadth_signal = (
        "STRONG BULL" if uptrend_count >= total * 0.8 else
        "BULL"        if uptrend_count >= total * 0.6 else
        "MIXED"       if uptrend_count >= total * 0.4 else
        "BEAR"
    )

    # Macro context inspired by the market-collision playbook:
    # falling oil and yields are treated as equity tailwinds.
    oil_6w_chg = _pct_change_over(fetch_ohlcv("CL=F", period="6mo"), sessions=30)
    y10_6w_chg = _pct_change_over(fetch_ohlcv("^TNX", period="6mo"), sessions=30)

    breadth_pts = _breadth_points(uptrend_count, total)
    us_pts = _phase_points(phase)
    eu_pts = _phase_points(eu_phase)
    oil_pts = _macro_points(oil_6w_chg, inverse=True)
    yld_pts = _macro_points(y10_6w_chg, inverse=True)

    total_score = breadth_pts + us_pts + eu_pts + oil_pts + yld_pts
    regime = (
        "RISK-ON" if total_score >= 9 else
        "BALANCED" if total_score >= 6 else
        "RISK-OFF"
    )
    guidance = (
        "Lean long; prioritize leading sectors and breakouts"
        if regime == "RISK-ON" else
        "Selective exposure; favor quality and strong relative strength"
        if regime == "BALANCED" else
        "Reduce risk; tighten stops and avoid weak sectors"
    )

    ctx.market_phase = phase
    ctx.eu_market_phase = eu_phase
    ctx.breadth_signal = breadth_signal
    ctx.market_assessment = {
        "score": total_score,
        "max_score": 12,
        "regime": regime,
        "guidance": guidance,
        "oil_6w_chg": oil_6w_chg,
        "yield10_6w_chg": y10_6w_chg,
        "components": {
            "breadth": breadth_pts,
            "us_trend": us_pts,
            "eu_trend": eu_pts,
            "oil_tailwind": oil_pts,
            "rates_tailwind": yld_pts,
        },
    }
    ctx.index_data = index_data
    ctx.uptrend_count = uptrend_count
    ctx.total_indices = total

    logger.info(
        "✔ MarketOverviewAgent done – US: %s | EU: %s | Breadth: %s | Regime: %s (%d/12)",
        phase, eu_phase, breadth_signal, regime, total_score,
    )


def _assess_phase(idx: Dict[str, Any]) -> str:
    """Classify index into a market phase string."""
    if not idx or "error" in idx:
        return "UNKNOWN"

    above_50  = idx.get("above_ma50",  False)
    above_200 = idx.get("above_ma200", False)
    chg_1m    = idx.get("1m_chg",  0) or 0
    chg_1y    = idx.get("1y_chg",  0) or 0

    if above_200 and above_50 and chg_1y > 10:
        return "BULL MARKET"
    elif above_200 and above_50:
        return "UPTREND"
    elif above_200 and not above_50 and chg_1m < 0:
        return "CORRECTION (above MA200)"
    elif not above_200 and above_50:
        return "RECOVERY ATTEMPT"
    elif not above_200 and not above_50 and chg_1y < -15:
        return "BEAR MARKET"
    else:
        return "DOWNTREND"


def _pct_change_over(df, sessions: int = 30) -> Optional[float]:
    """Return percent change over N sessions, or None if unavailable."""
    if df is None or df.empty or "Close" not in df.columns:
        return None
    close = df["Close"].dropna()
    if len(close) < 2:
        return None
    ref_idx = max(0, len(close) - sessions - 1)
    ref = close.iloc[ref_idx]
    if not ref:
        return None
    return round((close.iloc[-1] / ref - 1) * 100, 2)


def _phase_points(phase: str) -> int:
    p = (phase or "").upper()
    if "BULL" in p:
        return 2
    if "UPTREND" in p or "CORRECTION" in p or "RECOVERY" in p:
        return 1
    return 0


def _breadth_points(uptrend_count: int, total: int) -> int:
    if total <= 0:
        return 0
    ratio = uptrend_count / total
    if ratio >= 0.8:
        return 4
    if ratio >= 0.6:
        return 3
    if ratio >= 0.4:
        return 2
    if ratio >= 0.2:
        return 1
    return 0


def _macro_points(chg: Optional[float], inverse: bool = False) -> int:
    """
    Score macro series on a 0-2 scale.
    inverse=True means falling values are bullish (oil/yields).
    """
    if chg is None:
        return 1

    effective = -chg if inverse else chg
    if effective >= 10:
        return 2
    if effective >= 2:
        return 1
    return 0
