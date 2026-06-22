# Felix Prehn Weekend Market Analysis System

A collaborative agent pipeline that fetches live market data every weekend and produces a comprehensive HTML report covering technical and fundamental analysis across all markets tradeable from a German portfolio account.

---

## Architecture

```
run_analysis.py (Orchestrator)
    │
    ├── Agent 1: market_overview.py
    │     → Market phase (Bull/Bear), index health, breadth
    │
    ├── Agent 2: sector_rotation.py
    │     → Ranks US & EU sectors by momentum, finds leaders
    │
    ├── Agent 3: stock_screener.py
    │     → Screens entire universe using Felix Prehn / CANSLIM criteria
    │     → Scores each stock 0–100
    │
    ├── Agent 4: technical_analyst.py
    │     → Generates price+MA+MACD+Volume charts for top candidates
    │     → Weinstein Stage 2 detection, RS vs S&P 500
    │
    ├── Agent 5: fundamental_analyst.py
    │     → EPS/revenue growth, P/E, ROE, margins, balance sheet
    │     → Strengths & risks summary
    │
    └── Agent 6: report_generator.py
          → Self-contained HTML report in reports/analysis_YYYY-MM-DD.html

tools/market_data.py          → yfinance wrappers (OHLCV + fundamentals)
tools/technical_indicators.py → Stage analysis, RSI, MACD, Bollinger, ATR
tools/fundamental_metrics.py  → Metric extraction + Felix Prehn scoring

mcp_server/server.py          → MCP server for Claude Code integration
```

---

## Market Universe

| Universe | Exchanges covered |
|---|---|
| DAX 40 | XETRA – German large caps |
| MDAX | XETRA – German mid caps |
| Euro Stoxx ex-DE | AMS, PAR, MAD, MIL, HEL, CPH, BRU |
| Swiss | SIX – NESN, NOVN, ROG, ABBN … |
| FTSE 100 | LSE – UK blue chips |
| S&P 500 Top 100 | NYSE/NASDAQ |
| NASDAQ 100 | NASDAQ |
| Russell 2000 (selected) | US small-cap representative basket |
| US Mid Caps (selected) | US mid-cap representative basket |
| Custom watchlist | Add tickers to `CUSTOM_WATCHLIST` in config.py |

---

## Felix Prehn Scoring (0–100)

### Technical (50 pts)
| Criterion | Max pts |
|---|---|
| Weinstein Stage 2 (price above rising MA200) | 20 |
| Above MA50 + MA150 + MA200 | 15 |
| RSI 50–70 (healthy momentum) | 5 |
| MACD line above signal | 5 |
| Within 25% of 52-week high | 5 |

### Fundamental (50 pts)
| Criterion | Max pts |
|---|---|
| EPS growth >25% | 15 |
| Revenue growth >15% | 10 |
| P/E ratio (lower = better) | 10 |
| ROE >20% | 10 |
| Net profit margin >20% | 5 |

**Ratings:**
- ⭐ STRONG BUY: 72–100
- ✅ BUY: 58–71
- 👀 WATCH: 42–57
- ❌ AVOID: 0–41

---

## Quick Start

### 1. Install dependencies

```bash
cd /Users/emc/Claude/Projects/SectorStockScreener/Analyzer
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the analysis

```bash
# Full broad universe (all markets, ~20-40 min first run)
python run_analysis.py

# Faster focused run (~5-10 min)
python run_analysis.py --universe focused

# Simplified max coverage (stocks + tracked ETFs, cache-first)
python run_analysis.py --universe allassets

# Single market
python run_analysis.py --universe dax
python run_analysis.py --universe sp500
python run_analysis.py --universe nasdaq
python run_analysis.py --universe russell2000
python run_analysis.py --universe midcap
python run_analysis.py --universe largecap
python run_analysis.py --universe xlargecap

# Your personal watchlist (edit CUSTOM_WATCHLIST in config.py first)
python run_analysis.py --universe custom

