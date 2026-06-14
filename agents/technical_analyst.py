"""
Agent 4 – Technical Analyst
Performs deep technical analysis on the top screened candidates.
Generates chart images (embedded as base64 in the HTML report).
"""

import base64
import io
import logging
from typing import Dict, Any, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")   # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

import config

logger = logging.getLogger(__name__)

CHART_WIDTH  = 14
CHART_HEIGHT = 8


def run(ctx: "AnalysisContext") -> None:
    logger.info("▶ TechnicalAnalystAgent starting – analysing top %d stocks", config.MAX_DETAIL_STOCKS)

    top = (ctx.screened_stocks or [])[:config.MAX_DETAIL_STOCKS]
    ta_results: Dict[str, Dict[str, Any]] = {}

    for item in top:
        ticker = item["ticker"]
        try:
            df   = item.get("_df")
            snap = item.get("_snap", {})
            chart_b64 = _build_chart(ticker, df, item.get("name", ""))
            ta_results[ticker] = {
                "chart_b64":     chart_b64,
                "snapshot":      snap,
                "interpretation": _interpret(snap),
            }
        except Exception as exc:
            logger.warning("TA chart failed for %s: %s", ticker, exc)
            ta_results[ticker] = {"chart_b64": None, "snapshot": {}, "interpretation": "Chart unavailable"}

    ctx.technical_analyses = ta_results
    logger.info("✔ TechnicalAnalystAgent done")


# ─────────────────────────────────────────────────────────────────────────────
# CHART GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _build_chart(ticker: str, df: Optional[pd.DataFrame], name: str = "") -> Optional[str]:
    """Generate a 3-panel chart and return as base64-encoded PNG string."""
    if df is None or len(df) < 50:
        return None

    # Use last 52 weeks
    plot_df = df.tail(252).copy()

    fig = plt.figure(figsize=(CHART_WIDTH, CHART_HEIGHT), facecolor="#1e1e2e")
    gs = gridspec.GridSpec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)

    ax1 = fig.add_subplot(gs[0])   # Price + MAs
    ax2 = fig.add_subplot(gs[1], sharex=ax1)   # MACD
    ax3 = fig.add_subplot(gs[2], sharex=ax1)   # Volume

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#1e1e2e")
        ax.tick_params(colors="#cdd6f4", labelsize=8)
        ax.yaxis.label.set_color("#cdd6f4")
        for spine in ax.spines.values():
            spine.set_edgecolor("#313244")

    dates = plot_df.index

    # ── Panel 1: Price + MAs ─────────────────────────────────────────────────
    ax1.plot(dates, plot_df["Close"], color="#cdd6f4", lw=1.2, label="Price", zorder=3)
    _plot_ma(ax1, plot_df, dates, "MA50",  "#a6e3a1", "MA50")
    _plot_ma(ax1, plot_df, dates, "MA150", "#f9e2af", "MA150")
    _plot_ma(ax1, plot_df, dates, "MA200", "#f38ba8", "MA200")

    # Bollinger Bands (shaded)
    if "BB_Upper" in plot_df.columns:
        ax1.fill_between(dates, plot_df["BB_Lower"], plot_df["BB_Upper"],
                         alpha=0.08, color="#89b4fa", zorder=1)

    ax1.set_ylabel("Price", color="#cdd6f4", fontsize=9)
    ax1.legend(loc="upper left", fontsize=7, facecolor="#313244",
               labelcolor="#cdd6f4", framealpha=0.7)
    ax1.set_title(f"{ticker}  {name}", color="#cba6f7", fontsize=11, pad=8)
    ax1.grid(color="#313244", linestyle="--", alpha=0.4)
    plt.setp(ax1.get_xticklabels(), visible=False)

    # ── Panel 2: MACD ────────────────────────────────────────────────────────
    if "MACD" in plot_df.columns:
        ax2.plot(dates, plot_df["MACD"],        color="#89b4fa", lw=1, label="MACD")
        ax2.plot(dates, plot_df["MACD_Signal"], color="#f38ba8", lw=1, label="Signal")
        hist = plot_df["MACD_Hist"]
        colors = ["#a6e3a1" if v >= 0 else "#f38ba8" for v in hist]
        ax2.bar(dates, hist, color=colors, alpha=0.6, width=1)
        ax2.axhline(0, color="#585b70", lw=0.8)
        ax2.set_ylabel("MACD", color="#cdd6f4", fontsize=9)
        ax2.legend(loc="upper left", fontsize=7, facecolor="#313244",
                   labelcolor="#cdd6f4", framealpha=0.7)
        ax2.grid(color="#313244", linestyle="--", alpha=0.4)
    plt.setp(ax2.get_xticklabels(), visible=False)

    # ── Panel 3: Volume ──────────────────────────────────────────────────────
    vol = plot_df["Volume"]
    vol_ma = plot_df.get("Vol_MA20", vol.rolling(20).mean())
    vol_colors = ["#a6e3a1" if c >= o else "#f38ba8"
                  for c, o in zip(plot_df["Close"], plot_df["Open"])]
    ax3.bar(dates, vol, color=vol_colors, alpha=0.7, width=1)
    ax3.plot(dates, vol_ma, color="#fab387", lw=1)
    ax3.set_ylabel("Volume", color="#cdd6f4", fontsize=9)
    ax3.grid(color="#313244", linestyle="--", alpha=0.4)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax3.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    fig.patch.set_alpha(0)
    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _plot_ma(ax, df, dates, col, color, label):
    if col in df.columns:
        series = df[col]
        ax.plot(dates, series, color=color, lw=1, linestyle="--",
                alpha=0.85, label=label, zorder=2)


