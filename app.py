"""
app.py – Streamlit frontend for the Felix Prehn Market Analysis System
Run with:   streamlit run app.py
"""

import base64
import os
import sys
from datetime import datetime
from typing import List, Optional

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


def _mini_chart(df: Optional[pd.DataFrame], days: int = 90) -> Optional[bytes]:
    """
    Compact sparkline showing price line + MA50 dashed.
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

    fig, ax = plt.subplots(figsize=(3.2, 1.15), facecolor="#1e1e2e")
    ax.set_facecolor("#1e1e2e")

    dates     = plot_df.index
    net_chg   = float(close.iloc[-1]) - float(close.iloc[0])
    line_clr  = "#a6e3a1" if net_chg >= 0 else "#f38ba8"

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

    universe = st.selectbox(
        "Universe",
        ["focused", "broad", "dax", "sp500", "nasdaq", "custom"],
        index=0,
        help="focused ~150 tickers (5–15 min) · broad ~700 (30–60 min)",
    )

    custom_input = st.text_area(
        "Extra Tickers (one per line)",
        value="\n".join(config.CUSTOM_WATCHLIST),
        height=110,
        placeholder="e.g.\nHIMS\nASML.AS\nIFX.DE",
        help="Appended to the chosen universe",
    )

    max_detail = st.slider(
        "Stocks to deep-analyse",
        min_value=5, max_value=40, value=config.MAX_DETAIL_STOCKS,
        help="Top N candidates get full TA chart + FA breakdown",
    )

    st.divider()
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

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
                    use_container_width=True,
                )

    st.divider()
    st.caption("Data: Yahoo Finance  \nNot financial advice.")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if run_btn:
    custom_tickers = [t.strip().upper() for t in custom_input.splitlines() if t.strip()]

    universe_map = {
        "dax":    config.DAX_40,
        "sp500":  config.SP500_TOP100,
        "nasdaq": config.NASDAQ_100_SELECTED,
        "custom": custom_tickers or config.CUSTOM_WATCHLIST,
    }
    base_tickers = universe_map.get(universe, config.get_universe(universe))
    all_tickers  = list(dict.fromkeys(base_tickers + custom_tickers))

    # Propagate UI slider to config so all agents respect it
    config.MAX_DETAIL_STOCKS = max_detail

    ctx = AnalysisContext(universe_name=universe, universe_tickers=all_tickers)

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
        st.write(f"   ✓ {len(ctx.screened_stocks)} candidates after screening")

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
        "Select a **universe** in the sidebar and click **🚀 Run Analysis** to launch the "
        "5-agent pipeline across all markets tradeable from Germany."
    )
    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📋 Universe Coverage")
        st.markdown("""
| Universe | Exchanges |
|---|---|
| DAX 40 | XETRA – German large caps |
| MDAX | XETRA – German mid caps |
| Euro Stoxx ex-DE | Amsterdam · Paris · Madrid · Milan |
| Swiss | SIX (NESN, NOVN, ROG…) |
| FTSE 100 | London Stock Exchange |
| S&P 500 Top 100 | NYSE / NASDAQ |
| NASDAQ 100 | NASDAQ |
| Custom | Your own tickers |
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
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS VIEW
# ─────────────────────────────────────────────────────────────────────────────

ctx    = st.session_state.ctx
stocks = ctx.screened_stocks or []

# ── Top KPI row ───────────────────────────────────────────────────────────────
st.title(f"📊 Analysis – {st.session_state.run_time}")