# Analyze your live portfolio (RESTOCK/HOLD/SELL per holding)
python run_analysis.py --universe xlargecap --portfolio portfolio_example.csv
```

The report opens in any browser: `reports/analysis_YYYY-MM-DD.html`

### Portfolio CSV Format

Use a CSV with at least a `Ticker` column:

```csv
Ticker,Quantity,AverageCost,EntryDate
AAPL,100,150.00,2025-11-12
MSFT,50,380.00,2026-01-08
```

Notes:
- `Quantity` and `AverageCost` are optional but recommended for P/L and position sizing context.
- `EntryDate` is optional (`YYYY-MM-DD` preferred) and is used for holding-period-aware decisions.
- Recommendations are shown as `RESTOCK`, `HOLD`, or `SELL` in the generated HTML report.

### Dynamic Universe Caching

- `russell2000` and `midcap` universes are fetched from public constituent sources when available.
- Results are cached locally in `data/universe_cache.json`.
- Cache TTL is 7 days by default and can be changed via `DYNAMIC_UNIVERSE_TTL_HOURS` in `config.py`.
- If a live fetch fails, the system falls back to the curated static list so runs remain reliable.

### Market Data Caching (Yahoo request reduction)

- OHLCV and fundamental `.info` responses are cached in-memory during each run.
- A persistent disk cache is also used across runs in `data/market_cache/`.
- OHLCV disk cache TTL defaults to 6 hours; info cache TTL defaults to 24 hours.
- Re-running the same universe now reuses local cache first, significantly reducing Yahoo load.

---

## Weekly Schedule (automate)

Add to your crontab (`crontab -e`) to run every Saturday at 7:00 AM:

```cron
0 7 * * 6 cd /Users/emc/Claude/Projects/SectorStockScreener/Analyzer && /path/to/.venv/bin/python run_analysis.py >> logs/weekend.log 2>&1
```

Or use the Cowork scheduler via Claude.

---

## MCP Server (Claude Code integration)

The MCP server lets you query the analysis interactively from Claude Code.

### Register the server

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stock-analysis": {
      "command": "/Users/emc/Claude/Projects/SectorStockScreener/Analyzer/.venv/bin/python",
      "args": ["/Users/emc/Claude/Projects/SectorStockScreener/Analyzer/mcp_server/server.py"],
      "cwd": "/Users/emc/Claude/Projects/SectorStockScreener/Analyzer"
    }
  }
}
```

Restart Claude Code, then you can ask:

- *"What is the market phase right now?"*
- *"Show me sector rotation for the last 3 months"*
- *"Give me the technical + fundamental snapshot for SAP.DE"*
- *"Screen the DAX for Felix Prehn buy signals"*
- *"Run the full weekend report"*

---

## Adding Your Own Tickers

Edit `config.py`:

```python
CUSTOM_WATCHLIST = [
    "HIMS",     # example US ticker
    "ASML.AS",  # example Dutch ticker
    "IFX.DE",   # example German ticker
    "AZN.L",    # example UK ticker
]
```

Then run: `python run_analysis.py --universe custom`

---

## Ticker Format Reference

| Market | Suffix | Example |
|---|---|---|
| Germany (XETRA) | `.DE` | `SAP.DE` |
| Netherlands | `.AS` | `ASML.AS` |
| France | `.PA` | `MC.PA` |
| Spain | `.MC` | `ITX.MC` |
| Italy | `.MI` | `ENEL.MI` |
| Switzerland | `.SW` | `NESN.SW` |
| UK | `.L` | `AZN.L` |
| Denmark | `.CO` | `NOVO-B.CO` |
| Finland | `.HE` | `NOKIA.HE` |
| US | (none) | `NVDA` |

---

## Disclaimer

This system is for **informational and educational purposes only**.  
It does not constitute financial advice. Always conduct your own due diligence.