# ─────────────────────────────────────────────────────────────────────────────
# TEXT INTERPRETATION
# ─────────────────────────────────────────────────────────────────────────────

def _interpret(snap: Dict[str, Any]) -> str:
    """Generate a short human-readable TA narrative."""
    lines: List[str] = []

    stage = snap.get("stage", 0)
    stage_names = {1: "Stage 1 (Basing)", 2: "Stage 2 (Advancing)",
                   3: "Stage 3 (Topping)", 4: "Stage 4 (Declining)"}
    lines.append(f"**Stage:** {stage_names.get(stage, 'Unknown')}")

    # MA context
    ma_str = []
    if snap.get("above_ma200"): ma_str.append("above MA200 ✓")
    else: ma_str.append("below MA200 ✗")
    if snap.get("above_ma150"): ma_str.append("above MA150 ✓")
    if snap.get("above_ma50"):  ma_str.append("above MA50 ✓")
    lines.append("**MAs:** " + ", ".join(ma_str))

    # RSI
    rsi = snap.get("rsi")
    if rsi:
        zone = ("overbought >80" if rsi > 80 else
                "strong 70–80"   if rsi > 70 else
                "bullish 50–70"  if rsi > 50 else
                "neutral 40–50"  if rsi > 40 else
                "oversold <40")
        lines.append(f"**RSI:** {rsi:.1f} – {zone}")

    # MACD
    if snap.get("macd_bullish"):
        lines.append("**MACD:** Bullish – line above signal")
    else:
        lines.append("**MACD:** Bearish – line below signal")

    # 52W proximity
    pct = snap.get("pct_from_52w_high")
    if pct is not None:
        if pct >= -5:
            lines.append(f"**Price:** Near 52W high ({pct:.1f}%) – leadership strength")
        elif pct >= -15:
            lines.append(f"**Price:** {pct:.1f}% from 52W high – consolidating")
        else:
            lines.append(f"**Price:** {pct:.1f}% from 52W high – recovery needed")

    # Relative strength
    rs = snap.get("rs_vs_benchmark")
    if rs is not None:
        lines.append(f"**RS vs S&P 500 (1Y):** {rs:+.1f}% – {'outperforming ✓' if rs > 0 else 'underperforming'}")

    return "\n".join(lines)
