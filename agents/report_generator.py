"""
Agent 6 – Report Generator
Assembles all agent outputs into a self-contained HTML report.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

import config
from tools.market_data import get_cache_summary

logger = logging.getLogger(__name__)


def run(ctx: "AnalysisContext") -> str:
    """Generate the HTML report. Returns the file path."""
    logger.info("▶ ReportGeneratorAgent starting")

    os.makedirs(config.REPORT_DIR, exist_ok=True)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    file_stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    universe = (getattr(ctx, "universe_name", "broad") or "broad").lower()
    filename = os.path.join(config.REPORT_DIR, f"analysis_{universe}_{file_stamp}.html")

    html = _render(ctx, date_str)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("✔ Report saved: %s", filename)
    return filename


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR HEATMAP
# ─────────────────────────────────────────────────────────────────────────────

def _sector_heatmap_b64(df: pd.DataFrame, title: str) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols = [c for c in ["1wk", "1mo", "3mo", "6mo", "1y"] if c in df.columns]
    if not cols:
        return None

    data = df[cols].fillna(0).astype(float).values
    sectors = list(df.index)

    fig, ax = plt.subplots(figsize=(9, max(3, len(sectors) * 0.45)),
                           facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")

    vmax = max(abs(data.max()), abs(data.min()), 5)
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto",
                   vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, color="#cdd6f4", fontsize=9)
    ax.set_yticks(range(len(sectors)))
    ax.set_yticklabels(sectors, color="#cdd6f4", fontsize=9)

    for i in range(len(sectors)):
        for j in range(len(cols)):
            v = data[i, j]
            ax.text(j, i, f"{v:+.1f}%", ha="center", va="center",
                    fontsize=7.5, color="black" if abs(v) < vmax * 0.6 else "white",
                    fontweight="bold")

    ax.set_title(title, color="#cba6f7", fontsize=11, pad=10)
    plt.colorbar(im, ax=ax, label="Return %").ax.tick_params(colors="#cdd6f4")
    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _bar_chart_b64(labels, values, colors, title, xlabel="") -> Optional[str]:
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")
    bars = ax.barh(labels, values, color=colors, alpha=0.85, height=0.6)
    ax.axvline(0, color="#585b70", lw=0.8)
    ax.set_xlabel(xlabel, color="#cdd6f4", fontsize=9)
    ax.set_title(title, color="#cba6f7", fontsize=11)
    ax.tick_params(colors="#cdd6f4", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#313244")
    for bar, val in zip(bars, values):
        ax.text(val + (0.3 if val >= 0 else -0.3), bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}%", va="center", ha="left" if val >= 0 else "right",
                color="#cdd6f4", fontsize=7.5)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO SECTION
# ─────────────────────────────────────────────────────────────────────────────

def _portfolio_section(portfolio: List[Dict[str, Any]]) -> str:
    """
    Generate portfolio analysis HTML section.
    Shows holdings with performance, scores, and buy/hold/sell recommendations.
    """
    if not portfolio:
        return ""
    
    def rec_badge(rec: str) -> str:
        if rec == "RESTOCK":
            color = "#a6e3a1"
            bg = "#1e3a2a"
        elif rec == "SELL":
            color = "#f38ba8"
            bg = "#3a1e27"
        else:  # HOLD
            color = "#f9e2af"
            bg = "#3a3219"
        return f'<span style="background:{bg};color:{color};padding:4px 10px;border-radius:12px;font-weight:bold;font-size:11px">{rec}</span>'
    
    def pct_color(v: float) -> str:
        if v > 0:
            return "#a6e3a1"
        elif v < 0:
            return "#f38ba8"
        else:
            return "#cdd6f4"
    
    # Portfolio summary
    total_gain = sum(h.get("unrealized_gain", 0) for h in portfolio)
    total_invested = sum(h.get("quantity", 0) * h.get("avg_cost", 0) for h in portfolio)
    total_market_value = sum(h.get("quantity", 0) * h.get("current_price", 0) for h in portfolio)
    portfolio_pct_gain = (total_gain / total_invested * 100) if total_invested > 0 else 0
    holdings_count = len(portfolio)
    restock_count = sum(1 for h in portfolio if h.get("recommendation") == "RESTOCK")
    hold_count = sum(1 for h in portfolio if h.get("recommendation") == "HOLD")
    sell_count = sum(1 for h in portfolio if h.get("recommendation") == "SELL")
    
    # Generate holdings table
    holdings_rows = ""
    for h in sorted(portfolio, key=lambda x: x.get("current_price", 0) * x.get("quantity", 0), reverse=True):
        position_value = h.get("current_price", 0) * h.get("quantity", 0)
        position_pct = (position_value / total_market_value * 100) if total_market_value > 0 else 0
        
        score = h.get("blended_score", 0)
        score_color = ("#a6e3a1" if score >= 72 else
                      "#94e2d5" if score >= 58 else
                      "#f9e2af" if score >= 42 else "#f38ba8")
        
        percentile = h.get("percentile", 0)
        
        holdings_rows += f"""
        <tr>
          <td><strong>{h['ticker']}</strong></td>
          <td style="text-align:right">{h.get('quantity', 0):.0f}</td>
          <td style="text-align:right">${h.get('avg_cost', 0):.2f}</td>
          <td style="text-align:right">${h.get('current_price', 0):.2f}</td>
          <td style="text-align:right;color:{pct_color(h.get('gain_pct', 0))}">{h.get('gain_pct', 0):+.1f}%</td>
          <td style="text-align:right">${position_value:,.0f}</td>
          <td style="text-align:right;font-size:11px">{position_pct:.1f}%</td>
          <td style="text-align:right"><span style="background:{score_color};color:#1e1e2e;padding:2px 6px;border-radius:8px;font-weight:bold;font-size:11px">{score:.0f}</span></td>
          <td style="text-align:right;font-size:11px;color:#a6adc8">{percentile:.0f}%ile</td>
          <td>{rec_badge(h.get('recommendation', 'HOLD'))}</td>
          <td style="font-size:11px;color:#a6adc8">{h.get('reason', 'N/A')}</td>
        </tr>"""
    
    return f"""
