"""
run_analysis.py – Weekend Market Analysis Orchestrator
───────────────────────────────────────────────────────
Chains all five agents in order and produces a self-contained HTML report.

Usage:
    python run_analysis.py              # broad universe (default)
    python run_analysis.py --universe focused
    python run_analysis.py --universe allassets
    python run_analysis.py --universe dax
    python run_analysis.py --universe sp500
    python run_analysis.py --universe russell2000
    python run_analysis.py --universe midcap
    python run_analysis.py --universe custom
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# SHARED ANALYSIS CONTEXT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalysisContext:
    """Mutable blackboard shared between all agents."""
    universe_name:   str = "broad"
    universe_tickers: List[str] = field(default_factory=list)
    benchmark_df:    Optional[pd.DataFrame] = None

    # Filled by Agent 1 – MarketOverviewAgent
    market_phase:    Optional[str] = None
    eu_market_phase: Optional[str] = None
    breadth_signal:  Optional[str] = None
    market_assessment: Dict[str, Any] = field(default_factory=dict)
    index_data:      Dict[str, Any] = field(default_factory=dict)
    uptrend_count:   int = 0
    total_indices:   int = 0

    # Filled by Agent 2 – SectorRotationAgent
    us_sector_df:    Optional[pd.DataFrame] = None
    eu_sector_df:    Optional[pd.DataFrame] = None
    us_sector_rank:  Optional[pd.DataFrame] = None
    eu_sector_rank:  Optional[pd.DataFrame] = None
    leading_us_sectors: List[str] = field(default_factory=list)
    leading_eu_sectors: List[str] = field(default_factory=list)
    leading_sectors: List[str] = field(default_factory=list)

    # Filled by Agent 3 – StockScreenerAgent
    screened_stocks: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ticker → {ohlcv, fundamentals}

    # Filled by Agent 3.5 – MoneyFlowAnalystAgent
    money_flow_analysis: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ticker → flow metrics
    sector_flows: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # sector → flow summary
    industry_flows: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # industry → flow summary
    entry_opportunities: List[Dict[str, Any]] = field(default_factory=list)  # entry signals by priority
    exit_risks: List[Dict[str, Any]] = field(default_factory=list)  # all exit risk alerts
    portfolio_exit_risks: List[Dict[str, Any]] = field(default_factory=list)  # positions to exit

    # Filled by Agent 4 – TechnicalAnalystAgent
    technical_analyses: Dict[str, Any] = field(default_factory=dict)

    # Filled by Agent 5 – FundamentalAnalystAgent
    fundamental_analyses: Dict[str, Any] = field(default_factory=dict)

    # Filled by Agent 5.5 – PortfolioAnalyzerAgent (optional)
    portfolio_analysis: List[Dict[str, Any]] = field(default_factory=list)

    # Filled by Agent 6 – ReportGeneratorAgent
    report_path: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(universe: str = "broad", portfolio_file: Optional[str] = None) -> str:
    """
    Execute the full agent pipeline and return the report file path.
    If portfolio_file is provided, also analyze user holdings.
    This function is also called by the MCP server's run_full_report tool.
    """
    import config
    from tools.market_data import fetch_ohlcv
    from tools.market_data import get_cache_summary
    from agents import (
        market_overview,
        sector_rotation,
        stock_screener,
        money_flow_analyst,
        technical_analyst,
        fundamental_analyst,
        portfolio_analyzer,
        report_generator,
    )

    t0 = time.time()
    console.print(Panel(
        f"[bold magenta]Felix Prehn Weekend Analysis[/bold magenta]\n"
        f"[dim]Universe: {universe.upper()}  ·  {pd.Timestamp.now().strftime('%A %d %B %Y')}[/dim]",
        border_style="magenta",
    ))

    # Resolve tickers through one path to keep behavior consistent.
    if universe == "custom":
        tickers = config.get_custom_watchlist() or config.DAX_40
    else:
        tickers = config.get_universe(universe)

    ctx = AnalysisContext(universe_name=universe, universe_tickers=tickers)

    # Benchmark (S&P 500) – needed for relative-strength calculations
    console.print("[cyan]Fetching benchmark data (S&P 500)…[/cyan]")
    ctx.benchmark_df = fetch_ohlcv("^GSPC", period="1y")

    # ── Agent 1 ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 1 · Market Overview[/bold blue]"))
    market_overview.run(ctx)
    console.print(
        f"  US phase: [green]{ctx.market_phase}[/green]  "
        f"EU phase: [green]{ctx.eu_market_phase}[/green]  "
        f"Breadth: [yellow]{ctx.breadth_signal}[/yellow]"
    )

    # ── Agent 2 ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 2 · Sector Rotation[/bold blue]"))
    sector_rotation.run(ctx)
    console.print(f"  US leaders: [green]{ctx.leading_us_sectors}[/green]")
    console.print(f"  EU leaders: [green]{ctx.leading_eu_sectors}[/green]")

    # ── Agent 3 ───────────────────────────────────────────────────────────────
    console.print(Rule(f"[bold blue]Agent 3 · Stock Screener ({len(tickers)} tickers)[/bold blue]"))
    stock_screener.run(ctx)
    if ctx.screened_stocks:
        top5 = [f"{s['ticker']}({s['score']})" for s in ctx.screened_stocks[:5]]
        console.print(f"  Top 5: [green]{', '.join(top5)}[/green]")
    else:
        console.print("  [yellow]No candidates passed screening[/yellow]")

    # ── Agent 3.4 – Portfolio Analyzer (optional) ──────────────────────────────
    if portfolio_file:
        console.print(Rule("[bold blue]Agent 3.4 · Portfolio Analyzer[/bold blue]"))
        portfolio_analyzer.run(ctx, portfolio_file)
        if ctx.portfolio_analysis:
            restock = sum(1 for h in ctx.portfolio_analysis if h.get("recommendation") == "RESTOCK")
            hold = sum(1 for h in ctx.portfolio_analysis if h.get("recommendation") == "HOLD")
            sell = sum(1 for h in ctx.portfolio_analysis if h.get("recommendation") == "SELL")
            console.print(
                f"  Holdings analyzed: {len(ctx.portfolio_analysis)} "
                f"([green]RESTOCK {restock}[/green], [yellow]HOLD {hold}[/yellow], [red]SELL {sell}[/red])"
            )

    # ── Agent 3.5 – Money Flow Analyst ────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 3.5 · Money Flow Analyst[/bold blue]"))
    money_flow_analyst.run(ctx)
    if ctx.money_flow_analysis:
        strong_buys = sum(1 for f in ctx.money_flow_analysis.values() if "STRONG BUY" in f.get("signal", ""))
        strong_sells = sum(1 for f in ctx.money_flow_analysis.values() if "EXIT" in f.get("signal", ""))
        console.print(f"  Strong buys: [green]{strong_buys}[/green], Strong sells: [red]{strong_sells}[/red]")

    # ── Agent 4 ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 4 · Technical Analyst[/bold blue]"))
    technical_analyst.run(ctx)
    console.print(f"  Charts generated: {len(ctx.technical_analyses)}")

    # ── Agent 5 ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 5 · Fundamental Analyst[/bold blue]"))
    fundamental_analyst.run(ctx)
    console.print(f"  FA analyses done: {len(ctx.fundamental_analyses)}")

    # ── Agent 6 ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold blue]Agent 6 · Report Generator[/bold blue]"))
    report_path = report_generator.run(ctx)
    ctx.report_path = report_path

    cache_summary = get_cache_summary()
    ohlcv_cache = cache_summary.get("ohlcv", {})
    info_cache = cache_summary.get("info", {})
    console.print(
        f"  Cache: OHLCV hit {ohlcv_cache.get('hit_rate_pct', 0.0):.1f}% "
        f"({ohlcv_cache.get('hits', 0)} hits / {ohlcv_cache.get('yahoo_requests', 0)} Yahoo req) · "
        f"Info hit {info_cache.get('hit_rate_pct', 0.0):.1f}%"
    )

    elapsed = round(time.time() - t0, 1)
    console.print(Panel(
        f"[bold green]✓ Analysis complete in {elapsed}s[/bold green]\n"
        f"[dim]Report: {report_path}[/dim]",
        border_style="green",
    ))

    return report_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Felix Prehn Weekend Market Analysis")
    parser.add_argument(
        "--universe",
        default="broad",
        choices=["focused", "broad", "allassets", "dax", "sp500", "nasdaq", "russell2000", "midcap", "largecap", "xlargecap", "custom"],
        help="Stock universe to analyse (default: broad)",
    )
    parser.add_argument(
        "--portfolio",
        type=str,
        default=None,
        help="Path to portfolio CSV (Ticker, Quantity, AverageCost, optional EntryDate) for RESTOCK/HOLD/SELL analysis",
    )
    args = parser.parse_args()

    # Change to the script's directory so relative paths (reports/, data/) work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    report = run_pipeline(universe=args.universe, portfolio_file=args.portfolio)
    print(f"\n  Report saved → {report}")
    print("  Open it in any browser.\n")
    if args.portfolio:
        print(f"  Portfolio analyzed from: {args.portfolio}")
