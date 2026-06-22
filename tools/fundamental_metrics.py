"""
Fundamental metrics extraction from yfinance .info dicts.
"""

from typing import Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────

def extract_fundamentals(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull and normalise the metrics Felix Prehn looks at.
    All ratios stored as decimals (e.g. 0.25 = 25%).
    """

    def get(key, default=None):
        v = info.get(key)
        return v if v not in (None, "N/A", "", float("inf"), float("-inf")) else default

    # Valuation
    trailing_pe  = _safe_float(get("trailingPE"))
    forward_pe   = _safe_float(get("forwardPE"))
    peg          = _safe_float(get("pegRatio"))
    pb           = _safe_float(get("priceToBook"))
    ps           = _safe_float(get("priceToSalesTrailing12Months"))
    ev_ebitda    = _safe_float(get("enterpriseToEbitda"))

    # Growth
    eps_growth   = _safe_float(get("earningsGrowth"))   # YoY trailing
    rev_growth   = _safe_float(get("revenueGrowth"))    # YoY trailing

    # Quality
    roe          = _safe_float(get("returnOnEquity"))
    roa          = _safe_float(get("returnOnAssets"))
    profit_margin = _safe_float(get("profitMargins"))
    gross_margin = _safe_float(get("grossMargins"))
    operating_margin = _safe_float(get("operatingMargins"))

    # Balance sheet
    debt_equity  = _safe_float(get("debtToEquity"))
    current_ratio = _safe_float(get("currentRatio"))
    quick_ratio  = _safe_float(get("quickRatio"))

    # Per share
    trailing_eps = _safe_float(get("trailingEps"))
    forward_eps  = _safe_float(get("forwardEps"))
    book_value   = _safe_float(get("bookValue"))
    revenue_per_share = _safe_float(get("revenuePerShare"))

    # Market data
    market_cap   = _safe_float(get("marketCap"))
    beta         = _safe_float(get("beta"))
    dividend_yield = _safe_float(get("dividendYield"))
    total_cash   = _safe_float(get("totalCash"))
    free_cashflow = _safe_float(get("freeCashflow"))
    operating_cashflow = _safe_float(get("operatingCashflow"))
    held_pct_inst = _safe_float(get("heldPercentInstitutions"))
    held_pct_ins = _safe_float(get("heldPercentInsiders"))

    # Identity
    name         = get("shortName") or get("longName") or ""
    sector       = get("sector") or ""
    industry     = get("industry") or ""
    country      = get("country") or ""
    currency     = get("currency") or ""
    exchange     = get("exchange") or ""

    return {
        # Identity
        "name":           name,
        "sector":         sector,
        "industry":       industry,
        "country":        country,
        "currency":       currency,
        "exchange":       exchange,

        # Valuation
        "trailing_pe":    trailing_pe,
        "forward_pe":     forward_pe,
        "peg":            peg,
        "pb":             pb,
        "ps":             ps,
        "ev_ebitda":      ev_ebitda,

        # Growth
        "earnings_growth": eps_growth,
        "revenue_growth":  rev_growth,

        # Quality
        "roe":             roe,
        "roa":             roa,
        "profit_margins":  profit_margin,
        "gross_margins":   gross_margin,
        "operating_margins": operating_margin,

        # Balance sheet
        "debt_equity":     debt_equity,
        "current_ratio":   current_ratio,
        "quick_ratio":     quick_ratio,

        # Per share
        "trailing_eps":    trailing_eps,
        "forward_eps":     forward_eps,
        "book_value":      book_value,
        "revenue_per_share": revenue_per_share,

        # Market
        "market_cap":      market_cap,
        "beta":            beta,
        "dividend_yield":  dividend_yield,
        "total_cash":      total_cash,
        "free_cashflow":   free_cashflow,
        "operating_cashflow": operating_cashflow,
        "held_percent_institutions": held_pct_inst,
        "held_percent_insiders": held_pct_ins,
    }


def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
        if f != f or abs(f) > 1e15:   # NaN or absurd value
            return None
        return f
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FELIX PREHN SCORING
# ─────────────────────────────────────────────────────────────────────────────

def score_prehn(tech: Dict[str, Any], fund: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a 0-100 Felix Prehn composite score combining
    technical stage analysis + CANSLIM-style fundamentals.

    Returns dict with:
        total_score   int (0–100)
        percentage    float
        rating        str ('STRONG BUY' / 'BUY' / 'WATCH' / 'AVOID')
        breakdown     dict of criterion → (description, earned, max)
    """
    score = 0
    breakdown: Dict[str, tuple] = {}

    # ── TECHNICAL (50 pts) ───────────────────────────────────────────────────

    # Stage 2 (20 pts)
    stage = tech.get("stage", 0)
    if stage == 2:
        pts = 20
    elif stage == 1:
        pts = 8   # potential base
    else:
        pts = 0
    score += pts
    breakdown["Stage"] = (_stage_label(stage), pts, 20)

    # Above MAs (15 pts: 5 each for MA50/150/200)
    ma_pts = (
        (5 if tech.get("above_ma50")  else 0) +
        (5 if tech.get("above_ma150") else 0) +
        (5 if tech.get("above_ma200") else 0)
    )
    score += ma_pts
    breakdown["Moving Averages"] = (
        f"MA50:{'✓' if tech.get('above_ma50') else '✗'}  "
        f"MA150:{'✓' if tech.get('above_ma150') else '✗'}  "
        f"MA200:{'✓' if tech.get('above_ma200') else '✗'}",
        ma_pts, 15,
    )

    # RSI (5 pts)
    rsi = tech.get("rsi")
    if rsi is not None:
        if 50 <= rsi <= 70:
            rsi_pts = 5
        elif 40 <= rsi < 50 or 70 < rsi <= 80:
            rsi_pts = 2
        else:
            rsi_pts = 0
        rsi_label = f"RSI {rsi:.1f}"
    else:
        rsi_pts, rsi_label = 2, "RSI N/A"
    score += rsi_pts
    breakdown["RSI"] = (rsi_label, rsi_pts, 5)

    # MACD bullish (5 pts)
    macd_pts = 5 if tech.get("macd_bullish") else 0
    score += macd_pts
    breakdown["MACD"] = (
        "Bullish (line > signal)" if tech.get("macd_bullish") else "Bearish/neutral",
        macd_pts, 5,
    )

    # Near 52-week high (5 pts)
    pct = tech.get("pct_from_52w_high", -100)
    if pct >= -10:
        h_pts = 5
    elif pct >= -25:
        h_pts = 2
    else:
        h_pts = 0
    score += h_pts
    breakdown["52W High Proximity"] = (f"{pct:.1f}% from 52W high", h_pts, 5)

    # ── FUNDAMENTAL (50 pts) ─────────────────────────────────────────────────

    # EPS growth (15 pts)
    eg = fund.get("earnings_growth")
    if eg is not None:
        if eg >= 0.25:
            eg_pts = 15
        elif eg >= 0.10:
            eg_pts = 8
        elif eg >= 0:
            eg_pts = 3
        else:
            eg_pts = 0
        eg_label = f"EPS growth {eg*100:.1f}%"
    else:
        eg_pts, eg_label = 5, "EPS growth N/A"  # benefit of doubt
    score += eg_pts
    breakdown["EPS Growth"] = (eg_label, eg_pts, 15)

    # Revenue growth (10 pts)
    rg = fund.get("revenue_growth")
    if rg is not None:
        if rg >= 0.15:
            rg_pts = 10
        elif rg >= 0.05:
            rg_pts = 5
        elif rg >= 0:
            rg_pts = 2
        else:
            rg_pts = 0
        rg_label = f"Revenue growth {rg*100:.1f}%"
    else:
        rg_pts, rg_label = 4, "Revenue growth N/A"
    score += rg_pts
    breakdown["Revenue Growth"] = (rg_label, rg_pts, 10)

    # P/E (10 pts) – use forward PE preferably
    pe = fund.get("forward_pe") or fund.get("trailing_pe")
    if pe is not None and pe > 0:
        if pe < 20:
            pe_pts, pe_label = 10, f"P/E {pe:.1f} – Value"
        elif pe < 30:
            pe_pts, pe_label = 7,  f"P/E {pe:.1f} – Fair"
        elif pe < 50:
            pe_pts, pe_label = 3,  f"P/E {pe:.1f} – Growth premium"
        elif pe < 80:
            pe_pts, pe_label = 1,  f"P/E {pe:.1f} – Expensive"
        else:
            pe_pts, pe_label = 0,  f"P/E {pe:.1f} – Overvalued"
    else:
        pe_pts, pe_label = 4, "P/E N/A"
    score += pe_pts
    breakdown["P/E Ratio"] = (pe_label, pe_pts, 10)

    # ROE (10 pts)
    roe = fund.get("roe")
    if roe is not None:
        if roe >= 0.20:
            roe_pts, roe_label = 10, f"ROE {roe*100:.1f}% – Excellent"
        elif roe >= 0.10:
            roe_pts, roe_label = 5,  f"ROE {roe*100:.1f}% – Good"
        elif roe >= 0:
            roe_pts, roe_label = 2,  f"ROE {roe*100:.1f}% – Weak"
        else:
            roe_pts, roe_label = 0,  f"ROE {roe*100:.1f}% – Negative"
    else:
        roe_pts, roe_label = 4, "ROE N/A"
    score += roe_pts
    breakdown["ROE"] = (roe_label, roe_pts, 10)

    # Profit margin (5 pts)
    pm = fund.get("profit_margins")
    if pm is not None:
        if pm >= 0.20:
            pm_pts, pm_label = 5, f"Net margin {pm*100:.1f}% – Strong"
        elif pm >= 0.10:
            pm_pts, pm_label = 3, f"Net margin {pm*100:.1f}% – Decent"
        elif pm >= 0:
            pm_pts, pm_label = 1, f"Net margin {pm*100:.1f}% – Thin"
        else:
            pm_pts, pm_label = 0, f"Net margin {pm*100:.1f}% – Loss-making"
    else:
        pm_pts, pm_label = 2, "Net margin N/A"
    score += pm_pts
    breakdown["Profit Margin"] = (pm_label, pm_pts, 5)

    # ── RATING ───────────────────────────────────────────────────────────────
    pct_score = score / 100 * 100
    if score >= 72:
        rating = "⭐ STRONG BUY"
    elif score >= 58:
        rating = "✅ BUY"
    elif score >= 42:
        rating = "👀 WATCH"
    else:
        rating = "❌ AVOID"

    return {
        "total_score": score,
        "percentage":  pct_score,
        "rating":      rating,
        "breakdown":   breakdown,
    }


def _stage_label(stage: int) -> str:
    labels = {1: "Stage 1 – Basing", 2: "Stage 2 – Advancing ✓",
              3: "Stage 3 – Topping", 4: "Stage 4 – Declining"}
    return labels.get(stage, "Stage unknown")


# ─────────────────────────────────────────────────────────────────────────────
# THREE-FILTER SINGLE-STOCK ASSESSMENT
# ─────────────────────────────────────────────────────────────────────────────

def assess_single_stock_filters(fund: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Evaluate a stock with a practical 3-filter overlay:
      1) Cash runway / self-funding profile
      2) Institutional support
      3) Revenue quality (growth + margin/earnings confirmation)

    Returns a score from 0-9 and a qualitative rating.
    """
    profile = profile or {}
    runway_levels = profile.get("runway_months", [6, 12, 24])
    inst_levels = profile.get("institutional_levels", [0.20, 0.35, 0.60])
    rev_levels = profile.get("revenue_growth_levels", [0.00, 0.10, 0.20])
    gross_margin_strong = profile.get("gross_margin_strong", 0.40)

    runway_months = _cash_runway_months(fund)
    inst = fund.get("held_percent_institutions")
    insider = fund.get("held_percent_insiders")
    rev_growth = fund.get("revenue_growth")
    eps_growth = fund.get("earnings_growth")
    gross_margin = fund.get("gross_margins")

    # Filter 1: Cash runway / survivability
    if runway_months is None:
        cash_pts, cash_label = 1, "Cash runway unavailable"
    elif runway_months >= runway_levels[2]:
        cash_pts, cash_label = 3, f"Cash runway {runway_months:.0f}m (strong)"
    elif runway_months >= runway_levels[1]:
        cash_pts, cash_label = 2, f"Cash runway {runway_months:.0f}m (acceptable)"
    elif runway_months >= runway_levels[0]:
        cash_pts, cash_label = 1, f"Cash runway {runway_months:.0f}m (tight)"
    else:
        cash_pts, cash_label = 0, f"Cash runway {runway_months:.0f}m (fragile)"

    # Filter 2: Institutional support
    if inst is None:
        inst_pts, inst_label = 1, "Institutional ownership unavailable"
    elif inst >= inst_levels[2] and (insider is None or insider < 0.30):
        inst_pts, inst_label = 3, f"Institutional ownership {inst*100:.0f}% (strong)"
    elif inst >= inst_levels[1]:
        inst_pts, inst_label = 2, f"Institutional ownership {inst*100:.0f}% (solid)"
    elif inst >= inst_levels[0]:
        inst_pts, inst_label = 1, f"Institutional ownership {inst*100:.0f}% (developing)"
    else:
        inst_pts, inst_label = 0, f"Institutional ownership {inst*100:.0f}% (weak)"

    # Filter 3: Revenue quality / inflection proxy
    if rev_growth is None:
        rev_pts, rev_label = 1, "Revenue quality unavailable"
    elif rev_growth >= rev_levels[2] and (eps_growth is None or eps_growth >= 0) and (gross_margin is None or gross_margin >= gross_margin_strong):
        rev_pts, rev_label = 3, f"Revenue quality strong ({rev_growth*100:.0f}% YoY)"
    elif rev_growth >= rev_levels[1] and (eps_growth is None or eps_growth >= 0):
        rev_pts, rev_label = 2, f"Revenue quality improving ({rev_growth*100:.0f}% YoY)"
    elif rev_growth >= rev_levels[0]:
        rev_pts, rev_label = 1, f"Revenue growth positive but low ({rev_growth*100:.0f}% YoY)"
    else:
        rev_pts, rev_label = 0, f"Revenue contraction ({rev_growth*100:.0f}% YoY)"

    total = cash_pts + inst_pts + rev_pts
    if total >= 7:
        rating = "PASS"
    elif total >= 4:
        rating = "WATCH"
    else:
        rating = "FAIL"

    return {
        "score": total,
        "max_score": 9,
        "rating": rating,
        "cash_runway_months": runway_months,
        "checks": {
            "cash_runway": {"points": cash_pts, "label": cash_label},
            "institutional_support": {"points": inst_pts, "label": inst_label},
            "revenue_quality": {"points": rev_pts, "label": rev_label},
        },
    }


def _cash_runway_months(fund: Dict[str, Any]) -> Optional[float]:
    """
    Estimate months of runway from total cash and annual cash-flow figures.
    Returns None when data is insufficient.
    """
    total_cash = fund.get("total_cash")
    if total_cash is None or total_cash <= 0:
        return None

    # Prefer free cash flow, then operating cash flow.
    # Positive annual cash flow implies self-funded operations.
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