<section>
  <h2>💼 Portfolio Analysis</h2>
  <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:16px;margin-bottom:20px">
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:10px;padding:12px">
      <p style="color:var(--subtext);font-size:12px">Total Invested</p>
      <p style="font-size:18px;font-weight:bold">${total_invested:,.0f}</p>
    </div>
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:10px;padding:12px">
      <p style="color:var(--subtext);font-size:12px">Market Value</p>
      <p style="font-size:18px;font-weight:bold">${total_market_value:,.0f}</p>
    </div>
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:10px;padding:12px">
      <p style="color:var(--subtext);font-size:12px">Unrealized P&L</p>
      <p style="font-size:18px;font-weight:bold;color:{pct_color(total_gain)}">${total_gain:+,.0f}</p>
    </div>
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:10px;padding:12px">
      <p style="color:var(--subtext);font-size:12px">Return %</p>
      <p style="font-size:18px;font-weight:bold;color:{pct_color(portfolio_pct_gain)}">{portfolio_pct_gain:+.2f}%</p>
    </div>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">
    <span class="chip chip-green">RESTOCK: {restock_count}</span>
    <span class="chip chip-yellow">HOLD: {hold_count}</span>
    <span class="chip chip-red">SELL: {sell_count}</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Qty</th><th>Avg Cost</th><th>Current</th><th>Gain %</th>
        <th>Position Value</th><th>% Port</th><th>Score</th><th>Percentile</th><th>Recommendation</th><th>Reason</th>
      </tr></thead>
      <tbody>{holdings_rows}</tbody>
    </table>
  </div>
  <p style="color:var(--subtext);font-size:11px;margin-top:8px">
    Score compared to screened universe ({holdings_count} holdings) · Percentile shows ranking vs. screened candidates
  </p>
</section>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML RENDERING
# ─────────────────────────────────────────────────────────────────────────────

