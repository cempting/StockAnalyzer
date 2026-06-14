"""
Agent 5 – Fundamental Analyst
Performs deep fundamental analysis on the top screened candidates,
applying Felix Prehn's CANSLIM-style quality criteria.
"""

import logging
from typing import Dict, Any, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config

logger = logging.getLogger(__name__)


def run(ctx: "AnalysisContext") -> None:
    logger.info("▶ FundamentalAnalystAgent starting")

    top = (ctx.screened_stocks or [])[:config.MAX_DETAIL_STOCKS]
    fa_results: Dict[str, Dict[str, Any]] = {}

    for item in top:
        ticker = item["ticker"]
        fund   = item.get("_fund", {})
        fa_results[ticker] = {
            "metrics":      _build_metrics_table(fund),
            "narrative":    _build_narrative(fund),
            "strengths":    _find_strengths(fund),
            "risks":        _find_risks(fund),
        }

    ctx.fundamental_analyses = fa_results
    logger.info("✔ FundamentalAnalystAgent done")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(val, pct: bool = False, mult: bool = False, dp: int = 1) -> str:
    if val is None:
        return "N/A"
    if pct:
        return f"{val * 100:.{dp}f}%"
    if mult:
        return f"{val:.{dp}f}x"
    if abs(val) >= 1_000_000_000:
        return f"${val/1_000_000_000:.1f}B"
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:.0f}M"
    return f"{val:.{dp}f}"


