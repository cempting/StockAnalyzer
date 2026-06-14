"""
Agent 3 – Stock Screener (Felix Prehn / CANSLIM-inspired)
Pass 1: fast market-cap + stage filter.
Pass 2: compute Prehn composite score.
Outputs a ranked list of candidates for deep analysis.
"""

import logging
from typing import List, Dict, Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

import config
from tools.market_data import fetch_ohlcv, fetch_info, fetch_ohlcv_batch
from tools.technical_indicators import add_indicators, get_technical_snapshot
from tools.fundamental_metrics import extract_fundamentals, score_prehn

logger = logging.getLogger(__name__)

BATCH_SIZE = 30   # tickers per yfinance batch download


def run(ctx: "AnalysisContext") -> None:
    logger.info("▶ StockScreenerAgent starting")

    tickers = ctx.universe_tickers
    bench_df = ctx.benchmark_df

    # ── Pass 1: batch-download 1Y OHLCV + quick stage check ─────────────────
    candidates: List[Dict[str, Any]] = []
    logger.info("Pass 1: fetching OHLCV for %d tickers in batches of %d", len(tickers), BATCH_SIZE)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Screening tickers…", total=len(tickers))

        for i in range(0, len(tickers), BATCH_SIZE):
            batch = tickers[i : i + BATCH_SIZE]
            ohlcv_map = fetch_ohlcv_batch(batch, period="2y")

            for ticker in batch:
                progress.advance(task)
                df_raw = ohlcv_map.get(ticker)
                if df_raw is None or len(df_raw) < 50:
                    continue

                df = add_indicators(df_raw)
                snap = get_technical_snapshot(df, bench_df)

                # Stage filter: skip stage 3 & 4
                stage = snap.get("stage", 0)
                if config.SCREENING["require_stage_2_or_1"] and stage in (3, 4):
                    continue

                candidates.append({
                    "ticker": ticker,
                    "df":     df,
                    "snap":   snap,
                })

    logger.info("Pass 1 survivors: %d / %d", len(candidates), len(tickers))

    # ── Pass 2: fetch fundamentals + score ───────────────────────────────────
    logger.info("Pass 2: fetching fundamentals and scoring %d candidates", len(candidates))

    scored: List[Dict[str, Any]] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Scoring candidates…", total=len(candidates))

        for c in candidates:
            progress.advance(task)
            ticker = c["ticker"]
            try:
                info = fetch_info(ticker)
                fund = extract_fundamentals(info)

                # Market cap filter
                mc = fund.get("market_cap")
                if mc and mc < config.SCREENING["min_market_cap"]:
                    continue

                sc = score_prehn(c["snap"], fund)

                scored.append({
                    "ticker":     ticker,
                    "name":       fund.get("name", ""),
                    "sector":     fund.get("sector", ""),
                    "industry":   fund.get("industry", ""),
                    "country":    fund.get("country", ""),
                    "score":      sc["total_score"],
                    "rating":     sc["rating"],
                    "breakdown":  sc["breakdown"],
                    "stage":      c["snap"].get("stage"),
                    "rsi":        c["snap"].get("rsi"),
                    "macd_bullish": c["snap"].get("macd_bullish"),
                    "above_ma200":  c["snap"].get("above_ma200"),
                    "pct_52h":    c["snap"].get("pct_from_52w_high"),
                    "ret_1m":     c["snap"].get("ret_1m"),
                    "ret_3m":     c["snap"].get("ret_3m"),
                    "ret_1y":     c["snap"].get("ret_1y"),
                    "rs_bench":   c["snap"].get("rs_vs_benchmark"),
                    "pe":         fund.get("forward_pe") or fund.get("trailing_pe"),
                    "eps_growth": fund.get("earnings_growth"),
                    "rev_growth": fund.get("revenue_growth"),
                    "roe":        fund.get("roe"),
                    "market_cap": fund.get("market_cap"),
                    # Keep df reference for downstream TA agent
                    "_df":        c["df"],
                    "_fund":      fund,
                    "_snap":      c["snap"],
                })
            except Exception as exc:
                logger.debug("Scoring error %s: %s", ticker, exc)

    # Sort by Prehn score
    scored.sort(key=lambda x: x["score"], reverse=True)

    ctx.screened_stocks = scored[: config.SCREENING["max_candidates"]]
    logger.info(
        "✔ StockScreenerAgent done – %d candidates, top score: %d",
        len(ctx.screened_stocks),
        ctx.screened_stocks[0]["score"] if ctx.screened_stocks else 0,
    )