def _render(ctx: "AnalysisContext", date_str: str) -> str:
    idx_data   = getattr(ctx, "index_data",           {})
    phase_us   = getattr(ctx, "market_phase",         "N/A")
    phase_eu   = getattr(ctx, "eu_market_phase",      "N/A")
    breadth    = getattr(ctx, "breadth_signal",       "N/A")
    market_assessment = getattr(ctx, "market_assessment", {})
    us_df      = getattr(ctx, "us_sector_df",         pd.DataFrame())
    eu_df      = getattr(ctx, "eu_sector_df",         pd.DataFrame())
    us_leaders = getattr(ctx, "leading_us_sectors",   [])
    eu_leaders = getattr(ctx, "leading_eu_sectors",   [])
    stocks     = getattr(ctx, "screened_stocks",      [])
    ta         = getattr(ctx, "technical_analyses",   {})
    fa         = getattr(ctx, "fundamental_analyses", {})
    portfolio  = getattr(ctx, "portfolio_analysis",   [])
    cache_summary = get_cache_summary()

    # ── Charts ───────────────────────────────────────────────────────────────
    us_heatmap = _sector_heatmap_b64(us_df, "US Sector Performance (%)")
    eu_heatmap = _sector_heatmap_b64(eu_df, "EU Sector Performance (%)")

    # Index bar chart (YTD)
    idx_labels = [k for k, v in idx_data.items() if v.get("ytd_chg") is not None]
    idx_values = [idx_data[k]["ytd_chg"] for k in idx_labels]
    idx_colors = ["#a6e3a1" if v >= 0 else "#f38ba8" for v in idx_values]
    idx_chart  = _bar_chart_b64(idx_labels, idx_values, idx_colors,
                                "Global Indices – YTD Performance", "YTD %")

    # Top stocks RS bar chart
    top20 = stocks[:20]
    rs_labels = [s["ticker"] for s in top20 if s.get("rs_bench") is not None]
    rs_vals   = [s["rs_bench"] for s in top20 if s.get("rs_bench") is not None]
    rs_colors = ["#a6e3a1" if v >= 0 else "#f38ba8" for v in rs_vals]
    rs_chart  = _bar_chart_b64(rs_labels, rs_vals, rs_colors,
                               "Relative Strength vs S&P 500 (1Y)", "RS %")

    def img(b64):
        if not b64:
            return "<p style='color:#6c7086'>Chart unavailable</p>"
        return f'<img src="data:image/png;base64,{b64}" style="max-width:100%;border-radius:8px;">'

    def pct(v):
        if v is None: return "–"
        color = "#a6e3a1" if v > 0 else "#f38ba8" if v < 0 else "#cdd6f4"
        return f'<span style="color:{color}">{v:+.2f}%</span>'

    def score_badge(sc):
        color = ("#a6e3a1" if sc >= 72 else
                 "#94e2d5" if sc >= 58 else
                 "#f9e2af" if sc >= 42 else "#f38ba8")
        return f'<span style="background:{color};color:#1e1e2e;padding:2px 8px;border-radius:12px;font-weight:bold">{sc}</span>'

    def single_stock_badge(assessment: Dict[str, Any]) -> str:
      sc = assessment.get("score") if assessment else None
      mx = assessment.get("max_score", 9) if assessment else 9
      if sc is None:
        return '<span style="color:#6c7086">N/A</span>'
      color = "#a6e3a1" if sc >= 7 else "#f9e2af" if sc >= 4 else "#f38ba8"
      return f'<span style="background:{color};color:#1e1e2e;padding:2px 8px;border-radius:12px;font-weight:bold">{sc}/{mx}</span>'

    def fmt_signed(v: Optional[float]) -> str:
      if v is None:
        return "N/A"
      return f"{v:+.2f}%"

    def regime_chip(regime: str) -> str:
      if regime == "RISK-ON":
        klass = "chip-green"
      elif regime == "BALANCED":
        klass = "chip-yellow"
      else:
        klass = "chip-red"
      return f'<div class="chip {klass}">🧭 Regime: {regime}</div>'

    # ── Indices table ─────────────────────────────────────────────────────────
    idx_rows = ""
    for name, d in idx_data.items():
        if "error" in d:
            continue
        ma50_icon  = "✓" if d.get("above_ma50")  else "✗"
        ma200_icon = "✓" if d.get("above_ma200") else "✗"
        idx_rows += f"""
        <tr>
          <td>{name}</td>
          <td>{d.get('last', '–')}</td>
          <td>{pct(d.get('1d_chg'))}</td>
          <td>{pct(d.get('1w_chg'))}</td>
          <td>{pct(d.get('1m_chg'))}</td>
          <td>{pct(d.get('ytd_chg'))}</td>
          <td>{pct(d.get('1y_chg'))}</td>
          <td style="color:{'#a6e3a1' if d.get('above_ma200') else '#f38ba8'}">{ma200_icon}</td>
          <td style="color:{'#a6e3a1' if d.get('above_ma50') else '#f38ba8'}">{ma50_icon}</td>
        </tr>"""

    regime = market_assessment.get("regime", "N/A")
    market_score = market_assessment.get("score")
    market_max = market_assessment.get("max_score", 12)
    guidance = market_assessment.get("guidance", "")
    comp = market_assessment.get("components", {})
    comp_rows = "".join(
      f"<tr><td>{k.replace('_', ' ').title()}</td><td>{v}</td></tr>"
      for k, v in comp.items()
    )

    oil_chg = market_assessment.get("oil_6w_chg")
    yld_chg = market_assessment.get("yield10_6w_chg")

    cache_ohlcv = cache_summary.get("ohlcv", {})
    cache_info = cache_summary.get("info", {})
    cache_ttl = cache_summary.get("ttl", {})

    cache_rows = f"""
      <tr><td>OHLCV cache hit rate</td><td>{cache_ohlcv.get('hit_rate_pct', 0.0):.1f}%</td></tr>
      <tr><td>OHLCV memory hits</td><td>{cache_ohlcv.get('memory_hits', 0)}</td></tr>
      <tr><td>OHLCV disk hits</td><td>{cache_ohlcv.get('disk_hits', 0)}</td></tr>
      <tr><td>OHLCV Yahoo requests</td><td>{cache_ohlcv.get('yahoo_requests', 0)}</td></tr>
      <tr><td>OHLCV Yahoo success</td><td>{cache_ohlcv.get('yahoo_success', 0)}</td></tr>
      <tr><td>OHLCV Yahoo empty</td><td>{cache_ohlcv.get('yahoo_empty', 0)}</td></tr>
      <tr><td>OHLCV errors</td><td>{cache_ohlcv.get('errors', 0)}</td></tr>
      <tr><td>OHLCV disk writes</td><td>{cache_ohlcv.get('disk_writes', 0)}</td></tr>
      <tr><td>Info cache hit rate</td><td>{cache_info.get('hit_rate_pct', 0.0):.1f}%</td></tr>
      <tr><td>Info memory hits</td><td>{cache_info.get('memory_hits', 0)}</td></tr>
      <tr><td>Info disk hits</td><td>{cache_info.get('disk_hits', 0)}</td></tr>
      <tr><td>Info Yahoo requests</td><td>{cache_info.get('yahoo_requests', 0)}</td></tr>
      <tr><td>Info Yahoo success</td><td>{cache_info.get('yahoo_success', 0)}</td></tr>
      <tr><td>Info errors</td><td>{cache_info.get('errors', 0)}</td></tr>
      <tr><td>Info disk writes</td><td>{cache_info.get('disk_writes', 0)}</td></tr>
      <tr><td>Memory TTL</td><td>{cache_ttl.get('memory_seconds', 0)} sec</td></tr>
      <tr><td>OHLCV disk TTL</td><td>{cache_ttl.get('ohlcv_disk_seconds', 0)} sec</td></tr>
      <tr><td>Info disk TTL</td><td>{cache_ttl.get('info_disk_seconds', 0)} sec</td></tr>
      <tr><td>Cache path</td><td style="font-size:11px;color:var(--subtext)">{cache_summary.get('cache_root', '')}</td></tr>
    """

    # ── Screened stocks table ─────────────────────────────────────────────────
    stock_rows = ""
    for s in stocks[:40]:
        stage_color = ("#a6e3a1" if s.get("stage") == 2 else
                       "#f9e2af" if s.get("stage") == 1 else "#f38ba8")
        ss_assessment = s.get("single_stock_assessment", {})
        blended = s.get("blended_score")
        blended_txt = f"{blended:.1f}" if blended is not None else "N/A"
        stock_rows += f"""
        <tr>
          <td><a href="#{s['ticker']}" style="color:#89b4fa">{s['ticker']}</a></td>
          <td style="font-size:11px">{s.get('name','')[:28]}</td>
          <td style="font-size:11px">{s.get('sector','')}</td>
          <td>{score_badge(s['score'])}</td>
          <td>{blended_txt}</td>
          <td>{single_stock_badge(ss_assessment)}</td>
          <td style="color:{stage_color}">S{s.get('stage','?')}</td>
          <td>{pct(s.get('ret_1m'))}</td>
          <td>{pct(s.get('ret_3m'))}</td>
          <td>{pct(s.get('ret_1y'))}</td>
          <td>{pct(s.get('rs_bench'))}</td>
          <td>{s.get('rsi') and f"{s['rsi']:.0f}" or "–"}</td>
          <td>{s.get('pe') and f"{s['pe']:.0f}" or "–"}</td>
          <td>{s.get('eps_growth') is not None and f"{s['eps_growth']*100:.0f}%" or "–"}</td>
          <td style="font-size:11px">{s.get('rating','')}</td>
        </tr>"""

    # ── Per-stock detail sections ─────────────────────────────────────────────
    detail_sections = ""
    for s in stocks[:config.MAX_DETAIL_STOCKS]:
        t = s["ticker"]
        ta_d = ta.get(t, {})
        fa_d = fa.get(t, {})

        chart_html = img(ta_d.get("chart_b64"))
        ta_interp  = (ta_d.get("interpretation") or "").replace("\n", "<br>")

        # FA metrics table
        fa_rows = ""
        for m in fa_d.get("metrics", []):
            sig_color = {"good": "#a6e3a1", "warn": "#f9e2af", "bad": "#f38ba8"}.get(
                m.get("signal", "neutral"), "#cdd6f4"
            )
            fa_rows += (
                f'<tr><td style="color:#a6adc8">{m["label"]}</td>'
                f'<td style="color:{sig_color};font-weight:bold">{m["value"]}</td>'
                f'<td style="font-size:11px;color:#bac2de">{m.get("thresholds", "")}</td></tr>'
            )

        tp = fa_d.get("threshold_profile", {})
        tp_text = ""
        if tp:
            tp_text = (
                f"Threshold context: style={tp.get('style', 'n/a')} · "
            f"cap={tp.get('cap_bucket', 'n/a')} · vol={tp.get('volatility', 'n/a')} · "
            f"industry_rule={tp.get('industry_rule', 'none')}"
            )

        strengths_html = "".join(f"<li>✅ {s_}</li>" for s_ in fa_d.get("strengths", []))
        risks_html     = "".join(f"<li>⚠️ {r}</li>"  for r  in fa_d.get("risks",     []))
        ss_assessment = s.get("single_stock_assessment", {})
        ss_checks = ss_assessment.get("checks", {})
        ss_rows = "".join(
          f"<tr><td style='color:#a6adc8'>{name.replace('_', ' ').title()}</td>"
          f"<td>{data.get('points', 0)}</td><td>{data.get('label', 'N/A')}</td></tr>"
          for name, data in ss_checks.items()
        )

        detail_sections += f"""
        <div id="{t}" class="stock-detail">
          <div class="stock-header">
            <h2>{t} – {s.get('name','')}
              <span class="badge" style="margin-left:12px">{score_badge(s['score'])}</span>
              <span style="font-size:14px;margin-left:8px;color:#cba6f7">{s.get('rating','')}</span>
            </h2>
            <p style="color:#a6adc8;font-size:12px">
              {s.get('sector','')} · {s.get('industry','')} · {s.get('country','')}
            </p>
          </div>
          <div class="two-col">
            <div>
              <h3>Technical Analysis</h3>
              {chart_html}
              <div class="ta-interp">{ta_interp}</div>
            </div>
            <div>
              <h3>Fundamental Analysis</h3>
              <p style="font-size:11px;color:#a6adc8;margin-bottom:8px">{tp_text}</p>
              <p style="font-size:13px;line-height:1.5;margin-bottom:12px">
                {fa_d.get('narrative','N/A')}
              </p>
              <table class="metrics-table">
                <thead><tr><th>Metric</th><th>Value</th><th>Thresholds (Good / Mediocre / Bad)</th></tr></thead>
                <tbody>{fa_rows}</tbody>
              </table>
              <div style="margin-top:12px">
                <strong style="color:#a6e3a1">Strengths</strong>
                <ul style="font-size:12px;margin:4px 0 12px 16px">{strengths_html}</ul>
                <strong style="color:#f38ba8">Risks</strong>
                <ul style="font-size:12px;margin:4px 0 0 16px">{risks_html}</ul>
              </div>
              <div style="margin-top:14px">
                <strong style="color:#89b4fa">3-Filter Single-Stock Assessment</strong>
                <p style="font-size:12px;color:#a6adc8;margin:4px 0 8px 0">
                  {single_stock_badge(ss_assessment)} · {ss_assessment.get('rating', 'N/A')}
                </p>
                <table class="metrics-table">
                  <thead><tr><th>Filter</th><th>Pts</th><th>Reading</th></tr></thead>
                  <tbody>{ss_rows}</tbody>
                </table>
              </div>
            </div>
          </div>
        </div>"""

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market Analysis – {date_str}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #1e1e2e; --surface: #313244; --surface2: #45475a;
    --text: #cdd6f4; --subtext: #a6adc8; --accent: #cba6f7;
    --green: #a6e3a1; --red: #f38ba8; --yellow: #f9e2af; --blue: #89b4fa;
  }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, "Segoe UI", sans-serif;
          font-size: 14px; line-height: 1.5; padding: 0; }}
  header {{ background: linear-gradient(135deg, #181825 0%, #313244 100%);
            padding: 28px 40px; border-bottom: 2px solid var(--surface2); }}
  header h1 {{ font-size: 26px; color: var(--accent); }}
  header p  {{ color: var(--subtext); font-size: 13px; margin-top: 4px; }}
  .phase-chips {{ display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }}
  .chip {{ padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
  .chip-green  {{ background: #1e3a2a; color: var(--green);  border: 1px solid var(--green); }}
  .chip-yellow {{ background: #3a3219; color: var(--yellow); border: 1px solid var(--yellow); }}
  .chip-red    {{ background: #3a1e27; color: var(--red);    border: 1px solid var(--red); }}
  .chip-blue   {{ background: #1e2d3a; color: var(--blue);   border: 1px solid var(--blue); }}
  main {{ max-width: 1400px; margin: 0 auto; padding: 30px 24px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{ font-size: 20px; color: var(--accent); margin-bottom: 16px; border-bottom: 1px solid var(--surface); padding-bottom: 8px; }}
  h3 {{ font-size: 15px; color: var(--blue); margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: var(--surface); color: var(--accent); padding: 8px 10px; text-align: left; position: sticky; top: 0; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid var(--surface); color: var(--text); }}
  tr:hover td {{ background: var(--surface); }}
  .table-wrap {{ overflow-x: auto; border-radius: 8px; border: 1px solid var(--surface); }}
  .metrics-table {{ font-size: 12px; }}
  .metrics-table th {{ background: #181825; }}
  .stock-detail {{ background: var(--surface); border-radius: 12px; padding: 24px;
                   margin-bottom: 30px; border: 1px solid var(--surface2); }}
  .stock-header h2 {{ border: none; font-size: 18px; padding: 0; margin-bottom: 4px; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 16px; }}
  @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  .ta-interp {{ font-size: 12px; color: var(--subtext); margin-top: 10px; line-height: 1.6; }}
  .leaders {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
  a {{ text-decoration: none; }}
  footer {{ text-align: center; color: var(--subtext); font-size: 11px;
            padding: 20px; border-top: 1px solid var(--surface); }}
</style>
</head>
<body>

<header>
  <h1>📊 Weekend Market Analysis</h1>
  <p>{date_str} · {ctx.universe_name.upper()} universe · {len(stocks)} candidates screened</p>
  <div class="phase-chips">
    <div class="chip {'chip-green' if 'BULL' in phase_us else 'chip-yellow' if 'UPTREND' in phase_us or 'CORR' in phase_us else 'chip-red'}">
      🇺🇸 US: {phase_us}
    </div>
    <div class="chip {'chip-green' if 'BULL' in phase_eu else 'chip-yellow' if 'UPTREND' in phase_eu or 'CORR' in phase_eu else 'chip-red'}">
      🇪🇺 EU: {phase_eu}
    </div>
    <div class="chip {'chip-green' if 'BULL' in breadth else 'chip-yellow' if breadth == 'MIXED' else 'chip-red'}">
      🌍 Breadth: {breadth}
    </div>
    {regime_chip(regime)}
    <div class="chip chip-blue">
      🏆 US Leaders: {', '.join(us_leaders) or 'N/A'}
    </div>
    <div class="chip chip-blue">
      🏆 EU Leaders: {', '.join(eu_leaders) or 'N/A'}
    </div>
  </div>
</header>

<main>

<!-- ── 1. Global Indices ───────────────────────────────────────────── -->
<section>
  <h2>🌐 Global Indices</h2>
  {img(idx_chart)}
  <div class="table-wrap" style="margin-top:16px">
    <table>
      <thead><tr>
        <th>Index</th><th>Last</th><th>1D</th><th>1W</th>
        <th>1M</th><th>YTD</th><th>1Y</th><th>MA200</th><th>MA50</th>
      </tr></thead>
      <tbody>{idx_rows}</tbody>
    </table>
  </div>
</section>

<!-- ── 2. Market Regime Scorecard ───────────────────────────────── -->
<section>
  <h2>🧭 Market Regime Scorecard</h2>
  <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:20px;align-items:start">
    <div class="table-wrap">
      <table>
        <thead><tr><th>Component</th><th>Points</th></tr></thead>
        <tbody>{comp_rows or '<tr><td colspan="2">No assessment data</td></tr>'}</tbody>
      </table>
    </div>
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:10px;padding:14px">
      <p><strong>Regime:</strong> {regime}</p>
      <p><strong>Score:</strong> {market_score if market_score is not None else 'N/A'}/{market_max}</p>
      <p><strong>Oil 6W:</strong> {fmt_signed(oil_chg)}</p>
      <p><strong>10Y Yield 6W:</strong> {fmt_signed(yld_chg)}</p>
      <p style="margin-top:8px;color:var(--subtext)">{guidance or ''}</p>
    </div>
  </div>
</section>

<!-- ── 2.5. Portfolio Analysis (if provided) ─────────────────────────── -->
{_portfolio_section(portfolio) if portfolio else ""}

<!-- ── 2.6. Yahoo Cache Summary ───────────────────────────────────────── -->
<section>
  <h2>🗄️ Yahoo Cache Summary</h2>
  <div class="table-wrap" style="max-width:760px">
    <table>
      <thead><tr><th>Metric</th><th>Value</th></tr></thead>
      <tbody>{cache_rows}</tbody>
    </table>
  </div>
  <p style="color:var(--subtext);font-size:11px;margin-top:8px">
    Higher cache hit rates mean fewer Yahoo requests and lower likelihood of rate limiting.
  </p>
</section>

<!-- ── 3. Sector Rotation ─────────────────────────────────────────── -->
<section>
  <h2>🔄 Sector Rotation</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;flex-wrap:wrap">
    <div>{img(us_heatmap)}</div>
    <div>{img(eu_heatmap)}</div>
  </div>
</section>

<!-- ── 4. Screened Candidates ─────────────────────────────────────── -->
<section>
  <h2>🎯 Screened Candidates (Felix Prehn Score)</h2>
  {img(rs_chart)}
  <div class="table-wrap" style="margin-top:16px">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Name</th><th>Sector</th><th>Score</th>
        <th>Blended</th><th>3F</th><th>Stage</th><th>1M</th><th>3M</th><th>1Y</th>
        <th>RS</th><th>RSI</th><th>P/E</th><th>EPS↑</th><th>Rating</th>
      </tr></thead>
      <tbody>{stock_rows}</tbody>
    </table>
  </div>
  <p style="color:var(--subtext);font-size:11px;margin-top:8px">
    Score 0–100 · Blended=Prehn score with 3-filter overlay · 3F=Cash runway, institutional support, revenue quality
  </p>
</section>

<!-- ── 5. Detailed Stock Analyses ────────────────────────────────── -->
<section>
  <h2>🔍 Detailed Analysis – Top {config.MAX_DETAIL_STOCKS} Candidates</h2>
  {detail_sections}
</section>

</main>
<footer>
  Generated by the Felix Prehn Collaborative Analysis System · {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
  For informational purposes only – not financial advice.
</footer>
</body>
</html>"""