def _build_metrics_table(fund: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return a list of {label, value, signal} dicts for the HTML table."""
    rows = []

    def row(label, val, signal="neutral"):
        rows.append({"label": label, "value": val, "signal": signal})

    # Valuation
    pe = fund.get("forward_pe") or fund.get("trailing_pe")
    pe_sig = "good" if pe and pe < 25 else "warn" if pe and pe < 45 else "bad" if pe else "neutral"
    row("Forward P/E", _fmt(pe, dp=1), pe_sig)

    peg = fund.get("peg")
    peg_sig = "good" if peg and peg < 1.0 else "warn" if peg and peg < 2.0 else "bad" if peg else "neutral"
    row("PEG Ratio", _fmt(peg, dp=2), peg_sig)

    pb = fund.get("pb")
    row("Price/Book", _fmt(pb, dp=2))

    ev = fund.get("ev_ebitda")
    row("EV/EBITDA", _fmt(ev, dp=1))

    # Growth
    eg = fund.get("earnings_growth")
    eg_sig = "good" if eg and eg > 0.20 else "warn" if eg and eg > 0 else "bad" if eg is not None else "neutral"
    row("EPS Growth (YoY)", _fmt(eg, pct=True), eg_sig)

    rg = fund.get("revenue_growth")
    rg_sig = "good" if rg and rg > 0.10 else "warn" if rg and rg > 0 else "bad" if rg is not None else "neutral"
    row("Revenue Growth (YoY)", _fmt(rg, pct=True), rg_sig)

    row("Trailing EPS", _fmt(fund.get("trailing_eps"), dp=2))
    row("Forward EPS", _fmt(fund.get("forward_eps"), dp=2))

    # Quality
    roe = fund.get("roe")
    roe_sig = "good" if roe and roe > 0.15 else "warn" if roe and roe > 0.05 else "bad" if roe is not None else "neutral"
    row("ROE", _fmt(roe, pct=True), roe_sig)

    roa = fund.get("roa")
    row("ROA", _fmt(roa, pct=True))

    pm = fund.get("profit_margins")
    pm_sig = "good" if pm and pm > 0.15 else "warn" if pm and pm > 0 else "bad" if pm is not None else "neutral"
    row("Net Margin", _fmt(pm, pct=True), pm_sig)

    gm = fund.get("gross_margins")
    row("Gross Margin", _fmt(gm, pct=True))

    om = fund.get("operating_margins")
    row("Operating Margin", _fmt(om, pct=True))

    # Balance sheet
    de = fund.get("debt_equity")
    de_sig = "good" if de and de < 50 else "warn" if de and de < 150 else "bad" if de is not None else "neutral"
    row("Debt / Equity", _fmt(de, dp=1) if de else "N/A", de_sig)

    row("Current Ratio", _fmt(fund.get("current_ratio"), dp=2))

    # Market
    mc = fund.get("market_cap")
    row("Market Cap", _fmt(mc))

    beta = fund.get("beta")
    row("Beta", _fmt(beta, dp=2))

    div = fund.get("dividend_yield")
    row("Dividend Yield", _fmt(div, pct=True) if div else "–")

    return rows


def _build_narrative(fund: Dict[str, Any]) -> str:
    """One-paragraph fundamental summary."""
    name    = fund.get("name", "This company")
    sector  = fund.get("sector", "")
    country = fund.get("country", "")
    eg      = fund.get("earnings_growth")
    rg      = fund.get("revenue_growth")
    pe      = fund.get("forward_pe") or fund.get("trailing_pe")
    roe     = fund.get("roe")
    pm      = fund.get("profit_margins")
    de      = fund.get("debt_equity")

    parts = [f"**{name}**"]
    if sector:
        parts[0] += f" ({sector}" + (f", {country})" if country else ")")

    if eg is not None and rg is not None:
        parts.append(
            f"is growing earnings at {eg*100:.0f}% YoY with {rg*100:.0f}% revenue growth"
        )
    elif eg is not None:
        parts.append(f"shows {eg*100:.0f}% YoY EPS growth")

    if pe and pe > 0:
        qual = "cheap" if pe < 15 else "fairly valued" if pe < 25 else "at a premium" if pe < 40 else "richly valued"
        parts.append(f"trades {qual} at P/E {pe:.0f}")

    if roe and roe > 0:
        quality = "exceptional" if roe > 0.25 else "solid" if roe > 0.12 else "modest"
        parts.append(f"with {quality} ROE of {roe*100:.0f}%")

    if pm and pm > 0:
        parts.append(f"and {pm*100:.0f}% net margins")

    if de is not None:
        if de < 30:
            parts.append("The balance sheet is clean with minimal leverage.")
        elif de > 150:
            parts.append("Leverage is elevated and warrants monitoring.")

    return " ".join(parts[:4]) + ". " + " ".join(parts[4:])


def _find_strengths(fund: Dict[str, Any]) -> List[str]:
    s = []
    if fund.get("earnings_growth", 0) and fund["earnings_growth"] > 0.20:
        s.append(f"Strong EPS growth {fund['earnings_growth']*100:.0f}%")
    if fund.get("revenue_growth", 0) and fund["revenue_growth"] > 0.10:
        s.append(f"Accelerating revenue {fund['revenue_growth']*100:.0f}%")
    if fund.get("roe", 0) and fund["roe"] > 0.18:
        s.append(f"High ROE {fund['roe']*100:.0f}%")
    if fund.get("profit_margins", 0) and fund["profit_margins"] > 0.20:
        s.append(f"Fat net margins {fund['profit_margins']*100:.0f}%")
    if fund.get("debt_equity") is not None and fund["debt_equity"] < 40:
        s.append("Low leverage / strong balance sheet")
    if fund.get("peg") and 0 < fund["peg"] < 1.2:
        s.append(f"Attractive PEG ratio {fund['peg']:.2f}")
    return s or ["No standout fundamental strengths identified"]


def _find_risks(fund: Dict[str, Any]) -> List[str]:
    r = []
    pe = fund.get("forward_pe") or fund.get("trailing_pe")
    if pe and pe > 50:
        r.append(f"High valuation – P/E {pe:.0f} leaves limited margin of safety")
    if fund.get("earnings_growth") is not None and fund["earnings_growth"] < 0:
        r.append(f"Declining EPS growth ({fund['earnings_growth']*100:.0f}%)")
    if fund.get("revenue_growth") is not None and fund["revenue_growth"] < 0:
        r.append("Revenue contraction")
    if fund.get("debt_equity") is not None and fund["debt_equity"] > 150:
        r.append(f"High leverage D/E {fund['debt_equity']:.0f}")
    if fund.get("profit_margins") is not None and fund["profit_margins"] < 0.05:
        r.append("Thin or negative margins")
    if fund.get("beta") and fund["beta"] > 1.5:
        r.append(f"High beta {fund['beta']:.2f} – amplified downside in market selloffs")
    return r or ["No major fundamental red flags"]
