"""
Stock Analysis MCP Server
─────────────────────────
Exposes live market data and analysis tools via the MCP protocol (stdio transport).

Connect to Claude Code by adding to ~/.claude/claude_desktop_config.json:

    {
      "mcpServers": {
        "stock-analysis": {
          "command": "python",
          "args": ["/path/to/Analyzer/mcp_server/server.py"],
          "cwd": "/path/to/Analyzer"
        }
      }
    }

Then in Claude Code you can ask:
  "Run the sector rotation analysis"
  "Screen stocks in the DAX for Felix Prehn criteria"
  "Show me the technical snapshot for SAP.DE"
"""

import asyncio
import json
import logging
import sys
import os

# Make sure parent dir is on path so we can import tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

import config
from tools.market_data import (
    fetch_ohlcv,
    fetch_info,
    fetch_sector_performance,
    fetch_index_data,
)
from tools.technical_indicators import add_indicators, get_technical_snapshot
from tools.fundamental_metrics import extract_fundamentals, score_prehn

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)

app = Server("stock-analysis")


# ─────────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_market_overview",
            description=(
                "Return performance and moving-average status for all major indices "
                "(S&P 500, NASDAQ 100, DAX 40, Euro Stoxx 50, FTSE 100, SMI, Nikkei). "
                "Use this first to assess market phase."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_sector_performance",
            description=(
                "Return 1W / 1M / 3M / 6M / 1Y performance for US SPDR sector ETFs "
                "and European sector ETFs. Reveals rotation trends."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["us", "eu", "both"],
                        "description": "Which sector map to fetch (default: both)",
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_stock_snapshot",
            description=(
                "Return full technical + fundamental snapshot for a single ticker. "
                "Includes Weinstein stage, RSI, MACD, MAs, P/E, EPS growth, ROE, "
                "and the Felix Prehn composite score (0–100)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Yahoo Finance ticker, e.g. 'SAP.DE', 'NVDA', 'ASML.AS'",
                    }
                },
                "required": ["ticker"],
            },
        ),
        types.Tool(
            name="screen_universe",
            description=(
                "Screen an entire universe against Felix Prehn criteria and return "
                "the top candidates ranked by composite score. "
                "WARNING: 'broad' takes several minutes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "universe": {
                        "type": "string",
                        "enum": ["focused", "broad", "dax", "sp500", "nasdaq", "custom"],
                        "description": "Which universe to screen (default: focused)",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top candidates to return (default: 20)",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="run_full_report",
            description=(
                "Run the complete weekend analysis pipeline: market overview → "
                "sector rotation → stock screening → TA+FA detail → HTML report. "
                "Saves the report to reports/ and returns the file path."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "universe": {
                        "type": "string",
                        "enum": ["focused", "broad"],
                        "description": "Universe size (default: focused)",
                    }
                },
                "required": [],
            },
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# TOOL HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "get_market_overview":
        data = fetch_index_data(config.MAJOR_INDICES, period="1y")
        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "get_sector_performance":
        region = arguments.get("region", "both")
        sector_map = {}
        if region in ("us", "both"):
            sector_map.update(config.US_SECTOR_ETFS)
        if region in ("eu", "both"):
            sector_map.update(config.EU_SECTOR_ETFS)
        df = fetch_sector_performance(sector_map)
        return [types.TextContent(type="text", text=df.to_string())]

    elif name == "get_stock_snapshot":
        ticker = arguments["ticker"].upper()

        # Fetch data
        df_raw = fetch_ohlcv(ticker, period="2y")
        info   = fetch_info(ticker)

        if df_raw is None or df_raw.empty:
            return [types.TextContent(type="text", text=f"ERROR: No data for {ticker}")]

        df = add_indicators(df_raw)
        # Use SPY as benchmark
        bench = fetch_ohlcv("^GSPC", period="1y")

        tech  = get_technical_snapshot(df, bench)
        fund  = extract_fundamentals(info)
        score = score_prehn(tech, fund)

        result = {
            "ticker":      ticker,
            "name":        fund.get("name", ""),
            "sector":      fund.get("sector", ""),
            "technical":   tech,
            "fundamental": fund,
            "prehn_score": score,
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    elif name == "screen_universe":
        universe_name = arguments.get("universe", "focused")
        top_n = int(arguments.get("top_n", 20))

        # Resolve ticker list
        if universe_name == "dax":
            tickers = config.DAX_40
        elif universe_name == "sp500":
            tickers = config.SP500_TOP100
        elif universe_name == "nasdaq":
            tickers = config.NASDAQ_100_SELECTED
        elif universe_name == "custom":
            tickers = config.CUSTOM_WATCHLIST
        else:
            tickers = config.get_universe(universe_name)

        bench = fetch_ohlcv("^GSPC", period="1y")

        results = []
        for ticker in tickers:
            try:
                df_raw = fetch_ohlcv(ticker, period="2y")
                if df_raw is None or len(df_raw) < 50:
                    continue
                df = add_indicators(df_raw)
                info = fetch_info(ticker)
                tech = get_technical_snapshot(df, bench)
                fund = extract_fundamentals(info)
                sc   = score_prehn(tech, fund)
                results.append({
                    "ticker":     ticker,
                    "name":       fund.get("name", ""),
                    "sector":     fund.get("sector", ""),
                    "score":      sc["total_score"],
                    "rating":     sc["rating"],
                    "stage":      tech.get("stage"),
                    "rsi":        tech.get("rsi"),
                    "ret_1m":     tech.get("ret_1m"),
                    "ret_3m":     tech.get("ret_3m"),
                    "eps_growth": fund.get("earnings_growth"),
                    "rev_growth": fund.get("revenue_growth"),
                    "pe":         fund.get("forward_pe") or fund.get("trailing_pe"),
                })
            except Exception as exc:
                logger.debug("Skipping %s: %s", ticker, exc)

        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:top_n]
        return [types.TextContent(type="text", text=json.dumps(top, indent=2, default=str))]

    elif name == "run_full_report":
        universe = arguments.get("universe", "focused")
        # Import lazily to keep server startup fast
        from run_analysis import run_pipeline
        report_path = run_pipeline(universe=universe)
        return [types.TextContent(type="text", text=f"Report saved: {report_path}")]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="stock-analysis",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
