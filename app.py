"""
app.py – Streamlit frontend for the Felix Prehn Market Analysis System
Run with:   streamlit run app.py
"""

import base64
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Hashable, List, Optional, Set, Tuple, cast

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# ── must be the very first Streamlit call ─────────────────────────────────────
st.set_page_config(
    page_title="Felix Prehn Market Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Add workspace root to path so all local modules resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from run_analysis import AnalysisContext
from tools.market_data import fetch_ohlcv
from agents import (
    market_overview  as ag_market,
    sector_rotation  as ag_sector,
    stock_screener   as ag_screener,
    technical_analyst as ag_ta,
    fundamental_analyst as ag_fa,
    report_generator as ag_report,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _pct_style(val):
    """Pandas Styler map: green/red for percentage columns."""
    if pd.isna(val):
        return ""
    return "color: #2da44e; font-weight:bold" if val > 0 else "color: #cf222e; font-weight:bold"


def _ma_style(val):
    return "color: #2da44e; font-weight:bold" if val == "✓" else "color: #cf222e"


def _stage_style(val):
    colors = {
        "S2": "background-color:#0d2b0d; color:#2da44e; font-weight:bold",
        "S1": "background-color:#2b2b0d; color:#bf8700; font-weight:bold",
        "S3": "background-color:#2b1a0d; color:#cf4500",
        "S4": "background-color:#2b0d0d; color:#cf222e",
    }
    return colors.get(str(val), "")


def _score_style(val):
    try:
        v = int(val)
        if v >= 72: return "background-color:#0d2b0d; color:#2da44e; font-weight:bold"
        if v >= 58: return "background-color:#0d1a2b; color:#0969da; font-weight:bold"
        if v >= 42: return "background-color:#2b2b0d; color:#bf8700; font-weight:bold"
        return "background-color:#2b0d0d; color:#cf222e; font-weight:bold"
    except (TypeError, ValueError):
        return ""


def _trend_arrow(val: Optional[float], decimals: int = 1) -> str:
    """Return trend indicator based on displayed rounding to avoid tiny-value false positives."""
    if val is None or pd.isna(val):
        return "⚪"
    shown = round(float(val), decimals)
    if shown > 0:
        return "🟢"
    if shown < 0:
        return "🔴"
    return "⚪"


def _parse_tickers(raw: str) -> List[str]:
    """Parse ticker input from comma/space/newline separated text and normalize."""
    if not raw:
        return []
    tokens = re.split(r"[\s,;]+", raw.strip())
    out: List[str] = []
    seen = set()
    for tok in tokens:
        t = tok.strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def score_badge_md(score: int, rating: str) -> str:
    colors = {
        "STRONG BUY": "🟢",
        "BUY":        "🔵",
        "WATCH":      "🟡",
        "AVOID":      "🔴",
    }
    key = rating.replace("⭐ ","").replace("✅ ","").replace("👀 ","").replace("❌ ","")
    icon = colors.get(key, "⚪")
    return f"{icon} **{score}/100** – {rating}"


def phase_to_emoji(phase: str) -> str:
    phase = phase or ""
    if "BULL" in phase:    return "🟢"
    if "UPTREND" in phase: return "🟢"
    if "CORR" in phase:    return "🟡"
    if "BEAR" in phase:    return "🔴"
    return "⚪"


def _normalize_sector_name(name: str) -> str:
    """Normalize sector labels across ETFs and stock metadata for matching."""
    if not name:
        return "Unknown"

    s = str(name).strip().lower()
    aliases = {
        "eu technology": "Technology",
        "technology": "Technology",
        "eu healthcare": "Healthcare",
        "healthcare": "Healthcare",
        "health care": "Healthcare",
        "eu banks": "Financials",
        "eu insurance": "Financials",
        "financial services": "Financials",
        "financial": "Financials",
        "financials": "Financials",
        "eu oil & gas": "Energy",
        "energy": "Energy",
        "oil & gas": "Energy",
        "eu industrials": "Industrials",
        "industrials": "Industrials",
        "industrial": "Industrials",
        "consumer cyclical": "Consumer Discretionary",
        "consumer discretionary": "Consumer Discretionary",
        "eu consumer": "Consumer",
        "consumer staples": "Consumer Staples",
        "basic materials": "Materials",
        "materials": "Materials",
        "utilities": "Utilities",
        "real estate": "Real Estate",
        "communication": "Communication",
        "communication services": "Communication",
    }

    if s in aliases:
        return aliases[s]

    for key, canonical in aliases.items():
        if key in s:
            return canonical

    return str(name).strip()


def _classify_flow_state(momentum_score: Optional[float], ret_1w: Optional[float], ret_1m: Optional[float]) -> str:
    """Classify whether a sector is attracting or losing liquidity."""
    ms = 0.0 if momentum_score is None or pd.isna(momentum_score) else float(momentum_score)
    r1w = None if ret_1w is None or pd.isna(ret_1w) else float(ret_1w)
    r1m = None if ret_1m is None or pd.isna(ret_1m) else float(ret_1m)
    accel = None
    if r1w is not None and r1m is not None:
        accel = r1w - (r1m / 4.0)

    if ms > 0 and (r1w is not None and r1w > 0):
        if accel is not None and accel > 0.30:
            return "Inflow Accelerating"
        return "Inflow"
    if ms > 0:
        return "Inflow Cooling"
    if ms < 0 and (r1w is not None and r1w < 0):
        if accel is not None and accel < -0.30:
            return "Outflow Accelerating"
        return "Outflow"
    return "Neutral"


def _flow_state_style(val: object) -> str:
    sval = str(val)
    palette = {
        "Inflow Accelerating": "background-color:#0d2b0d;color:#2da44e;font-weight:bold",
        "Inflow": "color:#2da44e;font-weight:bold",
        "Inflow Cooling": "color:#bf8700;font-weight:bold",
        "Outflow Accelerating": "background-color:#2b0d0d;color:#cf222e;font-weight:bold",
        "Outflow": "color:#cf222e;font-weight:bold",
        "Neutral": "color:#94a3b8",
    }
    return palette.get(sval, "")


def _build_sector_flow_table(ctx: AnalysisContext) -> pd.DataFrame:
    rows = []
    for region, rank_df in (("US", ctx.us_sector_rank), ("EU", ctx.eu_sector_rank)):
        if rank_df is None or rank_df.empty:
            continue
        for sector_name, row in rank_df.iterrows():
            r1w = row.get("1wk")
            r1m = row.get("1mo")
            accel = None
            if r1w is not None and not pd.isna(r1w) and r1m is not None and not pd.isna(r1m):
                accel = round(float(r1w) - (float(r1m) / 4.0), 2)

            rows.append({
                "Region": region,
                "Sector": sector_name,
                "Canonical": _normalize_sector_name(str(sector_name)),
                "1W%": r1w,
                "1M%": r1m,
                "3M%": row.get("3mo"),
                "6M%": row.get("6mo"),
                "1Y%": row.get("1y"),
                "Momentum": row.get("momentum_score"),
                "Flow Delta": accel,
                "Flow State": _classify_flow_state(row.get("momentum_score"), r1w, r1m),
            })

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out = out.sort_values(["Momentum", "1W%"], ascending=False, na_position="last").reset_index(drop=True)
    return out


def _build_liquidity_winners(
    stocks: List[dict],
    flow_df: pd.DataFrame,
    top_n: int = 20,
    early_bias_mode: str = "Balanced",
) -> pd.DataFrame:
    """Rank screened stocks by liquidity inflow + upside-left profile.

    Intention: prefer names attracting fresh liquidity that are not already
    overly extended in price, while still allowing true leaders to rank.
    """
    if not stocks:
        return pd.DataFrame()

    sector_mom = {}
    sector_flow = {}
    top_inflow = set()
    if flow_df is not None and not flow_df.empty:
        for canonical, grp in flow_df.groupby("Canonical"):
            sector_mom[canonical] = float(grp["Momentum"].max()) if not grp["Momentum"].isna().all() else 0.0
            preferred = grp.sort_values("Momentum", ascending=False).iloc[0]
            sector_flow[canonical] = preferred.get("Flow State", "Neutral")

        top_inflow = set(
            flow_df.loc[flow_df["Momentum"] > 0]
            .sort_values("Momentum", ascending=False)
            .head(5)["Canonical"]
            .tolist()
        )

    bias_presets = {
        "Conservative": {
            "potential_mult": 0.85,
            "extension_mult": 1.25,
            "flow_mult": 0.95,
            "trend_mult": 0.90,
        },
        "Balanced": {
            "potential_mult": 1.00,
            "extension_mult": 1.00,
            "flow_mult": 1.00,
            "trend_mult": 1.00,
        },
        "Aggressive": {
            "potential_mult": 1.30,
            "extension_mult": 0.75,
            "flow_mult": 1.10,
            "trend_mult": 1.15,
        },
    }
    bias = bias_presets.get(early_bias_mode, bias_presets["Balanced"])

    rows = []
    for s in stocks:
        canonical = _normalize_sector_name(s.get("sector") or "")
        sec_mom = sector_mom.get(canonical, 0.0)
        flow_state = sector_flow.get(canonical, "Neutral")

        prehn = float(s.get("score") or 0.0)
        rs = float(s.get("rs_bench") or 0.0)
        ret_3m = float(s.get("ret_3m") or 0.0)
        ret_1m = float(s.get("ret_1m") or 0.0)
        stage = int(s.get("stage") or 0)
        rsi = float(s.get("rsi") or 0.0)
        pct_52h = s.get("pct_52h")
        pct_52h = float(pct_52h) if pct_52h is not None and not pd.isna(pct_52h) else None

        volume_spike = _recent_volume_spike(s.get("_df"))

        # Stage 1 and early Stage 2 get preference for "more upside left".
        stage_bonus = 8 if stage == 1 else 6 if stage == 2 else -5
        sector_bonus = 10 if canonical in top_inflow else 0

        flow_bonus = 0
        if flow_state == "Inflow Accelerating":
            flow_bonus = 8
        elif flow_state == "Inflow":
            flow_bonus = 5
        elif flow_state == "Inflow Cooling":
            flow_bonus = 2
        flow_bonus *= bias["flow_mult"]

        # Potential bonuses reward constructive, not-yet-overextended trajectories.
        potential_bonus = 0.0
        if -2.0 <= ret_1m <= 12.0:
            potential_bonus += 6.0
        if 0.0 <= ret_3m <= 28.0:
            potential_bonus += 7.0
        if pct_52h is not None and -35.0 <= pct_52h <= -8.0:
            potential_bonus += 6.0
        if volume_spike:
            potential_bonus += 4.0
        potential_bonus *= bias["potential_mult"]

        # Extension penalty tempers rankings for names that may already be crowded.
        extension_penalty = 0.0
        if ret_1m > 15.0:
            extension_penalty += min(15.0, (ret_1m - 15.0) * 0.8)
        if ret_3m > 45.0:
            extension_penalty += min(20.0, (ret_3m - 45.0) * 0.5)
        if rsi > 72.0:
            extension_penalty += min(10.0, (rsi - 72.0) * 1.2)
        if pct_52h is not None and pct_52h > -5.0:
            extension_penalty += 5.0
        extension_penalty *= bias["extension_mult"]

        liquidity_score = round(
            max(0.0, min(
                100.0,
                prehn * 0.46
                + sec_mom * 1.75
                + max(rs, 0.0) * (0.20 * bias["trend_mult"])
                + stage_bonus
                + sector_bonus
                + flow_bonus
                + potential_bonus
                - extension_penalty,
            )),
            1,
        )

        reasons = []
        if canonical in top_inflow:
            reasons.append("inflow sector")
        if flow_state in ("Inflow Accelerating", "Inflow"):
            reasons.append(flow_state.lower())
        if stage == 2:
            reasons.append("Stage 2")
        elif stage == 1:
            reasons.append("early base")
        if rs > 0:
            reasons.append("RS > 0")
        if ret_1m > 0:
            reasons.append("1M momentum")
        if 0 < ret_3m <= 28:
            reasons.append("3M momentum")
        if volume_spike:
            reasons.append("fresh volume")
        if pct_52h is not None and -35 <= pct_52h <= -8:
            reasons.append("upside left vs 52W high")
        if prehn >= 72:
            reasons.append("strong quality")
        why_text = " + ".join(reasons[:4]) if reasons else "watchlist candidate"

        risk_notes = []
        if extension_penalty >= 8:
            risk_notes.append("extended")
        if stage in (3, 4):
            risk_notes.append("late stage")
        if rs <= 0:
            risk_notes.append("weak RS")
        risk_text = " | ".join(risk_notes[:2]) if risk_notes else "balanced setup"

        rows.append({
            "Ticker": s.get("ticker"),
            "Name": (s.get("name") or "")[:30],
            "Why": why_text,
            "Risk": risk_text,
            "Sector": s.get("sector") or "",
            "Flow Sector": canonical,
            "Flow State": flow_state,
            "Prehn": prehn,
            "Liquidity": liquidity_score,
            "Stage": f"S{stage if stage else '?'}",
            "1M%": s.get("ret_1m"),
            "3M%": s.get("ret_3m"),
            "RS%": s.get("rs_bench"),
            "Inflow Match": "Yes" if canonical in top_inflow else "No",
            "Rating": (s.get("rating") or "").replace("⭐ ", "").replace("✅ ", "").replace("👀 ", "").replace("❌ ", ""),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["Liquidity", "Prehn"], ascending=False).head(top_n).reset_index(drop=True)


def _flow_context_maps(flow_df: pd.DataFrame) -> Tuple[Set[str], Dict[str, str]]:
    """Return top-inflow sectors and latest flow-state per canonical sector."""
    top_inflow: Set[str] = set()
    flow_state_by_sector: Dict[str, str] = {}
    if flow_df is None or flow_df.empty:
        return top_inflow, flow_state_by_sector

    top_inflow = set(
        flow_df.loc[flow_df["Momentum"] > 0]
        .sort_values("Momentum", ascending=False)
        .head(5)["Canonical"]
        .tolist()
    )

    for canonical, grp in flow_df.groupby("Canonical"):
        row = grp.sort_values("Momentum", ascending=False).iloc[0]
        flow_state_by_sector[str(canonical)] = str(row.get("Flow State") or "Neutral")

    return top_inflow, flow_state_by_sector


def _recent_volume_spike(df: Optional[pd.DataFrame], lookback: int = 20, multiple: float = 3.0) -> bool:
    """Proxy for institutional attention used by several strategy playbooks."""
    if df is None or df.empty or len(df) < lookback + 5:
        return False
    if "Volume" not in df.columns or "Close" not in df.columns:
        return False

    vol = pd.to_numeric(df["Volume"], errors="coerce")
    close = pd.to_numeric(df["Close"], errors="coerce")
    if vol.isna().all() or close.isna().all():
        return False

    recent = vol.iloc[-(lookback + 1):-1]
    baseline = float(recent.mean()) if not recent.empty else 0.0
    if baseline <= 0:
        return False

    latest_spike = float(vol.iloc[-1]) >= baseline * multiple
    up_day = float(close.iloc[-1]) >= float(close.iloc[-2])
    return bool(latest_spike and up_day)


def _ma_trend_and_position(df: Optional[pd.DataFrame]) -> Tuple[bool, bool]:
    """Return (ma50_uptrend, price_above_ma50_and_ma150)."""
    if df is None or df.empty or "Close" not in df.columns:
        return False, False

    close = pd.to_numeric(df["Close"], errors="coerce")
    ma50 = pd.to_numeric(df["MA50"], errors="coerce") if "MA50" in df.columns else close.rolling(50).mean()
    ma150 = pd.to_numeric(df["MA150"], errors="coerce") if "MA150" in df.columns else close.rolling(150).mean()

    if len(close) < 170:
        return False, False

    ma50_now = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else None
    ma50_prev = float(ma50.iloc[-20]) if not pd.isna(ma50.iloc[-20]) else None
    close_now = float(close.iloc[-1]) if not pd.isna(close.iloc[-1]) else None
    ma150_now = float(ma150.iloc[-1]) if not pd.isna(ma150.iloc[-1]) else None

    ma50_up = bool(ma50_now is not None and ma50_prev is not None and ma50_now > ma50_prev)
    above_ma = bool(
        close_now is not None
        and ma50_now is not None
        and ma150_now is not None
        and close_now > ma50_now
        and close_now > ma150_now
    )
    return ma50_up, above_ma


def _ma50_up_and_price_above_ma50(df: Optional[pd.DataFrame]) -> Tuple[bool, bool]:
    """Return (ma50_uptrend, price_above_ma50)."""
    if df is None or df.empty or "Close" not in df.columns:
        return False, False

    close = pd.to_numeric(df["Close"], errors="coerce")
    ma50 = pd.to_numeric(df["MA50"], errors="coerce") if "MA50" in df.columns else close.rolling(50).mean()
    if len(close) < 80:
        return False, False

    ma50_now = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else None
    ma50_prev = float(ma50.iloc[-20]) if not pd.isna(ma50.iloc[-20]) else None
    close_now = float(close.iloc[-1]) if not pd.isna(close.iloc[-1]) else None

    ma50_up = bool(ma50_now is not None and ma50_prev is not None and ma50_now > ma50_prev)
    above_ma50 = bool(close_now is not None and ma50_now is not None and close_now > ma50_now)
    return ma50_up, above_ma50


def _region_country_universe(scope: str) -> List[str]:
    """Automatic base universe by region/country scope for hierarchical analysis."""
    key = (scope or "US").strip().lower()

    if key == "us":
        base = config.get_universe("largecap") + config.get_universe("midcap") + config.get_universe("smallcap")
    elif key == "germany":
        base = config.DAX_40 + config.MDAX_SELECTED
    elif key == "uk":
        base = config.FTSE_100_SELECTED
    elif key == "switzerland":
        base = config.SWISS_SELECTED
    elif key == "europe":
        base = config.DAX_40 + config.MDAX_SELECTED + config.EURO_STOXX_EX_DE + config.SWISS_SELECTED + config.FTSE_100_SELECTED
    else:  # global
        base = config.get_universe("broad")

    return list(dict.fromkeys(base))


def _hierarchical_felix_selection(
    ctx: AnalysisContext,
    early_bias_mode: str,
    industry_filter_mode: str,
) -> Tuple[List[dict], Dict[str, object]]:
    """Auto process: winning sectors -> winning industries -> Felix-aligned stocks."""
    all_scored = list(getattr(ctx, "all_scored_stocks", []) or [])
    if not all_scored:
        return [], {"winning_sectors": [], "winning_industries": []}

    flow_df = _build_sector_flow_table(ctx)
    top_inflow, flow_state_by_sector = _flow_context_maps(flow_df)

    # 1) Winning sectors: require flow support + MA50 up + price above MA50 on sector ETF.
    sector_etfs = {}
    sector_etfs.update(getattr(config, "US_SECTOR_ETFS", {}))
    sector_etfs.update(getattr(config, "EU_SECTOR_ETFS", {}))

    winning_sectors: Set[str] = set()
    for sector_name, etf in sector_etfs.items():
        canonical = _normalize_sector_name(sector_name)
        flow_state = flow_state_by_sector.get(canonical, "Neutral")
        flow_ok = canonical in top_inflow or flow_state in ("Inflow", "Inflow Accelerating")
        if not flow_ok:
            continue
        etf_df = fetch_ohlcv(etf, period="1y")
        ma50_up, above_ma50 = _ma50_up_and_price_above_ma50(etf_df)
        if ma50_up and above_ma50:
            winning_sectors.add(canonical)

    # 2) Winning industries inside winning sectors.
    industry_stats: Dict[str, Dict[str, object]] = {}
    for s in all_scored:
        canonical = _normalize_sector_name(s.get("sector") or "")
        if canonical not in winning_sectors:
            continue
        ind = (s.get("industry") or "").strip() or "Unclassified"
        ma50_up, above_ma50 = _ma50_up_and_price_above_ma50(s.get("_df"))
        passed = bool(ma50_up and above_ma50)

        rec = industry_stats.setdefault(ind, {"sector": canonical, "count": 0, "pass": 0})
        current_count = rec.get("count", 0)
        current_pass = rec.get("pass", 0)
        rec["count"] = int(cast(int, current_count)) + 1
        rec["pass"] = int(cast(int, current_pass)) + (1 if passed else 0)

    winning_industries: Set[str] = set()
    for ind, rec in industry_stats.items():
        count = int(cast(int, rec.get("count", 0)))
        passed = int(cast(int, rec.get("pass", 0)))
        ratio = (passed / count) if count else 0.0
        if count < 2:
            continue
        if industry_filter_mode == "All pass":
            if passed == count:
                winning_industries.add(ind)
        else:  # Majority pass
            if ratio >= 0.5:
                winning_industries.add(ind)

    # 3) Final stocks: all stocks in winning industries, then ranked by Felix fit and liquidity score.
    felix_rows = []
    liquidity_rows = _build_liquidity_winners(all_scored, flow_df, top_n=max(len(all_scored), 50), early_bias_mode=early_bias_mode)
    liq_map = {str(r.get("Ticker")): float(r.get("Liquidity") or 0.0) for _, r in liquidity_rows.iterrows()} if not liquidity_rows.empty else {}

    for s in all_scored:
        ind = (s.get("industry") or "").strip() or "Unclassified"
        if ind not in winning_industries:
            continue
        f_fit, f_match, f_missing, f_checks = _felix_method_signals(s, top_inflow, flow_state_by_sector)
        felix_rows.append({
            "ticker": s.get("ticker"),
            "felix_fit": f_fit,
            "felix_pass": sum(1 for v in f_checks.values() if v),
            "liquidity": liq_map.get(str(s.get("ticker")), 0.0),
            "matched": f_match,
            "missing": f_missing,
            "stock": s,
        })

    felix_rows.sort(key=lambda x: (x["felix_fit"], x["liquidity"], float(x["stock"].get("score") or 0.0)), reverse=True)

    selected: List[dict] = []
    for row in felix_rows:
        stx = dict(row["stock"])
        stx["felix_fit"] = row["felix_fit"]
        stx["felix_pass"] = row["felix_pass"]
        stx["felix_matched"] = row["matched"]
        stx["felix_missing"] = row["missing"]
        stx["liquidity_score"] = row["liquidity"]
        selected.append(stx)

    meta = {
        "winning_sectors": sorted(winning_sectors),
        "winning_industries": sorted(winning_industries),
        "industry_count": len(winning_industries),
        "sector_count": len(winning_sectors),
    }
    return selected, meta


def _heartbeat_pattern_signal(s: dict) -> bool:
    """Approximate heartbeat/consolidation phase from available technical context."""
    stage = int(s.get("stage") or 0)
    df = s.get("_df")
    if df is None or df.empty or "Close" not in df.columns:
        return stage == 1

    close = pd.to_numeric(df["Close"], errors="coerce")
    if len(close) < 70:
        return stage == 1

    c60 = close.tail(60)
    c20 = close.tail(20)
    hi60, lo60 = float(c60.max()), float(c60.min())
    hi20, lo20 = float(c20.max()), float(c20.min())
    if lo60 <= 0 or lo20 <= 0:
        return stage == 1

    range60 = (hi60 - lo60) / lo60
    range20 = (hi20 - lo20) / lo20

    # Stage 1 is preferred; early stage 2 with still-tight ranges is acceptable.
    if stage == 1:
        return True
    if stage == 2 and range20 <= 0.18 and range60 <= 0.38:
        return True
    return False


def _felix_method_signals(
    s: dict,
    top_inflow: Set[str],
    flow_state_by_sector: Dict[str, str],
) -> Tuple[float, str, str, Dict[str, bool]]:
    """Felix focus: follow money + winning stock pattern checks."""
    canonical = _normalize_sector_name(s.get("sector") or "")
    flow_state = flow_state_by_sector.get(canonical, "Neutral")

    liquidity_in = bool(canonical in top_inflow or flow_state in ("Inflow", "Inflow Accelerating"))
    heartbeat = _heartbeat_pattern_signal(s)
    ma50_up, above_ma50_ma150 = _ma_trend_and_position(s.get("_df"))
    vol_spike = _recent_volume_spike(s.get("_df"))

    checks = {
        "Liquidity Inflow": liquidity_in,
        "Heartbeat Pattern": heartbeat,
        "MA50 Trending Up": ma50_up,
        "Price > MA50 & MA150": above_ma50_ma150,
        "Recent Volume Spike": vol_spike,
    }
    passed = sum(1 for v in checks.values() if v)
    fit = round((passed / len(checks)) * 100.0, 1)

    matched = [k for k, v in checks.items() if v]
    missing = [k for k, v in checks.items() if not v]
    matched_text = " + ".join(matched[:4]) if matched else "No Felix criteria matched"
    risk_text = " | ".join(missing[:3]) if missing else "All Felix criteria matched"
    return fit, matched_text, risk_text, checks


STRATEGY_LENS_OPTIONS = {
    "None": "No strategy lens (show default model ranking)",
    "01 Beginner Long-Term Investor": "Quality-first compounding and broad risk control",
    "02 DCA Accumulator": "Recurring accumulation with strict thesis protection",
    "03 90-Day Systematic Trader": "Triple-confirmation process with hard risk rules",
    "04 Institutional Money-Flow Trader": "Sector-first flow tracking and leader selection",
    "05 Wall Street Protocol Technical Trader": "4-pillar technical confirmation before entry",
    "06 Sector Rotation Macro Investor": "Rotate across top momentum sectors via regime",
    "07 Market Collision Wave Investor": "Follow macro causal-wave sector transitions",
    "08 AI Infrastructure Investor": "Picks-and-shovels AI infrastructure leadership",
    "09 AI Power-Stack Investor": "Layered AI exposure with quality/risk balancing",
    "10 Space Catalyst Trader": "Catalyst + volume + structure confirmation",
    "11 Quality Runway Growth Investor": "Cash runway + sponsorship + growth inflection",
    "12 New-Fed Gold/Silver/Bitcoin Macro Trader": "Policy-sensitive macro allocation discipline",
    "13 Deep-Research 10x Investor": "Rare asymmetric setups with strict quality gates",
}


def _strategy_lens_evaluation(
    s: dict,
    top_inflow: Set[str],
    flow_state_by_sector: Dict[str, str],
    lens: str,
) -> Tuple[float, str, str]:
    """Return fit score (0-100), matched pattern labels, and risk flags for selected lens."""
    if lens == "None":
        return 0.0, "", ""

    stage = int(s.get("stage") or 0)
    canonical = _normalize_sector_name(s.get("sector") or "")
    flow_state = flow_state_by_sector.get(canonical, "Neutral")
    rs = float(s.get("rs_bench") or 0.0)
    ret_1m = float(s.get("ret_1m") or 0.0)
    ret_3m = float(s.get("ret_3m") or 0.0)
    prehn = float(s.get("score") or 0.0)
    pe = s.get("pe")
    eps = s.get("eps_growth")
    industry = (s.get("industry") or "").lower()
    ticker = (s.get("ticker") or "").upper()

    signals = {
        "stage2": stage == 2,
        "stage1or2": stage in (1, 2),
        "inflow": canonical in top_inflow,
        "flow_positive": flow_state in ("Inflow", "Inflow Accelerating"),
        "rs_positive": rs > 0,
        "mom_1m": ret_1m > 0,
        "mom_3m": ret_3m > 0,
        "quality72": prehn >= 72,
        "quality58": prehn >= 58,
        "eps_positive": (eps is not None) and (float(eps) > 0),
        "pe_reasonable": (pe is not None) and (0 < float(pe) <= 80),
        "volume_spike": _recent_volume_spike(s.get("_df")),
        "ai_exposure": canonical in {"Technology", "Industrials", "Energy", "Communication"},
        "space_exposure": ("aerospace" in industry) or ("defense" in industry) or ticker in {"RKLB", "LUNR", "ASTS", "SPCE"},
        "macro_hedge_proxy": canonical in {"Materials", "Energy"} or ticker in {"GLD", "SLV", "GDX", "GDXJ", "SIL", "BITO", "BTC-USD"},
    }

    rules_by_lens = {
        "01 Beginner Long-Term Investor": ["quality58", "stage1or2", "pe_reasonable"],
        "02 DCA Accumulator": ["quality58", "stage1or2", "eps_positive"],
        "03 90-Day Systematic Trader": ["volume_spike", "stage1or2", "rs_positive", "eps_positive"],
        "04 Institutional Money-Flow Trader": ["inflow", "flow_positive", "rs_positive", "stage1or2"],
        "05 Wall Street Protocol Technical Trader": ["stage1or2", "rs_positive", "volume_spike", "mom_3m"],
        "06 Sector Rotation Macro Investor": ["inflow", "flow_positive", "mom_1m", "mom_3m"],
        "07 Market Collision Wave Investor": ["flow_positive", "mom_1m", "mom_3m", "rs_positive"],
        "08 AI Infrastructure Investor": ["ai_exposure", "quality58", "rs_positive", "mom_3m"],
        "09 AI Power-Stack Investor": ["ai_exposure", "quality58", "mom_1m", "eps_positive"],
        "10 Space Catalyst Trader": ["space_exposure", "volume_spike", "stage1or2", "eps_positive"],
        "11 Quality Runway Growth Investor": ["quality58", "eps_positive", "pe_reasonable", "rs_positive"],
        "12 New-Fed Gold/Silver/Bitcoin Macro Trader": ["macro_hedge_proxy", "stage1or2", "rs_positive", "mom_1m"],
        "13 Deep-Research 10x Investor": ["stage1or2", "eps_positive", "rs_positive", "mom_3m", "quality58"],
    }

    matched_labels = {
        "stage2": "Stage 2",
        "stage1or2": "Stage 1/2 structure",
        "inflow": "Top inflow sector",
        "flow_positive": "Positive sector flow",
        "rs_positive": "RS > 0",
        "mom_1m": "1M momentum",
        "mom_3m": "3M momentum",
        "quality72": "Strong quality score",
        "quality58": "Quality score",
        "eps_positive": "EPS growth positive",
        "pe_reasonable": "P/E in model range",
        "volume_spike": "Volume spike",
        "ai_exposure": "AI-exposed sector",
        "space_exposure": "Space/aerospace exposure",
        "macro_hedge_proxy": "Macro-hedge proxy",
    }

    required = rules_by_lens.get(lens, [])
    if not required:
        return 0.0, "", ""

    matched = [k for k in required if signals.get(k)]
    fit = round((len(matched) / len(required)) * 100.0, 1)

    matched_text = " + ".join(matched_labels[k] for k in matched[:4]) or "No primary pattern match"

    risk_flags = []
    if stage in (3, 4):
        risk_flags.append("Late/declining stage")
    if rs <= 0:
        risk_flags.append("Negative RS")
    if not signals["flow_positive"] and lens in {
        "04 Institutional Money-Flow Trader",
        "06 Sector Rotation Macro Investor",
        "07 Market Collision Wave Investor",
    }:
        risk_flags.append("Weak sector flow")
    if lens in {"03 90-Day Systematic Trader", "05 Wall Street Protocol Technical Trader", "10 Space Catalyst Trader"} and not signals["volume_spike"]:
        risk_flags.append("No volume confirmation")
    if lens in {"11 Quality Runway Growth Investor", "13 Deep-Research 10x Investor"} and not signals["eps_positive"]:
        risk_flags.append("No EPS inflection")

    risk_text = " | ".join(risk_flags[:3]) or "No major rule conflict"
    return fit, matched_text, risk_text


def _liquidity_confidence(flow_df: pd.DataFrame, winners_df: pd.DataFrame) -> tuple[int, str]:
    """Return confidence score (0-100) and label for current liquidity regime."""
    if flow_df is None or flow_df.empty:
        return 0, "No Data"

    positive = int((flow_df["Momentum"] > 0).sum()) if "Momentum" in flow_df.columns else 0
    total = max(len(flow_df), 1)
    breadth = positive / total

    accel_source = flow_df["Flow Delta"] if "Flow Delta" in flow_df.columns else pd.Series(dtype=float)
    accel = pd.to_numeric(accel_source, errors="coerce")
    accel_up = int((accel > 0).sum()) if accel is not None else 0
    accel_ratio = accel_up / total

    winner_quality = 0.0
    if winners_df is not None and not winners_df.empty:
        top_n = winners_df.head(10)
        winner_quality = float(top_n["Liquidity"].mean()) / 100.0

    score = int(round(min(1.0, max(0.0, 0.45 * breadth + 0.20 * accel_ratio + 0.35 * winner_quality)) * 100))

    if score >= 75:
        label = "High"
    elif score >= 55:
        label = "Medium"
    elif score >= 35:
        label = "Low"
    else:
        label = "Very Low"

    return score, label


def _mini_chart(df: Optional[pd.DataFrame], days: int = 90) -> Optional[bytes]:
    """
    Compact sparkline with separate panels for price and volume.
    Green line when price is up over the period, red when down.
    Returns raw PNG bytes for st.image(), or None if insufficient data.
    """
    if df is None or df.empty or len(df) < 10:
        return None

    plot_df = df.tail(days).copy()
    close   = plot_df["Close"]

    # Compute MA50 against the full series if column missing
    if "MA50" not in plot_df.columns:
        plot_df["MA50"] = df["Close"].rolling(50).mean().tail(days).values

    fig = plt.figure(figsize=(3.2, 1.45), facecolor="#1e1e2e")
    gs = fig.add_gridspec(2, 1, height_ratios=[3.4, 1.2], hspace=0.02)
    ax = fig.add_subplot(gs[0, 0])
    ax_vol = fig.add_subplot(gs[1, 0], sharex=ax)
    ax.set_facecolor("#1e1e2e")
    ax_vol.set_facecolor("#1e1e2e")

    dates     = plot_df.index
    start_px = float(close.iloc[0])
    end_px   = float(close.iloc[-1])
    net_pct  = ((end_px / start_px) - 1.0) * 100.0 if start_px else 0.0
    shown_pct = round(net_pct, 1)
    line_clr = "#a6e3a1" if shown_pct > 0 else "#f38ba8" if shown_pct < 0 else "#94a3b8"

    vol = pd.to_numeric(plot_df["Volume"], errors="coerce") if "Volume" in plot_df.columns else None
    if vol is not None and not vol.isna().all() and float(vol.max()) > 0:
        vol = vol.fillna(0)
        day_dir = close.diff().fillna(0)
        vol_colors = ["#a6e3a1" if d >= 0 else "#f38ba8" for d in day_dir]
        ax_vol.bar(dates, vol, width=1.0, color=vol_colors, alpha=0.85, zorder=2)
        ax_vol.set_ylim(0, float(vol.max()) * 1.12)
        ax_vol.axis("off")
    else:
        ax_vol.axis("off")

    ax.plot(dates, close, color=line_clr, lw=1.4, zorder=3)
    ax.fill_between(dates, close, float(close.min()) * 0.999,
                    alpha=0.13, color=line_clr, zorder=2)

    ma50 = plot_df["MA50"]
    if not ma50.isna().all():
        ax.plot(dates, ma50, color="#f9e2af", lw=0.85,
                linestyle="--", alpha=0.9, zorder=4)

    ax.set_xlim(dates[0], dates[-1])
    ax.axis("off")
    plt.tight_layout(pad=0.1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=95, bbox_inches="tight",
                facecolor="#1e1e2e", edgecolor="none")
    buf.seek(0)
    raw = buf.read()
    plt.close(fig)
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 Market Analyzer")
    st.caption("Felix Prehn Methodology")
    st.divider()

    saved_watchlist = config.get_custom_watchlist()

    region_scope = st.selectbox(
        "Region / Country Scope",
        ["US", "Germany", "UK", "Switzerland", "Europe", "Global"],
        index=0,
        help="Automatic hierarchical process starts from this scope: sector -> industry -> Felix stock selection.",
    )

    watchlist_input = st.text_area(
        "My Saved Watchlist",
        value="\n".join(saved_watchlist),
        height=120,
        placeholder="e.g. HIMS, ASML.AS, IFX.DE",
        help="These tickers are persisted and used whenever universe=custom.",
    )

    if st.button("💾 Save Watchlist", width="stretch"):
        try:
            saved = config.save_custom_watchlist(_parse_tickers(watchlist_input))
            st.success(f"Saved {len(saved)} watchlist tickers")
        except Exception as exc:
            st.error(f"Could not save watchlist: {exc}")

    custom_input = st.text_area(
        "Run-only Extra Tickers",
        value="",
        height=110,
        placeholder="e.g. HIMS, ASML.AS, IFX.DE",
        help="Use commas, spaces, or new lines. Appended to the selected universe for this run only.",
    )

    strategy_lens = st.selectbox(
        "Strategy Lens",
        options=list(STRATEGY_LENS_OPTIONS.keys()),
        index=0,
        help="Select an investor/trader style from assets/skills and rank opportunities by that rule set.",
    )
    st.caption(f"Lens focus: {STRATEGY_LENS_OPTIONS.get(strategy_lens, '')}")

    early_opportunity_bias = st.select_slider(
        "Early Opportunity Bias",
        options=["Conservative", "Balanced", "Aggressive"],
        value="Balanced",
        help=(
            "Controls how strongly Liquidity Shift prioritizes stocks with room to run over already-extended winners. "
            "Conservative = stronger penalty for extension; Aggressive = stronger preference for early inflow setups."
        ),
    )

    felix_focus_mode = st.toggle(
        "Felix Focus Mode",
        value=True,
        help=(
            "Prioritize candidates that match the Felix method: follow liquidity flow + heartbeat consolidation + "
            "MA trend/position + recent volume spike."
        ),
    )

    industry_filter_mode = st.selectbox(
        "Winning Industry Filter",
        options=["Majority pass", "All pass"],
        index=0,
        help=(
            "Majority pass: industry qualifies if >=50% of evaluated stocks pass sector/industry Felix MA50 criteria. "
            "All pass: industry qualifies only if every evaluated stock passes."
        ),
    )

    max_detail = st.slider(
        "Stocks to deep-analyse",
        min_value=5,
        max_value=500,
        value=min(max(config.MAX_DETAIL_STOCKS, 5), 500),
        help="Top N candidates get full TA chart + FA breakdown",
    )

    st.divider()
    run_btn = st.button("🚀 Run Analysis", type="primary", width="stretch")

    if "run_time" in st.session_state:
        st.success(f"Last run: {st.session_state.run_time}")
        _ctx = st.session_state.ctx
        if getattr(_ctx, "report_path", None) and os.path.exists(_ctx.report_path):
            with open(_ctx.report_path, "rb") as _f:
                st.download_button(
                    "📥 Download HTML Report",
                    data=_f.read(),
                    file_name=os.path.basename(_ctx.report_path),
                    mime="text/html",
                    width="stretch",
                )

    st.divider()
    st.caption("Data: Yahoo Finance  \nNot financial advice.")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if run_btn:
    custom_tickers = _parse_tickers(custom_input)
    saved_watchlist = config.get_custom_watchlist()

    base_tickers = _region_country_universe(region_scope)
    all_tickers  = list(dict.fromkeys(base_tickers + custom_tickers))

    # Propagate UI depth to both screener and deep-analysis stages.
    depth = max(1, min(int(max_detail), 500))
    config.SCREENING["max_candidates"] = depth
    config.MAX_DETAIL_STOCKS = depth

    ctx = AnalysisContext(universe_name=region_scope.lower(), universe_tickers=all_tickers)

    with st.status("🔄 Running analysis pipeline…", expanded=True) as _status:
        st.write("📡 Fetching benchmark (S&P 500)…")
        ctx.benchmark_df = fetch_ohlcv("^GSPC", period="1y")

        st.write("🌍 **Agent 1** — Market Overview…")
        ag_market.run(ctx)
        st.write(
            f"   ✓ US: **{ctx.market_phase}**  |  "
            f"EU: **{ctx.eu_market_phase}**  |  "
            f"Breadth: **{ctx.breadth_signal}**"
        )

        st.write("🔄 **Agent 2** — Sector Rotation…")
        ag_sector.run(ctx)
        st.write(
            f"   ✓ US leaders: {ctx.leading_us_sectors}  |  "
            f"EU leaders: {ctx.leading_eu_sectors}"
        )

        st.write(f"🎯 **Agent 3** — Stock Screener ({len(all_tickers)} tickers)…")
        ag_screener.run(ctx)

        st.write("🧠 **Automatic Felix hierarchy** — winning sectors → winning industries → stocks…")
        hierarchical_stocks, hierarchy_meta = _hierarchical_felix_selection(
            ctx,
            early_opportunity_bias,
            industry_filter_mode,
        )
        if hierarchical_stocks:
            ctx.screened_stocks = hierarchical_stocks[: config.SCREENING["max_candidates"]]
            st.write(
                f"   ✓ {len(ctx.screened_stocks)} Felix candidates "
                f"from {hierarchy_meta.get('sector_count', 0)} sectors and "
                f"{hierarchy_meta.get('industry_count', 0)} industries"
            )
            st.session_state["hierarchy_meta"] = hierarchy_meta
        else:
            st.write("   ⚠ No hierarchical Felix candidates found; keeping screener output")
            st.session_state["hierarchy_meta"] = {"winning_sectors": [], "winning_industries": []}

        st.write(f"📈 **Agent 4** — Technical Analyst (top {max_detail})…")
        ag_ta.run(ctx)
        st.write(f"   ✓ {len(ctx.technical_analyses)} charts generated")

        st.write("📊 **Agent 5** — Fundamental Analyst…")
        ag_fa.run(ctx)
        st.write(f"   ✓ FA done for {len(ctx.fundamental_analyses)} stocks")

        st.write("📄 Saving HTML report to reports/…")
        ctx.report_path = ag_report.run(ctx)
        st.write(f"   ✓ {ctx.report_path}")

        _status.update(label="✅ Analysis complete!", state="complete")

    st.session_state.ctx      = ctx
    st.session_state.run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE  (no results yet)
# ─────────────────────────────────────────────────────────────────────────────

if "ctx" not in st.session_state:
    st.title("📊 Felix Prehn Weekend Market Analyzer")
    st.markdown(
        "Select a **region/country scope** in the sidebar and click **🚀 Run Analysis**. "
        "The app then runs an automatic hierarchy: **winning sectors -> winning industries -> Felix stock candidates**."
    )
    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📋 Scope Coverage")
        st.markdown("""
    | Scope | Coverage |
|---|---|
    | US | Large + Mid + Small cap sets |
    | Germany | DAX + MDAX |
    | UK | FTSE selection |
    | Switzerland | Swiss selection |
    | Europe | DE + Euro ex-DE + CH + UK |
    | Global | Broad multi-region mix |
        """)

    with col_r:
        st.subheader("🤖 Agent Network")
        st.markdown("""
**Agent 1 – Market Overview**
Determines market phase (Bull/Bear) per region + global breadth.

**Agent 2 – Sector Rotation**
Ranks US & EU sectors by 1W–1Y momentum. Flags leaders.

**Agent 3 – Stock Screener**
Screens every ticker with Felix Prehn / CANSLIM criteria. Scores 0–100.

**Agent 4 – Technical Analyst**
Stage 2 detection, price+MA+MACD chart, RS vs S&P 500.

**Agent 5 – Fundamental Analyst**
EPS growth, ROE, P/E, margins, strengths & risks.
        """)

    st.divider()
    st.subheader("🎯 Felix Prehn Scoring (0–100)")
    c1, c2 = st.columns(2)
    c1.markdown("""
**Technical (50 pts)**
- Stage 2 – Weinstein advancing phase → 20 pts
- Above MA50 / MA150 / MA200 → 15 pts
- RSI 50–70 → 5 pts
- MACD line > signal → 5 pts
- Within 25% of 52W high → 5 pts
    """)
    c2.markdown("""
**Fundamental (50 pts)**
- EPS growth > 25% → 15 pts
- Revenue growth > 15% → 10 pts
- P/E quality → 10 pts
- ROE > 20% → 10 pts
- Net margin > 20% → 5 pts

⭐ STRONG BUY ≥ 72 · ✅ BUY ≥ 58 · 👀 WATCH ≥ 42 · ❌ AVOID < 42
    """)

    st.divider()
    st.subheader("✅ Felix Focus Mode")
    st.markdown(
        """
- **Follow the money**: prioritize sectors and stocks with active liquidity inflow.
- **Find winning setups early**: favor names with heartbeat-style consolidation, MA50 trend up, price above MA50 and MA150, and recent volume spikes.
- The app surfaces this directly via **Felix Fit**, **Felix Pass**, **Felix Matched**, and **Felix Missing** in Liquidity Shift and Screened Stocks.
        """
    )

    st.divider()
    st.subheader("🧠 Strategy Lenses From assets/skills")
    st.markdown("Use the sidebar **Strategy Lens** selector to rank ideas by a chosen rulebook:")
    for name, desc in STRATEGY_LENS_OPTIONS.items():
        if name == "None":
            continue
        st.markdown(f"- **{name}**: {desc}")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS VIEW
# ─────────────────────────────────────────────────────────────────────────────

ctx    = st.session_state.ctx
stocks = ctx.screened_stocks or []
_flow_df_for_kpi = _build_sector_flow_table(ctx)
_winners_for_kpi = _build_liquidity_winners(
    stocks,
    _flow_df_for_kpi,
    top_n=max(12, config.MAX_DETAIL_STOCKS),
    early_bias_mode=early_opportunity_bias,
)
_top_inflow_sectors, _flow_state_by_sector = _flow_context_maps(_flow_df_for_kpi)
_liq_conf_score, _liq_conf_label = _liquidity_confidence(_flow_df_for_kpi, _winners_for_kpi)

# ── Top KPI row ───────────────────────────────────────────────────────────────
st.title(f"📊 Analysis – {st.session_state.run_time}")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric(
    f"{phase_to_emoji(ctx.market_phase)} US Market",
    ctx.market_phase or "–",
)
k2.metric(
    f"{phase_to_emoji(ctx.eu_market_phase)} EU Market",
    ctx.eu_market_phase or "–",
)
k3.metric("🌍 Breadth", ctx.breadth_signal or "–")
k4.metric("🎯 Candidates", len(stocks))
k5.metric("🏆 Top Score", f"{stocks[0]['score']}/100" if stocks else "–")
k6.metric("💧 Liquidity Confidence", f"{_liq_conf_score}/100", _liq_conf_label)
st.divider()

hier_meta = st.session_state.get("hierarchy_meta")
if isinstance(hier_meta, dict) and hier_meta:
    st.caption(
        f"Hierarchy summary: {hier_meta.get('sector_count', 0)} winning sectors -> "
        f"{hier_meta.get('industry_count', 0)} winning industries -> "
        f"{len(stocks)} shortlisted stocks  ·  Industry filter: {industry_filter_mode}"
    )

with st.expander("📚 Abbreviations & Stage Guide", expanded=False):
    st.markdown(
        """
        **Returns**: 1D, 1W, 1M, 3M, 6M, 1Y = return over 1 day/week/month/3 months/6 months/1 year.  
        **YTD** = year-to-date return.

        **Trend/Momentum**:  
        **MA50 / MA150 / MA200** = 50/150/200-day moving average.  
        **RS** = relative strength vs S&P 500.  
        **RSI** = Relative Strength Index (0-100).  
        **MACD** = moving average convergence/divergence momentum signal.

        **Fundamentals**:  
        **P/E** = price-to-earnings ratio.  
        **EPS** = earnings per share.  
        **EPS↑** = EPS growth metric.  
        **ROE** = return on equity.

        **Other labels**:  
        **3F** = three-filter overlay (cash runway, institutional support, revenue quality).  
        **TA / FA** = technical analysis / fundamental analysis.

        **Weinstein Stage model**:  
        **S1 (Basing)** = sideways consolidation.  
        **S2 (Advancing)** = price above rising long MA (preferred for long setups).  
        **S3 (Topping)** = trend plateauing, higher reversal risk.  
        **S4 (Declining)** = price below falling long MA (downtrend).
        """
    )


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🌐 Market Overview",
    "🔄 Sector Rotation",
    "💧 Liquidity Shift",
    "🏭 Industries",
    "🎯 Screened Stocks",
    "🔍 Deep Dive",
])


# ── TAB 1: MARKET OVERVIEW ────────────────────────────────────────────────────
with tab1:
    idx = ctx.index_data or {}

    if idx:
        rows = []
        for name, d in idx.items():
            if "error" in d:
                continue
            rows.append({
                "Index":  name,
                "Last":   d.get("last"),
                "1D%":    d.get("1d_chg"),
                "1W%":    d.get("1w_chg"),
                "1M%":    d.get("1m_chg"),
                "YTD%":   d.get("ytd_chg"),
                "1Y%":    d.get("1y_chg"),
                "MA200":  "✓" if d.get("above_ma200") else "✗",
                "MA50":   "✓" if d.get("above_ma50")  else "✗",
            })
        df_idx = pd.DataFrame(rows).set_index("Index")

        pct_cols: List[Hashable] = ["1D%", "1W%", "1M%", "YTD%", "1Y%"]
        styled = (
            df_idx.style
            .map(_pct_style, subset=pct_cols)
            .map(_ma_style,  subset=["MA200", "MA50"])
            .format({c: "{:+.2f}%" for c in pct_cols}, na_rep="–")
            .format({"Last": "{:.2f}"}, na_rep="–")
        )
        st.dataframe(styled, width="stretch", height=380)

        # Uptrend count badge
        up = ctx.uptrend_count
        total = ctx.total_indices
        st.caption(
            f"{up}/{total} indices above both MA50 & MA200  —  "
            f"breadth signal: **{ctx.breadth_signal}**"
        )
    else:
        st.info("No index data available.")


# ── TAB 2: SECTOR ROTATION ────────────────────────────────────────────────────
with tab2:

    def _render_sector_tab(df_rank, leaders, title, etf_map):
        st.subheader(title)
        if df_rank is None or df_rank.empty:
            st.info("No sector data.")
            return

        # ── Return table ──────────────────────────────────────────────────────
        period_cols = [c for c in ["1wk", "1mo", "3mo", "6mo", "1y"] if c in df_rank.columns]
        extra       = ["momentum_score", "rank"] if "rank" in df_rank.columns else []
        display     = df_rank[[c for c in period_cols + extra if c in df_rank.columns]]

        def _s(val):
            if pd.isna(val) or not isinstance(val, (int, float)): return ""
            return "color:#2da44e;font-weight:bold" if val > 0 else "color:#cf222e;font-weight:bold"

        fmt = {c: "{:+.1f}%" for c in period_cols}
        if "momentum_score" in display.columns:
            fmt["momentum_score"] = "{:+.2f}"

        st.dataframe(
            display.style.map(_s, subset=period_cols).format(fmt, na_rep="–"),
            use_container_width=True, height=320,
        )
        if leaders:
            st.success(f"**Top momentum:** {' · '.join(leaders)}")

        # ── Mini chart grid ───────────────────────────────────────────────────
        st.markdown("##### Sparklines – Price, MA50 & Volume (3 months)")
        etf_items = list(etf_map.items())
        COLS = 4
        for i in range(0, len(etf_items), COLS):
            chunk     = etf_items[i : i + COLS]
            grid_cols = st.columns(COLS)
            for gc, (name, etf) in zip(grid_cols, chunk):
                df_etf = fetch_ohlcv(etf, period="6mo")
                img    = _mini_chart(df_etf)
                ret_1w = None
                if df_rank is not None and name in df_rank.index and "1wk" in df_rank.columns:
                    v = df_rank.loc[name, "1wk"]
                    ret_1w = None if pd.isna(v) else float(v)
                is_leader  = name in leaders
                leader_tag = " 🏆" if is_leader else ""
                pct_str    = f"{ret_1w:+.1f}%" if ret_1w is not None else "–"
                arrow      = _trend_arrow(ret_1w)
                with gc:
                    if img:
                        st.image(img, width='stretch')
                    st.caption(f"{arrow} **{name}**{leader_tag}  \n1M: {pct_str}")

    _render_sector_tab(ctx.us_sector_rank, ctx.leading_us_sectors, "🇺🇸 US Sectors", config.US_SECTOR_ETFS)
    st.divider()
    _render_sector_tab(ctx.eu_sector_rank, ctx.leading_eu_sectors, "🇪🇺 EU Sectors", config.EU_SECTOR_ETFS)


# ── TAB 3: LIQUIDITY SHIFT ───────────────────────────────────────────────────
with tab3:
    st.subheader("Where Liquidity Is Moving")
    st.caption(
        "Flow State blends weighted sector momentum with short-term acceleration. "
        "Stocks are ranked to favor early liquidity inflow candidates with more upside left, "
        "while penalizing already-extended moves."
    )
    st.caption(f"Early Opportunity Bias: **{early_opportunity_bias}**")
    if felix_focus_mode:
        st.caption("Felix Focus Mode: **ON** (prioritizing money-flow + winning-stock pattern alignment)")
    t3c1, t3c2 = st.columns([1, 1])
    with t3c1:
        felix_only_tab3 = st.checkbox(
            "Felix-only candidates",
            value=False,
            key="felix_only_tab3",
            help="When enabled, show only names that pass a minimum number of Felix criteria.",
        )
    with t3c2:
        felix_min_pass_tab3 = st.select_slider(
            "Felix min pass",
            options=[4, 5],
            value=4,
            key="felix_min_pass_tab3",
            help="4 = strong alignment, 5 = strict all-criteria alignment.",
        )
    with st.expander("What does Early Opportunity Bias do?", expanded=False):
        st.markdown(
            """
            - **Conservative**: applies a stronger extension penalty. It favors cleaner, less stretched setups and deprioritizes names that already ran hard.
            - **Balanced**: neutral weighting between early-opportunity signals and momentum continuation.
            - **Aggressive**: boosts early inflow + upside-left signals more strongly and softens extension penalties, so emerging movers surface earlier.

            This slider changes only **Liquidity Shift ranking behavior**. It does not change raw market data, technical analysis, or fundamental analysis outputs.
            """
        )
    if strategy_lens != "None":
        st.caption(f"Strategy lens active: **{strategy_lens}**")

    flow_df = _flow_df_for_kpi.copy() if _flow_df_for_kpi is not None else pd.DataFrame()
    winners_df = _winners_for_kpi.copy() if _winners_for_kpi is not None else pd.DataFrame()

    f1, f2, f3 = st.columns(3)
    with f1:
        region_filter = st.multiselect(
            "Region",
            options=["US", "EU"],
            default=["US", "EU"],
            key="liq_region_filter",
        )
    with f2:
        stage_only_s2 = st.checkbox("Only Stage 2 winners", value=False, key="liq_stage2_filter")
    with f3:
        min_liq_score = st.slider(
            "Minimum Liquidity Score",
            min_value=0,
            max_value=100,
            value=60,
            step=1,
            key="liq_min_score",
        )

    if flow_df is not None and not flow_df.empty and region_filter:
        flow_df = flow_df[flow_df["Region"].isin(region_filter)].reset_index(drop=True)

    if winners_df is not None and not winners_df.empty:
        winners_df = winners_df[winners_df["Liquidity"] >= float(min_liq_score)]
        if stage_only_s2:
            winners_df = winners_df[winners_df["Stage"] == "S2"]
        if region_filter and flow_df is not None and not flow_df.empty:
            allowed_canonical = set(flow_df["Canonical"].tolist()) if "Canonical" in flow_df.columns else set()
            if allowed_canonical:
                winners_df = winners_df[winners_df["Flow Sector"].isin(allowed_canonical)]

        if strategy_lens != "None":
            by_ticker = {x.get("ticker"): x for x in (stocks or [])}
            lens_fit = []
            lens_match = []
            lens_risk = []
            for _, row in winners_df.iterrows():
                base = by_ticker.get(row.get("Ticker"))
                if not base:
                    lens_fit.append(0.0)
                    lens_match.append("No stock context")
                    lens_risk.append("Unavailable")
                    continue
                fit, matched, risk_text = _strategy_lens_evaluation(
                    base,
                    _top_inflow_sectors,
                    _flow_state_by_sector,
                    strategy_lens,
                )
                lens_fit.append(fit)
                lens_match.append(matched)
                lens_risk.append(risk_text)

            winners_df = winners_df.assign(
                **{
                    "Lens Fit": lens_fit,
                    "Matched Patterns": lens_match,
                    "Risk Flags": lens_risk,
                }
            )
            winners_df = winners_df.sort_values(["Lens Fit", "Liquidity", "Prehn"], ascending=False)

        by_ticker = {x.get("ticker"): x for x in (stocks or [])}
        felix_fit_vals = []
        felix_match_vals = []
        felix_risk_vals = []
        felix_pass_count_vals = []
        for _, row in winners_df.iterrows():
            base = by_ticker.get(row.get("Ticker"))
            if not base:
                felix_fit_vals.append(0.0)
                felix_match_vals.append("No stock context")
                felix_risk_vals.append("Unavailable")
                felix_pass_count_vals.append(0)
                continue
            f_fit, f_match, f_risk, f_checks = _felix_method_signals(
                base,
                _top_inflow_sectors,
                _flow_state_by_sector,
            )
            felix_fit_vals.append(f_fit)
            felix_match_vals.append(f_match)
            felix_risk_vals.append(f_risk)
            felix_pass_count_vals.append(sum(1 for v in f_checks.values() if v))

        winners_df = winners_df.assign(
            **{
                "Felix Fit": felix_fit_vals,
                "Felix Matched": felix_match_vals,
                "Felix Missing": felix_risk_vals,
                "Felix Pass": felix_pass_count_vals,
            }
        )

        if felix_focus_mode:
            winners_df = winners_df.sort_values(["Felix Fit", "Liquidity", "Prehn"], ascending=False)

        if felix_only_tab3:
            winners_df = winners_df[winners_df["Felix Pass"] >= int(felix_min_pass_tab3)]
        winners_df = winners_df.reset_index(drop=True)

    if flow_df.empty:
        st.info("No sector flow data available yet.")
    else:
        top_inflow = flow_df[flow_df["Momentum"] > 0].head(3)
        top_outflow = flow_df[flow_df["Momentum"] < 0].sort_values("Momentum").head(3)
        accel = flow_df.dropna(subset=["Flow Delta"]).sort_values("Flow Delta", ascending=False).head(3)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Top Inflow Sectors**")
            if top_inflow.empty:
                st.write("No clear inflow yet")
            else:
                for _, r in top_inflow.iterrows():
                    st.write(f"🟢 {r['Region']} · {r['Sector']} ({r['Momentum']:+.2f})")
        with c2:
            st.markdown("**Fastest Acceleration**")
            if accel.empty:
                st.write("No acceleration signal")
            else:
                for _, r in accel.iterrows():
                    st.write(f"⚡ {r['Region']} · {r['Sector']} ({r['Flow Delta']:+.2f})")
        with c3:
            st.markdown("**Outflow Warnings**")
            if top_outflow.empty:
                st.write("No major outflows")
            else:
                for _, r in top_outflow.iterrows():
                    st.write(f"🔴 {r['Region']} · {r['Sector']} ({r['Momentum']:+.2f})")

        st.markdown("#### Sector Flow Matrix")
        show_cols: List[Hashable] = ["Region", "Sector", "Flow State", "Momentum", "Flow Delta", "1W%", "1M%", "3M%", "1Y%"]
        fmt_map: Dict[Hashable, object] = {
            "Momentum": "{:+.2f}",
            "Flow Delta": "{:+.2f}",
            "1W%": "{:+.2f}%",
            "1M%": "{:+.2f}%",
            "3M%": "{:+.2f}%",
            "1Y%": "{:+.2f}%",
        }
        st.dataframe(
            flow_df[show_cols].style
            .map(_flow_state_style, subset=["Flow State"])
            .map(_pct_style, subset=["1W%", "1M%", "3M%", "1Y%"])
            .map(_pct_style, subset=["Flow Delta"])
            .format(cast(Any, fmt_map), na_rep="–"),
            width="stretch",
            height=420,
        )

    st.markdown("#### Most Likely Winners From Ongoing Liquidity Shift")
    if winners_df.empty:
        st.info("No screened stocks available for liquidity ranking yet.")
    else:
        csv_bytes = winners_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Export Liquidity Winners (CSV)",
            data=csv_bytes,
            file_name=f"liquidity_winners_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=False,
        )

        win_event = st.dataframe(
            winners_df,
            width="stretch",
            height=min(700, 50 + len(winners_df) * 36),
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Why": st.column_config.TextColumn(
                    "Why",
                    help="Main reasons this stock ranks high: inflow alignment, early structure, and upside-left signals.",
                    width="large",
                ),
                "Risk": st.column_config.TextColumn(
                    "Risk",
                    help="Quick risk view (for example extended/late-stage/weak RS).",
                ),
                "Liquidity": st.column_config.ProgressColumn(
                    "Liquidity",
                    help="Composite score (0-100): inflow strength + quality + trend context + upside-left profile - extension penalty.",
                    min_value=0,
                    max_value=100,
                    format="%.1f /100",
                ),
                "Prehn": st.column_config.NumberColumn(
                    "Prehn",
                    help="Base Felix Prehn stock score before liquidity overlay.",
                    format="%.0f",
                ),
                "Stage": st.column_config.TextColumn(
                    "Stage",
                    help="Weinstein stage label (S1 basing, S2 advancing, S3 topping, S4 declining).",
                ),
                "1M%": st.column_config.NumberColumn(
                    "1M%",
                    help="1-month price return.",
                    format="%.2f%%",
                ),
                "3M%": st.column_config.NumberColumn(
                    "3M%",
                    help="3-month price return.",
                    format="%.2f%%",
                ),
                "RS%": st.column_config.NumberColumn(
                    "RS%",
                    help="Relative strength versus S&P 500.",
                    format="%.2f%%",
                ),
                "Felix Fit": st.column_config.ProgressColumn(
                    "Felix Fit",
                    help="Felix method alignment score across 5 checks.",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "Felix Pass": st.column_config.NumberColumn(
                    "Felix Pass",
                    help="Number of Felix criteria passed (out of 5).",
                    format="%d /5",
                ),
                "Felix Matched": st.column_config.TextColumn(
                    "Felix Matched",
                    help="Matched Felix criteria: liquidity flow, heartbeat, MA trend/position, volume.",
                    width="large",
                ),
                "Felix Missing": st.column_config.TextColumn(
                    "Felix Missing",
                    help="Unmet Felix criteria for this candidate.",
                    width="large",
                ),
                "Lens Fit": st.column_config.ProgressColumn(
                    "Lens Fit",
                    help="How strongly this stock matches the selected strategy's pattern checklist.",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "Matched Patterns": st.column_config.TextColumn(
                    "Matched Patterns",
                    help="Top matched pattern-recognition signals for the selected lens.",
                    width="large",
                ),
                "Risk Flags": st.column_config.TextColumn(
                    "Risk Flags",
                    help="Rule conflicts or risk guard-rail warnings for the selected lens.",
                    width="large",
                ),
            },
        )
        st.caption(
            "Liquidity score now emphasizes names with strong inflow and room to run, "
            "not only names that already made the biggest move. Felix Fit shows direct alignment to the Felix method. "
            "Click a row to inspect it in Deep Dive."
        )

        sel_rows: List[int] = []
        if isinstance(win_event, dict):
            selection = win_event.get("selection")
            if isinstance(selection, dict):
                raw_rows = selection.get("rows", [])
                if isinstance(raw_rows, list):
                    sel_rows = [int(r) for r in raw_rows]
        if sel_rows:
            sel_ticker = winners_df.iloc[sel_rows[0]]["Ticker"]
            st.session_state["deep_dive_ticker"] = sel_ticker
            st.success(f"{sel_ticker} selected for Deep Dive.")


