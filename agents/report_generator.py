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

logger = logging.getLogger(__name__)


def run(ctx: "AnalysisContext") -> str:
    """Generate the HTML report. Returns the file path."""
    logger.info("▶ ReportGeneratorAgent starting")

    os.makedirs(config.REPORT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(config.REPORT_DIR, f"analysis_{date_str}.html")

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

    data = df[cols].fillna(0).values
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
# HTML RENDERING
# ─────────────────────────────────────────────────────────────────────────────

def _render(ctx: "AnalysisContext", date_str: str) -> str:
    idx_data   = getattr(ctx, "index_data",           {})
    phase_us   = getattr(ctx, "market_phase",         "N/A")
    phase_eu   = getattr(ctx, "eu_market_phase",      "N/A")
    breadth    = getattr(ctx, "breadth_signal",       "N/A")
    us_df      = getattr(ctx, "us_sector_df",         pd.DataFrame())
    eu_df      = getattr(ctx, "eu_sector_df",         pd.DataFrame())
    us_leaders = getattr(ctx, "leading_us_sectors",   [])
    eu_leaders = getattr(ctx, "leading_eu_sectors",   [])
    stocks     = getattr(ctx, "screened_stocks",      [])
    ta         = getattr(ctx, "technical_analyses",   {})
    fa         = getattr(ctx, "fundamental_analyses", {})

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

    # ── Screened stocks table ─────────────────────────────────────────────────
    stock_rows = ""
    for s in stocks[:40]:
        stage_color = ("#a6e3a1" if s.get("stage") == 2 else
                       "#f9e2af" if s.get("stage") == 1 else "#f38ba8")
        stock_rows += f"""
        <tr>
          <td><a href="#{s['ticker']}" style="color:#89b4fa">{s['ticker']}</a></td>
          <td style="font-size:11px">{s.get('name','')[:28]}</td>
          <td style="font-size:11px">{s.get('sector','')}</td>
          <td>{score_badge(s['score'])}</td>
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
            fa_rows += f'<tr><td style="color:#a6adc8">{m["label"]}</td><td style="color:{sig_color};font-weight:bold">{m["value"]}</td></tr>'

        strengths_html = "".join(f"<li>✅ {s_}</li>" for s_ in fa_d.get("strengths", []))
        risks_html     = "".join(f"<li>⚠️ {r}</li>"  for r  in fa_d.get("risks",     []))

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
              <p style="font-size:13px;line-height:1.5;margin-bottom:12px">
                {fa_d.get('narrative','N/A')}
              </p>
              <table class="metrics-table">
                <thead><tr><th>Metric</th><th>Value</th></tr></thead>
                <tbody>{fa_rows}</tbody>
              </table>
              <div style="margin-top:12px">
                <strong style="color:#a6e3a1">Strengths</strong>
                <ul style="font-size:12px;margin:4px 0 12px 16px">{strengths_html}</ul>
                <strong style="color:#f38ba8">Risks</strong>
                <ul style="font-size:12px;margin:4px 0 0 16px">{risks_html}</ul>
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

<!-- ── 2. Sector Rotation ─────────────────────────────────────────── -->
<section>
  <h2>🔄 Sector Rotation</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;flex-wrap:wrap">
    <div>{img(us_heatmap)}</div>
    <div>{img(eu_heatmap)}</div>
  </div>
</section>

<!-- ── 3. Screened Candidates ─────────────────────────────────────── -->
<section>
  <h2>🎯 Screened Candidates (Felix Prehn Score)</h2>
  {img(rs_chart)}
  <div class="table-wrap" style="margin-top:16px">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Name</th><th>Sector</th><th>Score</th>
        <th>Stage</th><th>1M</th><th>3M</th><th>1Y</th>
        <th>RS</th><th>RSI</th><th>P/E</th><th>EPS↑</th><th>Rating</th>
      </tr></thead>
      <tbody>{stock_rows}</tbody>
    </table>
  </div>
  <p style="color:var(--subtext);font-size:11px;margin-top:8px">
    Score 0–100 · Stage: S2=Advancing (Felix's sweet spot) · RS=Relative Strength vs S&amp;P 500
  </p>
</section>

<!-- ── 4. Detailed Stock Analyses ────────────────────────────────── -->
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
