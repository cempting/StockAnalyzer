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
from tools.market_data import fetch_index_data

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

    ctx.market_phase = phase
    ctx.eu_market_phase = eu_phase
    ctx.breadth_signal = breadth_signal
    ctx.index_data = index_data
    ctx.uptrend_count = uptrend_count
    ctx.total_indices = total

    logger.info(
        "✔ MarketOverviewAgent done – US phase: %s | EU phase: %s | Breadth: %s",
        phase, eu_phase, breadth_signal,
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