# ── TAB 4: INDUSTRIES ────────────────────────────────────────────────────────
with tab4:
    if not stocks:
        st.info("Run the analysis first — industry data is derived from screened stocks.")
    else:
        # ── Build industry summary from screened stocks ───────────────────────
        industry_groups: dict = {}
        for s in stocks:
            ind = (s.get("industry") or "").strip() or "Unclassified"
            sec = (s.get("sector")   or "").strip() or "Other"
            if ind not in industry_groups:
                industry_groups[ind] = {"sector": sec, "stocks": []}
            industry_groups[ind]["stocks"].append(s)

        ind_rows = []
        for ind, data in industry_groups.items():
            stks    = data["stocks"]
            scores  = [s["score"]    for s in stks]
            r1w     = [s["ret_1w"]   for s in stks if s.get("ret_1w")  is not None]
            r1m     = [s["ret_1m"]   for s in stks if s.get("ret_1m")  is not None]
            r3m     = [s["ret_3m"]   for s in stks if s.get("ret_3m")  is not None]
            top_s   = max(stks, key=lambda x: x["score"])
            industry_etfs = getattr(config, "INDUSTRY_ETFS", {})
            etf_t   = industry_etfs.get(ind) if isinstance(industry_etfs, dict) else None
            ind_rows.append({
                "industry":   ind,
                "sector":     data["sector"],
                "count":      len(stks),
                "avg_score":  round(sum(scores) / len(scores), 1),
                "avg_1w":     round(sum(r1w) / len(r1w), 2) if r1w else None,
                "avg_1m":     round(sum(r1m) / len(r1m), 2) if r1m else None,
                "avg_3m":     round(sum(r3m) / len(r3m), 2) if r3m else None,
                "top_stock":  top_s["ticker"],
                "top_score":  top_s["score"],
                "etf":        etf_t or "–",
                "_stocks":    stks,
            })
        ind_rows.sort(key=lambda x: x["avg_score"], reverse=True)

        # ── Sector filter ─────────────────────────────────────────────────────
        all_sectors = sorted({r["sector"] for r in ind_rows})
        sel_sector  = st.selectbox(
            "Filter by Sector",
            ["All sectors"] + all_sectors,
            key="ind_sector_filter",
        )
        filtered_ind = (
            ind_rows if sel_sector == "All sectors"
            else [r for r in ind_rows if r["sector"] == sel_sector]
        )

        # ── Industry summary table ────────────────────────────────────────────
        st.markdown("#### Industry Summary")
        tbl_rows = []
        for r in filtered_ind:
            tbl_rows.append({
                "Industry":   r["industry"],
                "Sector":     r["sector"],
                "# Stocks":   r["count"],
                "Avg Score":  r["avg_score"],
                "Avg 1M%":    r["avg_1m"],
                "Avg 3M%":    r["avg_3m"],
                "Top Stock":  r["top_stock"],
                "Top Score":  r["top_score"],
                "ETF":        r["etf"],
            })
        df_ind = pd.DataFrame(tbl_rows)

        def _ind_score_style(val):
            try:
                v = float(val)
                if v >= 72: return "background-color:#0d2b0d;color:#2da44e;font-weight:bold"
                if v >= 58: return "background-color:#0d1a2b;color:#0969da;font-weight:bold"
                if v >= 42: return "background-color:#2b2b0d;color:#bf8700;font-weight:bold"
                return "background-color:#2b0d0d;color:#cf222e;font-weight:bold"
            except (TypeError, ValueError):
                return ""

        styled_ind = (
            df_ind.style
            .map(_ind_score_style, subset=["Avg Score", "Top Score"])
            .map(_pct_style,       subset=["Avg 1M%", "Avg 3M%"])
            .format({"Avg 1M%": "{:+.2f}%", "Avg 3M%": "{:+.2f}%"}, na_rep="–")
            .format({"Avg Score": "{:.1f}", "Top Score": "{:.0f}"})
        )
        st.dataframe(styled_ind, width="stretch", height=min(600, 60 + len(tbl_rows) * 36))
        st.caption(
            "Industries derived from Yahoo Finance metadata.  "
            "ETF column = representative industry ETF where one exists."
        )

        # ── Industry ETF sparklines ───────────────────────────────────────────
        etf_industries = [r for r in filtered_ind if r["etf"] != "–"]
        if etf_industries:
            st.markdown("#### Industry ETF Sparklines – Price, MA50 & Volume (3 months)")
            COLS = 4
            for i in range(0, len(etf_industries), COLS):
                chunk     = etf_industries[i : i + COLS]
                grid_cols = st.columns(COLS)
                for gc, r in zip(grid_cols, chunk):
                    df_etf = fetch_ohlcv(r["etf"], period="6mo")
                    img    = _mini_chart(df_etf)
                    score_icon = (
                        "🟢" if r["avg_score"] >= 72 else
                        "🔵" if r["avg_score"] >= 58 else
                        "🟡" if r["avg_score"] >= 42 else "🔴"
                    )
                    avg_1w  = r["avg_1m"]
                    pct_str = f"{avg_1w:+.1f}%" if avg_1w is not None else "–"
                    arrow   = _trend_arrow(avg_1w)
                    with gc:
                        if img:
                            st.image(img)
                        st.caption(
                            f"{score_icon} **{r['industry'][:22]}**  \n"
                            f"{r['etf']}  ·  {arrow} 1M avg: {pct_str}  ·  {r['count']} stocks"
                        )

        # ── Industry drill-down: stocks filter ───────────────────────────────
        st.divider()
        st.markdown("#### Stocks by Industry")
        ind_names      = ["All industries"] + [r["industry"] for r in filtered_ind]
        sel_industry   = st.selectbox("Filter by Industry", ind_names, key="ind_drill")

        if sel_industry == "All industries":
            drill_stocks = [s for r in filtered_ind for s in r["_stocks"]]
        else:
            match = next((r for r in filtered_ind if r["industry"] == sel_industry), None)
            drill_stocks = match["_stocks"] if match else []

        if drill_stocks:
            drill_rows = []
            for s in sorted(drill_stocks, key=lambda x: x["score"], reverse=True):
                drill_rows.append({
                    "Ticker":  s["ticker"],
                    "Name":    (s.get("name") or "")[:28],
                    "Industry":(s.get("industry") or "")[:30],
                    "Score":   s["score"],
                    "Stage":   f"S{s.get('stage','?')}",
                    "1W%":     s.get("ret_1w"),
                    "1M%":     s.get("ret_1m"),
                    "3M%":     s.get("ret_3m"),
                    "1Y%":     s.get("ret_1y"),
                    "RS%":     s.get("rs_bench"),
                    "RSI":     round(s["rsi"], 0) if s.get("rsi") else None,
                    "P/E":     round(s["pe"],  1) if s.get("pe")  else None,
                })
            df_drill = pd.DataFrame(drill_rows)
            pct_d: List[Hashable] = ["1M%", "3M%", "1Y%", "RS%"]
            styled_drill = (
                df_drill.style
                .map(_score_style, subset=["Score"])
                .map(_stage_style, subset=["Stage"])
                .map(_pct_style,   subset=pct_d)
                .format({c: "{:+.2f}%" for c in pct_d}, na_rep="–")
                .format({"P/E": "{:.1f}", "RSI": "{:.0f}"}, na_rep="–")
            )
            st.dataframe(styled_drill, width="stretch",
                         height=min(700, 50 + len(drill_rows) * 36))

            # Mini sparklines for this industry's stocks
            st.markdown("##### Sparklines")
            COLS = 5
            for i in range(0, len(drill_stocks), COLS):
                chunk     = sorted(drill_stocks, key=lambda x: x["score"], reverse=True)[i : i + COLS]
                grid_cols = st.columns(COLS)
                for gc, s in zip(grid_cols, chunk):
                    img    = _mini_chart(s.get("_df"))
                    score  = s["score"]
                    stage  = s.get("stage", "?")
                    ret_1m = s.get("ret_1m")
                    s_icon = "🟢" if score >= 72 else "🔵" if score >= 58 else "🟡" if score >= 42 else "🔴"
                    st_tag = "✅" if stage == 2 else "⚠️" if stage == 1 else "❌"
                    ret_str = f"  {ret_1m:+.1f}%" if ret_1m is not None else ""
                    with gc:
                        if img:
                            st.image(img)
                        st.caption(
                            f"{s_icon} **{s['ticker']}** {score}/100  \n"
                            f"S{stage}{st_tag}{ret_str}"
                        )
        else:
            st.info("No stocks found for this selection.")


