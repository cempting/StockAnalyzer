"""
Agent 2 – Sector Rotation
Ranks sectors by momentum across multiple timeframes and flags leadership.
"""

import logging
from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import config
from tools.market_data import fetch_sector_performance

logger = logging.getLogger(__name__)

PERIODS = ["1wk", "1mo", "3mo", "6mo", "1y"]


def run(ctx: "AnalysisContext") -> None:
    logger.info("▶ SectorRotationAgent starting")

    us_df = fetch_sector_performance(config.US_SECTOR_ETFS, periods=PERIODS)
    eu_df = fetch_sector_performance(config.EU_SECTOR_ETFS, periods=PERIODS)

    us_ranked  = _rank_sectors(us_df)
    eu_ranked  = _rank_sectors(eu_df)

    # Felix Prehn: focus on sectors in top 3 for both 1M and 3M momentum
    leading_us = _find_leaders(us_ranked)
    leading_eu = _find_leaders(eu_ranked)

    ctx.us_sector_df   = us_df
    ctx.eu_sector_df   = eu_df
    ctx.us_sector_rank = us_ranked
    ctx.eu_sector_rank = eu_ranked
    ctx.leading_us_sectors = leading_us
    ctx.leading_eu_sectors = leading_eu
    ctx.leading_sectors = leading_us + leading_eu  # used by screener

    logger.info(
        "✔ SectorRotationAgent done – US leaders: %s | EU leaders: %s",
        leading_us, leading_eu,
    )


def _rank_sectors(df: pd.DataFrame) -> pd.DataFrame:
    """Add composite momentum rank column."""
    if df.empty:
        return df
    result = df.copy()
    # Composite score: weighted average of available period returns
    weights = {"1wk": 0.1, "1mo": 0.25, "3mo": 0.30, "6mo": 0.20, "1y": 0.15}
    score = pd.Series(0.0, index=result.index)
    for col, w in weights.items():
        if col in result.columns:
            filled = result[col].fillna(0)
            score += filled * w
    result["momentum_score"] = score.round(2)
    result["rank"] = result["momentum_score"].rank(ascending=False).astype(int)
    return result.sort_values("rank")


def _find_leaders(df: pd.DataFrame, top_n: int = 3) -> List[str]:
    """Return top N sector names by composite momentum."""
    if df.empty or "rank" not in df.columns:
        return []
    top = df[df["rank"] <= top_n]
    return list(top.index)