k1, k2, k3, k4, k5 = st.columns(5)
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
st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "🌐 Market Overview",
    "🔄 Sector Rotation",
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

        pct_cols = ["1D%", "1W%", "1M%", "YTD%", "1Y%"]
        styled = (
            df_idx.style
            .map(_pct_style, subset=pct_cols)
            .map(_ma_style,  subset=["MA200", "MA50"])
            .format({c: "{:+.2f}%" for c in pct_cols}, na_rep="–")
            .format({"Last": "{:.2f}"}, na_rep="–")
        )
        st.dataframe(styled, use_container_width=True, height=380)

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
        st.markdown("##### Sparklines – Price & MA50 (3 months)")
        etf_items = list(etf_map.items())
        COLS = 4
        for i in range(0, len(etf_items), COLS):
            chunk     = etf_items[i : i + COLS]
            grid_cols = st.columns(COLS)
            for gc, (name, etf) in zip(grid_cols, chunk):
                df_etf = fetch_ohlcv(etf, period="6mo")
                img    = _mini_chart(df_etf)
                ret_1m = None
                if df_rank is not None and name in df_rank.index and "1mo" in df_rank.columns:
                    v = df_rank.loc[name, "1mo"]
                    ret_1m = None if pd.isna(v) else float(v)
                is_leader  = name in leaders
                leader_tag = " 🏆" if is_leader else ""
                pct_str    = f"{ret_1m:+.1f}%" if ret_1m is not None else "–"
                arrow      = "🟢" if ret_1m and ret_1m > 0 else "🔴" if ret_1m and ret_1m < 0 else "⚪"
                with gc:
                    if img:
                        st.image(img, use_column_width=True)
                    st.caption(f"{arrow} **{name}**{leader_tag}  \n1M: {pct_str}")

    _render_sector_tab(ctx.us_sector_rank, ctx.leading_us_sectors, "🇺🇸 US Sectors", config.US_SECTOR_ETFS)
    st.divider()
    _render_sector_tab(ctx.eu_sector_rank, ctx.leading_eu_sectors, "🇪🇺 EU Sectors", config.EU_SECTOR_ETFS)


# ── TAB 3: SCREENED STOCKS ────────────────────────────────────────────────────
with tab3:
    if not stocks:
        st.warning("No candidates passed screening.")
    else:
        rows = []
        for s in stocks:
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
            })

        df_sc = pd.DataFrame(rows)
        pct_cols_sc = ["1M%", "3M%", "1Y%", "RS%"]

        styled_sc = (
            df_sc.style
            .map(_score_style, subset=["Score"])
            .map(_stage_style, subset=["Stage"])
            .map(_pct_style,   subset=pct_cols_sc)
            .format({c: "{:+.2f}%" for c in pct_cols_sc}, na_rep="–")
            .format({"P/E": "{:.1f}", "RSI": "{:.0f}"}, na_rep="–")
        )

        st.dataframe(styled_sc, use_container_width=True, height=min(900, 50 + len(rows) * 36))
        st.caption(
            "Score 0–100  ·  Stage S2 = advancing (ideal entry per Weinstein/Prehn)  "
            "·  RS% = 1Y return relative to S&P 500"
        )

        # ── Mini chart gallery ────────────────────────────────────────────────
        st.divider()
        st.markdown("##### Sparklines – Price & MA50 (3 months)")
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
                        st.image(img, use_column_width=True)
                    st.caption(
                        f"{s_icon} **{s['ticker']}** {score}/100  \n"
                        f"S{stage}{st_tag}{ret_str}"
                    )


# ── TAB 4: DEEP DIVE ─────────────────────────────────────────────────────────
with tab4:
    if not stocks:
        st.info("Run the analysis first.")
        st.stop()

    top_n_stocks = stocks[:config.MAX_DETAIL_STOCKS]
    options = [
        f"{s['ticker']}  {(s.get('name') or '')[:30]}  [{s['score']}/100]"
        for s in top_n_stocks
    ]
    chosen_label = st.selectbox("Select stock", options, index=0)
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
            st.image(base64.b64decode(chart_b64), use_column_width=True)
        else:
            st.warning("Chart unavailable (need ≥50 trading days of data).")

        interp = ta_d.get("interpretation", "")
        if interp:
            with st.expander("TA Interpretation", expanded=True):
                st.markdown(interp)

    with right_col:
        st.subheader("📊 Fundamentals")

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
                lc, vc = st.columns([2, 1])
                lc.markdown(f"{icon} {m['label']}")
                vc.markdown(f"**{m['value']}**")

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