# ── TAB 5: SCREENED STOCKS ────────────────────────────────────────────────────
with tab5:
    if not stocks:
        st.warning("No candidates passed screening.")
    else:
        if felix_focus_mode:
            st.info(
                "Felix Focus Mode active: ranking by Felix method alignment first, then model quality."
            )

        if strategy_lens != "None":
            st.info(
                f"Strategy Lens active: **{strategy_lens}**  \n"
                f"{STRATEGY_LENS_OPTIONS.get(strategy_lens, '')}"
            )

        rows = []
        for s in stocks:
            felix_fit, felix_match, felix_missing, felix_checks = _felix_method_signals(
                s,
                _top_inflow_sectors,
                _flow_state_by_sector,
            )
            fit, matched, risk_text = _strategy_lens_evaluation(
                s,
                _top_inflow_sectors,
                _flow_state_by_sector,
                strategy_lens,
            )
            rows.append({
                "Ticker":  s["ticker"],
                "Name":    (s.get("name") or "")[:28],
                "Sector":  (s.get("sector") or ""),
                "Score":   s["score"],
                "Rating":  (s.get("rating") or "").replace("⭐ ","").replace("✅ ","").replace("👀 ","").replace("❌ ",""),
                "Stage":   f"S{s.get('stage','?')}",
                "1M%":     s.get("ret_1m"),
                "3M%":     s.get("ret_3m"),
                "1Y%":     s.get("ret_1y"),
                "RS%":     s.get("rs_bench"),
                "RSI":     round(s["rsi"], 0)           if s.get("rsi")        else None,
                "P/E":     round(s["pe"],  1)           if s.get("pe")         else None,
                "EPS↑":    f"{s['eps_growth']*100:.0f}%" if s.get("eps_growth") is not None else "–",
                "Felix Fit": felix_fit,
                "Felix Pass": sum(1 for v in felix_checks.values() if v),
                "Felix Matched": felix_match,
                "Felix Missing": felix_missing,
                "Lens Fit": fit,
                "Matched Patterns": matched,
                "Risk Flags": risk_text,
            })

        df_sc = pd.DataFrame(rows)

        t5c1, t5c2 = st.columns([1, 1])
        with t5c1:
            felix_only_tab5 = st.checkbox(
                "Felix-only candidates",
                value=False,
                key="felix_only_tab5",
                help="When enabled, show only names that pass a minimum number of Felix criteria.",
            )
        with t5c2:
            felix_min_pass_tab5 = st.select_slider(
                "Felix min pass",
                options=[4, 5],
                value=4,
                key="felix_min_pass_tab5",
                help="4 = strong alignment, 5 = strict all-criteria alignment.",
            )

        if felix_only_tab5:
            df_sc = df_sc[df_sc["Felix Pass"] >= int(felix_min_pass_tab5)]

        if felix_focus_mode:
            df_sc = df_sc.sort_values(["Felix Fit", "Score"], ascending=False).reset_index(drop=True)
        elif strategy_lens != "None":
            df_sc = df_sc.sort_values(["Lens Fit", "Score"], ascending=False).reset_index(drop=True)

        sc_event = st.dataframe(
            df_sc,
            width="stretch",
            height=min(900, 50 + len(rows) * 36),
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score",
                    help="Felix Prehn model score (0-100).",
                    min_value=0,
                    max_value=100,
                    format="%d /100",
                ),
                "Felix Fit": st.column_config.ProgressColumn(
                    "Felix Fit",
                    help="Felix method alignment score across 5 checks.",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "Felix Pass": st.column_config.NumberColumn(
                    "Felix Pass",
                    help="Number of Felix criteria passed (out of 5).",
                    format="%d /5",
                ),
                "Felix Matched": st.column_config.TextColumn(
                    "Felix Matched",
                    help="Matched Felix criteria: liquidity flow, heartbeat, MA trend/position, volume.",
                    width="large",
                ),
                "Felix Missing": st.column_config.TextColumn(
                    "Felix Missing",
                    help="Unmet Felix criteria for this candidate.",
                    width="large",
                ),
                "Lens Fit": st.column_config.ProgressColumn(
                    "Lens Fit",
                    help="How strongly this stock matches the selected strategy's pattern checklist.",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "Matched Patterns": st.column_config.TextColumn(
                    "Matched Patterns",
                    help="Top matched pattern-recognition signals for the selected lens.",
                    width="large",
                ),
                "Risk Flags": st.column_config.TextColumn(
                    "Risk Flags",
                    help="Rule conflicts or risk guard-rail warnings for the selected lens.",
                    width="large",
                ),
                "Stage": st.column_config.TextColumn(
                    "Stage",
                    help="Weinstein stage label (S1 basing, S2 advancing, S3 topping, S4 declining).",
                ),
                "1M%": st.column_config.NumberColumn(
                    "1M%",
                    help="1-month price return.",
                    format="%.2f%%",
                ),
                "3M%": st.column_config.NumberColumn(
                    "3M%",
                    help="3-month price return.",
                    format="%.2f%%",
                ),
                "1Y%": st.column_config.NumberColumn(
                    "1Y%",
                    help="1-year price return.",
                    format="%.2f%%",
                ),
                "RS%": st.column_config.NumberColumn(
                    "RS%",
                    help="Relative strength versus S&P 500.",
                    format="%.2f%%",
                ),
                "RSI": st.column_config.NumberColumn(
                    "RSI",
                    help="Relative Strength Index momentum oscillator (0-100).",
                    format="%.0f",
                ),
                "P/E": st.column_config.NumberColumn(
                    "P/E",
                    help="Price-to-earnings ratio.",
                    format="%.1f",
                ),
                "EPS↑": st.column_config.TextColumn(
                    "EPS↑",
                    help="Earnings per share growth rate.",
                ),
            },
        )
        st.caption(
            "Score 0–100  ·  Stage S2 = advancing (ideal entry per Weinstein/Prehn)  "
            "·  RS% = 1Y return relative to S&P 500  "
            "·  Felix Fit = direct method alignment (money flow + heartbeat + MA + volume)  "
            "·  Lens Fit shows alignment with selected assets/skills playbook  "
            "·  **Click a row to open it in Deep Dive ↗**"
        )

        # Handle row click → pre-select in Deep Dive tab
        sel_rows: List[int] = []
        if isinstance(sc_event, dict):
            selection = sc_event.get("selection")
            if isinstance(selection, dict):
                raw_rows = selection.get("rows", [])
                if isinstance(raw_rows, list):
                    sel_rows = [int(r) for r in raw_rows]
        if sel_rows:
            sel_ticker = rows[sel_rows[0]]["Ticker"]
            st.session_state["deep_dive_ticker"] = sel_ticker
            st.success(
                f"**{sel_ticker}** selected — switch to the **🔍 Deep Dive** tab for the full analysis."
            )

        # ── Mini chart gallery ────────────────────────────────────────────────
        st.divider()
        st.markdown("##### Sparklines – Price, MA50 & Volume (3 months)")
        COLS   = 5
        top_sc = stocks[:config.MAX_DETAIL_STOCKS]
        for i in range(0, len(top_sc), COLS):
            chunk     = top_sc[i : i + COLS]
            grid_cols = st.columns(COLS)
            for gc, s in zip(grid_cols, chunk):
                img    = _mini_chart(s.get("_df"))
                score  = s["score"]
                stage  = s.get("stage", "?")
                ret_1m = s.get("ret_1m")
                s_icon = "🟢" if score >= 72 else "🔵" if score >= 58 else "🟡" if score >= 42 else "🔴"
                st_tag = "✅" if stage == 2 else "⚠️" if stage == 1 else "❌"
                ret_str = f"  {ret_1m:+.1f}%" if ret_1m is not None else ""
                with gc:
                    if img:
                        st.image(img, width='stretch')
                    st.caption(
                        f"{s_icon} **{s['ticker']}** {score}/100  \n"
                        f"S{stage}{st_tag}{ret_str}"
                    )


