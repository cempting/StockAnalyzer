"""
Agent – Portfolio Analyzer
Evaluates user holdings against current market conditions and screening scores.
Generates RESTOCK/HOLD/SELL recommendations for each position.
"""

import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from tools.market_data import fetch_ohlcv, fetch_info
from tools.fundamental_metrics import extract_fundamentals, score_prehn, assess_single_stock_filters
from tools.technical_indicators import add_indicators, get_technical_snapshot

logger = logging.getLogger(__name__)


def run(ctx: "AnalysisContext", portfolio_file: Optional[str] = None) -> None:
    """
    Analyze user portfolio holdings and generate buy/hold/sell recommendations.
    Compares each holding against screened universe statistics and market regime.
    """
    if not portfolio_file or not os.path.exists(portfolio_file):
        logger.warning("Portfolio file not provided or does not exist; skipping portfolio analysis")
        ctx.portfolio_analysis = []
        return

    logger.info("▶ PortfolioAnalystAgent starting")

    try:
        portfolio_df = pd.read_csv(portfolio_file)
    except Exception as e:
        logger.error("Failed to read portfolio file %s: %s", portfolio_file, e)
        ctx.portfolio_analysis = []
        return

    # Validate required columns
    if "Ticker" not in portfolio_df.columns:
        logger.error("Portfolio CSV must have 'Ticker' column")
        ctx.portfolio_analysis = []
        return

    holdings = []
    for _, row in portfolio_df.iterrows():
        ticker = str(row["Ticker"]).strip().upper()
        if not ticker:
            continue

        quantity = _safe_float(row.get("Quantity", 0), default=0.0)
        avg_cost = _safe_float(row.get("AverageCost", 0), default=0.0)
        entry_date = str(row.get("EntryDate", "")).strip() if "EntryDate" in portfolio_df.columns else ""
        days_held = _days_since(entry_date)

        holdings.append({
            "ticker": ticker,
            "quantity": quantity,
            "avg_cost": avg_cost,
            "entry_date": entry_date,
            "days_held": days_held,
        })

    if not holdings:
        logger.warning("No holdings found in portfolio file")
        ctx.portfolio_analysis = []
        return

    calibration = config.get_universe_calibration(getattr(ctx, "universe_name", "default"))
    prehn_w = float(calibration.get("blended_prehn_weight", 0.85))
    filter_w = float(calibration.get("blended_filter_weight", 0.15))

    # Universe benchmark stats used for recommendation thresholds.
    screened_scores = [
        float(s.get("blended_score", s.get("score", 0)))
        for s in (ctx.screened_stocks or [])
        if s.get("blended_score", s.get("score")) is not None
    ]
    if screened_scores:
        universe_mean_score = sum(screened_scores) / len(screened_scores)
        universe_25th = _percentile(screened_scores, 0.25)
        universe_50th = _percentile(screened_scores, 0.50)
        universe_75th = _percentile(screened_scores, 0.75)
    else:
        universe_mean_score = 50.0
        universe_25th = 42.0
        universe_50th = 55.0
        universe_75th = 70.0

    regime = (getattr(ctx, "market_assessment", {}) or {}).get("regime", "BALANCED")

    analysis = []
    for holding in holdings:
        ticker = holding["ticker"]

        tech, fund, current_price = _load_holding_snapshot(ctx, ticker)
        if current_price is None or not tech:
            logger.warning("Skipping %s: no technical data", ticker)
            continue

        # Score using existing logic
        prehn_score = score_prehn(tech, fund)
        filter_score = assess_single_stock_filters(fund, calibration.get("single_stock_filters"))
        total_score = round(
            prehn_score["total_score"] * prehn_w +
            (filter_score["score"] / filter_score["max_score"] * 100) * filter_w,
            2,
        )

        # Calculate position metrics
        unrealized_gain = (current_price - holding["avg_cost"]) * holding["quantity"]
        gain_pct = ((current_price - holding["avg_cost"]) / holding["avg_cost"] * 100) if holding["avg_cost"] > 0 else 0

        # Generate recommendation aligned to market regime and score percentiles.
        recommendation, reason = _recommend_action(
            blended_score=total_score,
            score_25=universe_25th,
            score_50=universe_50th,
            score_75=universe_75th,
            regime=regime,
            days_held=holding.get("days_held"),
            cash_runway_months=filter_score.get("cash_runway_months"),
            gain_pct=gain_pct,
        )

        sector = fund.get("sector", "")
        leading_us_sectors = ctx.leading_us_sectors or []
        if sector in leading_us_sectors and recommendation == "HOLD" and total_score >= universe_mean_score:
            recommendation = "RESTOCK"
            reason = f"{reason}; sector leadership tailwind ({sector})"

        entry = {
            "ticker": ticker,
            "quantity": holding["quantity"],
            "avg_cost": holding["avg_cost"],
            "entry_date": holding.get("entry_date", ""),
            "days_held": holding.get("days_held"),
            "current_price": current_price,
            "unrealized_gain": unrealized_gain,
            "gain_pct": gain_pct,
            "prehn_score": prehn_score["total_score"],
            "filter_score": filter_score["score"] / filter_score["max_score"] * 100,
            "blended_score": total_score,
            "percentile": _percentile_rank(total_score, screened_scores),
            "recommendation": recommendation,
            "reason": reason,
            "sector": sector,
            "cash_runway_months": filter_score.get("cash_runway_months"),
            "regime": regime,
        }
        analysis.append(entry)

    ctx.portfolio_analysis = analysis
    logger.info("✔ PortfolioAnalystAgent done – %d holdings analyzed", len(analysis))


