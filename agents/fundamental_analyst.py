"""
Agent 5 – Fundamental Analyst
Performs deep fundamental analysis on the top screened candidates,
applying Felix Prehn's CANSLIM-style quality criteria.
"""

import logging
from typing import Dict, Any, List, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config

logger = logging.getLogger(__name__)


# Named industry overrides (keyword-based) for stricter, context-aware thresholds.
# Values are (good, warn) tuples for each metric.
INDUSTRY_THRESHOLD_OVERRIDES: List[Tuple[List[str], Dict[str, Tuple[float, float]], str]] = [
    # --- Granular healthcare splits ---
    (
        ["medical devices", "medical instruments", "medical care facilities"],
        {
            "pe": (28.0, 45.0),
            "peg": (1.5, 2.4),
            "eps_growth": (0.18, 0.05),
            "revenue_growth": (0.12, 0.03),
            "roe": (0.14, 0.07),
            "net_margin": (0.12, 0.04),
            "debt_equity": (65.0, 160.0),
            "institutional": (0.36, 0.20),
        },
        "medical-devices",
    ),
    (
        ["diagnostics", "research", "health information services"],
        {
            "pe": (30.0, 50.0),
            "peg": (1.6, 2.6),
            "eps_growth": (0.20, 0.06),
            "revenue_growth": (0.14, 0.04),
            "roe": (0.13, 0.06),
            "net_margin": (0.10, 0.03),
            "debt_equity": (70.0, 170.0),
            "institutional": (0.34, 0.19),
        },
        "diagnostics/research",
    ),
    (
        ["biotech", "biotechnology", "drug manufacturers", "pharmaceutical"],
        {
            "pe": (45.0, 85.0),
            "peg": (1.8, 3.0),
            "eps_growth": (0.30, 0.08),
            "revenue_growth": (0.20, 0.05),
            "roe": (0.12, 0.04),
            "net_margin": (0.08, -0.02),
            "debt_equity": (70.0, 180.0),
            "institutional": (0.32, 0.18),
        },
        "biotech/pharma",
    ),
    # --- Granular semiconductor splits ---
    (
        ["semiconductor equipment", "chip equipment"],
        {
            "pe": (35.0, 58.0),
            "peg": (1.7, 2.8),
            "eps_growth": (0.28, 0.09),
            "revenue_growth": (0.20, 0.06),
            "roe": (0.16, 0.08),
            "net_margin": (0.15, 0.05),
            "debt_equity": (50.0, 120.0),
            "institutional": (0.40, 0.24),
        },
        "semiconductor-equipment",
    ),
    (
        ["semiconductor", "chip", "electronic components"],
        {
            "pe": (32.0, 52.0),
            "peg": (1.6, 2.6),
            "eps_growth": (0.26, 0.08),
            "revenue_growth": (0.18, 0.05),
            "roe": (0.16, 0.08),
            "net_margin": (0.14, 0.04),
            "debt_equity": (55.0, 130.0),
            "institutional": (0.38, 0.22),
        },
        "semiconductors",
    ),
    (
        ["software", "saas", "information technology services", "internet content"],
        {
            "pe": (38.0, 65.0),
            "peg": (1.8, 2.8),
            "eps_growth": (0.24, 0.07),
            "revenue_growth": (0.18, 0.06),
            "roe": (0.14, 0.06),
            "net_margin": (0.12, 0.00),
            "debt_equity": (45.0, 120.0),
            "institutional": (0.35, 0.20),
        },
        "software/internet",
    ),
    # --- Granular banking splits ---
    (
        ["banks—regional", "regional bank", "banks regional"],
        {
            "pe": (10.0, 16.0),
            "peg": (0.9, 1.5),
            "eps_growth": (0.14, 0.02),
            "revenue_growth": (0.07, 0.00),
            "roe": (0.10, 0.05),
            "net_margin": (0.08, 0.02),
            "debt_equity": (240.0, 460.0),
            "institutional": (0.35, 0.20),
        },
        "regional-banks",
    ),
    (
        ["banks—diversified", "diversified bank", "money center bank"],
        {
            "pe": (11.0, 18.0),
            "peg": (1.0, 1.7),
            "eps_growth": (0.15, 0.03),
            "revenue_growth": (0.08, 0.01),
            "roe": (0.11, 0.06),
            "net_margin": (0.09, 0.03),
            "debt_equity": (220.0, 430.0),
            "institutional": (0.40, 0.24),
        },
        "diversified-banks",
    ),
    (
        ["banks", "bank", "capital markets", "asset management", "financial data"],
        {
            "pe": (12.0, 20.0),
            "peg": (1.0, 1.8),
            "eps_growth": (0.16, 0.03),
            "revenue_growth": (0.10, 0.01),
            "roe": (0.11, 0.06),
            "net_margin": (0.10, 0.03),
            "debt_equity": (220.0, 420.0),
            "institutional": (0.40, 0.24),
        },
        "banks/capital-markets",
    ),
    (
        ["insurance"],
        {
            "pe": (11.0, 18.0),
            "peg": (1.0, 1.6),
            "eps_growth": (0.12, 0.02),
            "revenue_growth": (0.08, 0.00),
            "roe": (0.10, 0.05),
            "net_margin": (0.08, 0.02),
            "debt_equity": (140.0, 300.0),
            "institutional": (0.35, 0.20),
        },
        "insurance",
    ),
    (
        ["utilities", "regulated electric", "renewable utilities"],
        {
            "pe": (20.0, 30.0),
            "peg": (1.3, 2.2),
            "eps_growth": (0.10, 0.01),
            "revenue_growth": (0.07, 0.00),
            "roe": (0.09, 0.05),
            "net_margin": (0.10, 0.03),
            "debt_equity": (100.0, 240.0),
            "institutional": (0.42, 0.25),
        },
        "utilities",
    ),
    (
        ["reit", "real estate", "real estate services", "real estate—"],
        {
            "pe": (22.0, 35.0),
            "peg": (1.4, 2.4),
            "eps_growth": (0.10, 0.00),
            "revenue_growth": (0.08, 0.00),
            "roe": (0.08, 0.04),
            "net_margin": (0.10, 0.02),
            "debt_equity": (90.0, 230.0),
            "institutional": (0.36, 0.20),
        },
        "real-estate/reit",
    ),
    (
        ["oil", "gas", "energy", "e&p", "integrated"],
        {
            "pe": (12.0, 22.0),
            "peg": (1.1, 2.0),
            "eps_growth": (0.14, 0.00),
            "revenue_growth": (0.10, 0.00),
            "roe": (0.12, 0.06),
            "net_margin": (0.10, 0.03),
            "debt_equity": (70.0, 180.0),
            "institutional": (0.38, 0.22),
        },
        "energy",
    ),
    (
        ["aerospace", "defense", "industrial machinery", "transportation", "logistics"],
        {
            "pe": (22.0, 35.0),
            "peg": (1.3, 2.2),
            "eps_growth": (0.14, 0.03),
            "revenue_growth": (0.10, 0.02),
            "roe": (0.12, 0.06),
            "net_margin": (0.09, 0.03),
            "debt_equity": (65.0, 160.0),
            "institutional": (0.36, 0.21),
        },
        "industrials",
    ),
]