# ── TAB 6: DEEP DIVE ─────────────────────────────────────────────────────────
with tab6:
    if not stocks:
        st.info("Run the analysis first.")
        st.stop()

    top_n_stocks = stocks[:config.MAX_DETAIL_STOCKS]
    options = [
        f"{s['ticker']}  {(s.get('name') or '')[:30]}  [{s['score']}/100]"
        for s in top_n_stocks
    ]
    # Default to the ticker clicked in Screened Stocks tab (if any)
    _presel = st.session_state.get("deep_dive_ticker")
    _default_idx = 0
    if _presel:
        for _i, _s in enumerate(top_n_stocks):
            if _s["ticker"] == _presel:
                _default_idx = _i
                break
    chosen_label = st.selectbox("Select stock", options, index=_default_idx)
    chosen_idx   = options.index(chosen_label)
    s            = top_n_stocks[chosen_idx]
    ticker       = s["ticker"]

    ta_d = (ctx.technical_analyses   or {}).get(ticker, {})
    fa_d = (ctx.fundamental_analyses or {}).get(ticker, {})

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"## {ticker}  —  {s.get('name','')}")
    st.caption(f"{s.get('sector','')}  ·  {s.get('industry','')}  ·  {s.get('country','')}")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Prehn Score",  f"{s['score']}/100")
    m2.metric("Stage",        f"Stage {s.get('stage','?')}")
    m3.metric("RSI",          f"{s['rsi']:.0f}" if s.get("rsi") else "–")
    m4.metric("1M Return",    f"{s['ret_1m']:+.2f}%" if s.get("ret_1m") is not None else "–")
    m5.metric("3M Return",    f"{s['ret_3m']:+.2f}%" if s.get("ret_3m") is not None else "–")
    m6.metric("RS vs S&P",    f"{s['rs_bench']:+.2f}%" if s.get("rs_bench") is not None else "–")

    st.markdown(f"> **Rating:** {s.get('rating','')}")
    st.divider()

    # ── Two-column layout: chart LEFT | FA RIGHT ─────────────────────────────
    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        st.subheader("📈 Technical Chart")
        chart_b64 = ta_d.get("chart_b64")
        if chart_b64:
            st.image(base64.b64decode(chart_b64))
        else:
            st.warning("Chart unavailable (need ≥50 trading days of data).")

        interp = ta_d.get("interpretation", "")
        if interp:
            with st.expander("TA Interpretation", expanded=True):
                st.markdown(interp)

    with right_col:
        st.subheader("📊 Fundamentals")

        threshold_profile = fa_d.get("threshold_profile", {})
        if threshold_profile:
            st.caption(
                "Threshold context: "
                f"Style={threshold_profile.get('style', 'n/a')} · "
                f"Cap={threshold_profile.get('cap_bucket', 'n/a')} · "
                f"Volatility={threshold_profile.get('volatility', 'n/a')} · "
                f"IndustryRule={threshold_profile.get('industry_rule', 'none')}"
            )

        narrative = fa_d.get("narrative", "")
        if narrative:
            st.markdown(narrative)
            st.divider()

        metrics = fa_d.get("metrics", [])
        if metrics:
            # Display as a styled mini-table using columns
            for m in metrics:
                sig = m.get("signal", "neutral")
                icon = {"good": "🟢", "warn": "🟡", "bad": "🔴"}.get(sig, "⚪")
                lc, vc, tc = st.columns([2, 1, 3])
                lc.markdown(f"{icon} {m['label']}")
                vc.markdown(f"**{m['value']}**")
                tc.markdown(m.get("thresholds", ""))

        strengths = fa_d.get("strengths", [])
        risks     = fa_d.get("risks",     [])

        if strengths or risks:
            st.divider()
        if strengths:
            st.markdown("**✅ Strengths**")
            for item in strengths:
                st.markdown(f"- {item}")
        if risks:
            st.markdown("**⚠️ Risks**")
            for item in risks:
                st.markdown(f"- {item}")

    # ── Score breakdown ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Score Breakdown")
    breakdown = s.get("breakdown", {})
    if breakdown:
        b_left, b_right = st.columns(2)
        items = list(breakdown.items())
        mid   = len(items) // 2

        for col, chunk in [(b_left, items[:mid]), (b_right, items[mid:])]:
            with col:
                for criterion, (detail, earned, max_pts) in chunk:
                    fill = earned / max_pts if max_pts else 0
                    color = "🟢" if fill >= 0.8 else "🟡" if fill >= 0.4 else "🔴"
                    st.markdown(
                        f"{color} **{criterion}** – {detail}  \n"
                        f"<small>{earned}/{max_pts} pts</small>",
                        unsafe_allow_html=True,
                    )
                    st.progress(min(float(fill), 1.0))
    else:
        st.info("Breakdown not available.")