def _percentile_rank(value: float, values: List[float]) -> float:
    """Calculate percentile rank of value within values list."""
    if not values or len(values) == 0:
        return 50.0
    sorted_vals = sorted(values)
    count_below = sum(1 for v in sorted_vals if v < value)
    return (count_below / len(sorted_vals)) * 100


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * q))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return float(sorted_vals[idx])


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _days_since(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(date_str, fmt).date()
            return (datetime.now().date() - dt).days
        except ValueError:
            continue
    return None


def _load_holding_snapshot(ctx: "AnalysisContext", ticker: str) -> tuple[Dict[str, Any], Dict[str, Any], Optional[float]]:
    snap_data = (ctx.snapshot_data or {}).get(ticker, {})
    tech = dict(snap_data.get("snap") or {})
    fund = dict(snap_data.get("fundamentals") or {})

    df = snap_data.get("ohlcv")
    if df is None:
        df = fetch_ohlcv(ticker, period="2y")
    if df is not None and not df.empty:
        if not tech:
            tech = get_technical_snapshot(add_indicators(df), ctx.benchmark_df)
        current_price = float(df["Close"].iloc[-1])
    else:
        current_price = None

    if not fund:
        info = fetch_info(ticker)
        fund = extract_fundamentals(info)

    return tech, fund, current_price


def _recommend_action(
    blended_score: float,
    score_25: float,
    score_50: float,
    score_75: float,
    regime: str,
    days_held: Optional[int],
    cash_runway_months: Optional[float],
    gain_pct: float,
) -> tuple[str, str]:
    # Hard risk rule: fragile balance sheet should not be averaged down.
    if cash_runway_months is not None and cash_runway_months < 6:
        return "SELL", f"Cash runway {cash_runway_months:.0f}m below 6m safety floor"

    if blended_score < score_25:
        if regime == "RISK-ON":
            return "SELL", f"Low score ({blended_score:.0f}) below 25th percentile in risk-on tape"
        return "HOLD", f"Low score ({blended_score:.0f}) but regime is defensive ({regime}); avoid forced selling"

    if blended_score >= score_75:
        if regime in ("RISK-ON", "BALANCED"):
            return "RESTOCK", f"High score ({blended_score:.0f}) above 75th percentile"
        return "HOLD", f"High score ({blended_score:.0f}) but regime is {regime}; keep size disciplined"

    if score_50 <= blended_score < score_75:
        return "HOLD", f"Score ({blended_score:.0f}) in upper-middle range; maintain position"

    # score_25 <= blended_score < score_50
    if days_held is not None and days_held > 90 and gain_pct > 15:
        return "SELL", f"Mediocre score ({blended_score:.0f}) with >90d holding and strong gain (+{gain_pct:.1f}%)"
    return "HOLD", f"Score ({blended_score:.0f}) in lower-middle range; watch for improvement"
