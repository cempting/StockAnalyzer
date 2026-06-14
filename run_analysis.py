"""
run_analysis.py – Weekend Market Analysis Orchestrator
───────────────────────────────────────────────────────
Chains all five agents in order and produces a self-contained HTML report.

Usage:
    python run_analysis.py              # broad universe (default)
    python run_analysis.py --universe focused
    python run_analysis.py --universe dax
    python run_analysis.py --universe sp500
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

    # Filled by Agent 4 – TechnicalAnalystAgent
    technical_analyses: Dict[str, Any] = field(default_factory=dict)

    # Filled by Agent 5 – FundamentalAnalystAgent
    fundamental_analyses: Dict[str, Any] = field(default_factory=dict)

    # Filled by Agent 6 – ReportGeneratorAgent
    report_path: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(universe: str = "broad") -> str:
    """
    Execute the full agent pipeline and return the report file path.
    This function is also called by the MCP server's run_full_report tool.
    """
    import config
    from tools.market_data import fetch_ohlcv
    from agents import (
        market_overview,
        sector_rotation,
        stock_screener,
        technical_analyst,
        fundamental_analyst,
        report_generator,
    )

    t0 = time.time()
    console.print(Panel(
        f"[bold magenta]Felix Prehn Weekend Analysis[/bold magenta]\n"
        f"[dim]Universe: {universe.upper()}  ·  {pd.Timestamp.now().strftime('%A %d %B %Y')}[/dim]",
        border_style="magenta",
    ))

    # Resolve tickers
    if universe == "dax":
        tickers = config.DAX_40
    elif universe == "sp500":
        tickers = config.SP500_TOP100
    elif universe == "nasdaq":
        tickers = config.NASDAQ_100_SELECTED
    elif universe == "custom":
        tickers = config.CUSTOM_WATCHLIST or config.DAX_40
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
        choices=["focused", "broad", "dax", "sp500", "nasdaq", "custom"],
        help="Stock universe to analyse (default: broad)",
    )
    args = parser.parse_args()

    # Change to the script's directory so relative paths (reports/, data/) work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    report = run_pipeline(universe=args.universe)
    print(f"\n  Report saved → {report}")
    print("  Open it in any browser.\n")