def run(ctx: "AnalysisContext") -> None:
    logger.info("▶ FundamentalAnalystAgent starting")

    top = (ctx.screened_stocks or [])[:config.MAX_DETAIL_STOCKS]
    fa_results: Dict[str, Dict[str, Any]] = {}

    for item in top:
        ticker = item["ticker"]
        fund   = item.get("_fund", {})
        profile = _infer_threshold_profile(fund)
        fa_results[ticker] = {
            "metrics":      _build_metrics_table(fund, profile),
            "threshold_profile": profile,
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


def _build_metrics_table(fund: Dict[str, Any], profile: Dict[str, str]) -> List[Dict[str, str]]:
    """Return a list of {label, value, signal, thresholds} dicts for deep-dive views."""
    rows = []

    def row(label, val, signal="neutral", thresholds=""):
        rows.append({"label": label, "value": val, "signal": signal, "thresholds": thresholds})

    def bucket_signal(value: Any, good_level: float, warn_level: float, higher_is_better: bool = True) -> str:
        if value is None:
            return "neutral"
        if higher_is_better:
            if value >= good_level:
                return "good"
            if value >= warn_level:
                return "warn"
            return "bad"
        if value <= good_level:
            return "good"
        if value <= warn_level:
            return "warn"
        return "bad"

    thresholds = _metric_thresholds(profile)

    # Valuation
    pe = fund.get("forward_pe") or fund.get("trailing_pe")
    pe_good, pe_warn = thresholds["pe"]
    pe_sig = bucket_signal(pe, pe_good, pe_warn, higher_is_better=False)
    row("Forward P/E", _fmt(pe, dp=1), pe_sig, f"Good <= {pe_good:.0f} | Mediocre <= {pe_warn:.0f} | Bad > {pe_warn:.0f}")

    peg = fund.get("peg")
    peg_good, peg_warn = thresholds["peg"]
    peg_sig = bucket_signal(peg, peg_good, peg_warn, higher_is_better=False)
    row("PEG Ratio", _fmt(peg, dp=2), peg_sig, f"Good <= {peg_good:.2f} | Mediocre <= {peg_warn:.2f} | Bad > {peg_warn:.2f}")

    pb = fund.get("pb")
    row("Price/Book", _fmt(pb, dp=2), thresholds="Sector-dependent: lower vs peers is better")

    ev = fund.get("ev_ebitda")
    row("EV/EBITDA", _fmt(ev, dp=1), thresholds="Sector-dependent: lower vs peers is better")

    # Growth
    eg = fund.get("earnings_growth")
    eg_good, eg_warn = thresholds["eps_growth"]
    eg_sig = bucket_signal(eg, eg_good, eg_warn, higher_is_better=True)
    row("EPS Growth (YoY)", _fmt(eg, pct=True), eg_sig,
        f"Good >= {eg_good*100:.0f}% | Mediocre >= {eg_warn*100:.0f}% | Bad < {eg_warn*100:.0f}%")

    rg = fund.get("revenue_growth")
    rg_good, rg_warn = thresholds["revenue_growth"]
    rg_sig = bucket_signal(rg, rg_good, rg_warn, higher_is_better=True)
    row("Revenue Growth (YoY)", _fmt(rg, pct=True), rg_sig,
        f"Good >= {rg_good*100:.0f}% | Mediocre >= {rg_warn*100:.0f}% | Bad < {rg_warn*100:.0f}%")

    row("Trailing EPS", _fmt(fund.get("trailing_eps"), dp=2))
    row("Forward EPS", _fmt(fund.get("forward_eps"), dp=2))

    # Quality
    roe = fund.get("roe")
    roe_good, roe_warn = thresholds["roe"]
    roe_sig = bucket_signal(roe, roe_good, roe_warn, higher_is_better=True)
    row("ROE", _fmt(roe, pct=True), roe_sig,
        f"Good >= {roe_good*100:.0f}% | Mediocre >= {roe_warn*100:.0f}% | Bad < {roe_warn*100:.0f}%")

    roa = fund.get("roa")
    row("ROA", _fmt(roa, pct=True))

    pm = fund.get("profit_margins")
    pm_good, pm_warn = thresholds["net_margin"]
    pm_sig = bucket_signal(pm, pm_good, pm_warn, higher_is_better=True)
    row("Net Margin", _fmt(pm, pct=True), pm_sig,
        f"Good >= {pm_good*100:.0f}% | Mediocre >= {pm_warn*100:.0f}% | Bad < {pm_warn*100:.0f}%")

    gm = fund.get("gross_margins")
    row("Gross Margin", _fmt(gm, pct=True))

    om = fund.get("operating_margins")
    row("Operating Margin", _fmt(om, pct=True))

    # Balance sheet
    de = fund.get("debt_equity")
    de_good, de_warn = thresholds["debt_equity"]
    de_sig = bucket_signal(de, de_good, de_warn, higher_is_better=False)
    row("Debt / Equity", _fmt(de, dp=1) if de else "N/A", de_sig,
        f"Good <= {de_good:.0f} | Mediocre <= {de_warn:.0f} | Bad > {de_warn:.0f}")

    row("Current Ratio", _fmt(fund.get("current_ratio"), dp=2), thresholds="Good >= 1.5 | Mediocre 1.0-1.5 | Bad < 1.0")

    runway = _cash_runway_months(fund)
    if runway is None:
        runway_val, runway_sig = "N/A", "neutral"
    elif runway >= 24:
        runway_val, runway_sig = f"{runway:.0f} months", "good"
    elif runway >= 12:
        runway_val, runway_sig = f"{runway:.0f} months", "warn"
    else:
        runway_val, runway_sig = f"{runway:.0f} months", "bad"
    row("Cash Runway (est.)", runway_val, runway_sig, "Good >= 24m | Mediocre 12-24m | Bad < 12m")

    # Market
    mc = fund.get("market_cap")
    row("Market Cap", _fmt(mc))

    beta = fund.get("beta")
    row("Beta", _fmt(beta, dp=2), thresholds="Low vol < 0.8 | Normal 0.8-1.3 | High vol > 1.3")

    inst = fund.get("held_percent_institutions")
    inst_good, inst_warn = thresholds["institutional"]
    inst_sig = bucket_signal(inst, inst_good, inst_warn, higher_is_better=True)
    row("Institutional Ownership", _fmt(inst, pct=True), inst_sig,
        f"Good >= {inst_good*100:.0f}% | Mediocre >= {inst_warn*100:.0f}% | Bad < {inst_warn*100:.0f}%")

    insider = fund.get("held_percent_insiders")
    insider_sig = "warn" if insider and insider >= 0.35 else "neutral"
    row("Insider Ownership", _fmt(insider, pct=True), insider_sig, "Contextual: very high insider can reduce float/liquidity")

    div = fund.get("dividend_yield")
    row("Dividend Yield", _fmt(div, pct=True) if div else "–", thresholds="Sector-dependent: Utilities/REITs expected higher")

    return rows


def _infer_threshold_profile(fund: Dict[str, Any]) -> Dict[str, str]:
    sector = (fund.get("sector") or "").lower()
    industry = (fund.get("industry") or "").lower()
    market_cap = fund.get("market_cap")
    beta = fund.get("beta")

    if market_cap is None:
        cap_bucket = "unknown"
    elif market_cap < 2_000_000_000:
        cap_bucket = "small"
    elif market_cap < 10_000_000_000:
        cap_bucket = "mid"
    elif market_cap < 200_000_000_000:
        cap_bucket = "large"
    else:
        cap_bucket = "mega"

    if beta is None:
        vol_bucket = "unknown"
    elif beta > 1.4:
        vol_bucket = "high"
    elif beta < 0.8:
        vol_bucket = "low"
    else:
        vol_bucket = "normal"

    if "bank" in industry or "financial" in sector or "insurance" in industry:
        style = "financial"
    elif "utility" in sector or "real estate" in sector:
        style = "defensive"
    elif "biotech" in industry or "software" in industry or "semiconductor" in industry or "technology" in sector:
        style = "growth"
    elif "energy" in sector or "materials" in sector:
        style = "cyclical"
    else:
        style = "core"

    return {
        "sector": fund.get("sector") or "Unknown",
        "industry": fund.get("industry") or "Unknown",
        "cap_bucket": cap_bucket,
        "volatility": vol_bucket,
        "style": style,
        "industry_rule": _match_industry_rule(sector, industry),
    }


def _match_industry_rule(sector: str, industry: str) -> str:
    text = f"{sector} | {industry}".lower()
    for keywords, _, rule_name in INDUSTRY_THRESHOLD_OVERRIDES:
        if any(k in text for k in keywords):
            return rule_name
    return "none"


def _metric_thresholds(profile: Dict[str, str]) -> Dict[str, Tuple[float, float]]:
    style = profile.get("style", "core")
    cap = profile.get("cap_bucket", "unknown")
    vol = profile.get("volatility", "unknown")
    rule_name = profile.get("industry_rule", "none")

    # Baseline thresholds: (good, warn)
    rules: Dict[str, Tuple[float, float]] = {
        "pe": (24.0, 40.0),
        "peg": (1.2, 2.0),
        "eps_growth": (0.20, 0.05),
        "revenue_growth": (0.12, 0.03),
        "roe": (0.16, 0.08),
        "net_margin": (0.14, 0.05),
        "debt_equity": (60.0, 160.0),
        "institutional": (0.40, 0.22),
    }

    # Sector/industry style adjustments
    if style == "growth":
        rules["pe"] = (35.0, 60.0)
        rules["peg"] = (1.6, 2.6)
        rules["eps_growth"] = (0.25, 0.08)
        rules["revenue_growth"] = (0.18, 0.06)
        rules["net_margin"] = (0.10, 0.00)
    elif style == "financial":
        rules["pe"] = (14.0, 22.0)
        rules["peg"] = (1.0, 1.8)
        rules["roe"] = (0.12, 0.06)
        rules["debt_equity"] = (180.0, 350.0)  # D/E naturally higher for financials
        rules["net_margin"] = (0.10, 0.03)
    elif style == "defensive":
        rules["pe"] = (22.0, 32.0)
        rules["eps_growth"] = (0.12, 0.02)
        rules["revenue_growth"] = (0.08, 0.01)
        rules["debt_equity"] = (90.0, 220.0)
    elif style == "cyclical":
        rules["pe"] = (18.0, 30.0)
        rules["eps_growth"] = (0.15, 0.03)
        rules["revenue_growth"] = (0.10, 0.02)
        rules["net_margin"] = (0.12, 0.03)

    # Cap/volatility adjustments (small/high-vol should demand stronger growth).
    if cap == "small" or vol == "high":
        eps_g, eps_w = rules["eps_growth"]
        rev_g, rev_w = rules["revenue_growth"]
        inst_g, inst_w = rules["institutional"]
        rules["eps_growth"] = (eps_g + 0.05, eps_w + 0.02)
        rules["revenue_growth"] = (rev_g + 0.04, rev_w + 0.01)
        rules["institutional"] = (inst_g - 0.05, max(0.10, inst_w - 0.04))
    elif cap == "mega" and vol == "low":
        eps_g, eps_w = rules["eps_growth"]
        rev_g, rev_w = rules["revenue_growth"]
        rules["eps_growth"] = (max(0.10, eps_g - 0.04), max(0.00, eps_w - 0.02))
        rules["revenue_growth"] = (max(0.06, rev_g - 0.03), max(0.00, rev_w - 0.01))

    # Named-industry strict overrides win over style-level rules.
    if rule_name != "none":
        for keywords, override_rules, override_name in INDUSTRY_THRESHOLD_OVERRIDES:
            if override_name == rule_name:
                rules.update(override_rules)
                break

    return rules


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
    runway = _cash_runway_months(fund)
    if runway and runway >= 18:
        s.append(f"Estimated cash runway {runway:.0f}+ months")
    if fund.get("held_percent_institutions") and fund["held_percent_institutions"] >= 0.40:
        s.append(f"Institutional ownership {fund['held_percent_institutions']*100:.0f}%")
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
    runway = _cash_runway_months(fund)
    if runway is not None and runway < 12:
        r.append(f"Limited cash runway ({runway:.0f} months) raises financing risk")
    if fund.get("held_percent_institutions") is not None and fund["held_percent_institutions"] < 0.20:
        r.append("Low institutional ownership may limit sponsorship")
    return r or ["No major fundamental red flags"]


def _cash_runway_months(fund: Dict[str, Any]) -> Any:
    total_cash = fund.get("total_cash")
    if total_cash is None or total_cash <= 0:
        return None

    annual_cf = fund.get("free_cashflow")
    if annual_cf is None:
        annual_cf = fund.get("operating_cashflow")
    if annual_cf is None:
        return None
    if annual_cf >= 0:
        return 120.0

    monthly_burn = abs(annual_cf) / 12.0
    if monthly_burn == 0:
        return None
    return total_cash / monthly_burn
