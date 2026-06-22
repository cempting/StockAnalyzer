"""
Agent – Money Flow Analyst
Analyzes institutional flows, dark pool activity, and momentum signals.
Generates BUY entry signals when money flows INTO sectors/stocks.
Generates SELL/EXIT warnings when money flows OUT of sectors/stocks.
"""

import logging
import os
from typing import Dict, List, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.dark_pool_analysis import (
    analyze_money_flows,
    generate_flow_signal,
    sector_flow_analysis,
    analyze_industry_flows,
    flag_exit_risks,
    flag_entry_opportunities,
)

logger = logging.getLogger(__name__)



def run(ctx: "AnalysisContext") -> None:
    """
    Analyze money flows for screened stocks and portfolio holdings.
    Generate momentum-based ENTRY and EXIT trading signals.
    """
    if not ctx.screened_stocks:
        logger.warning("No screened stocks; skipping money flow analysis")
        ctx.money_flow_analysis = {}
        ctx.portfolio_exit_risks = []
        ctx.sector_flows = {}
        ctx.entry_opportunities = []
        ctx.exit_risks = []
        return

    logger.info("▶ MoneyFlowAnalystAgent starting")

    # Extract tickers from screened stocks
    screened_tickers = [s.get("ticker") for s in ctx.screened_stocks if s.get("ticker")]
    logger.info("  Analyzing money flows for %d candidates...", len(screened_tickers))

    # Analyze flows for screened stocks
    flow_data = analyze_money_flows(screened_tickers, lookback_days=20)

    # ─────────────────────────────────────────────────────────────────────────
    # ENRICH SCREENED STOCKS WITH FLOW DATA
    # ─────────────────────────────────────────────────────────────────────────
    flow_analysis = {}
    power_moves_breakdown = {"0": 0, "1": 0, "2": 0, "3": 0}
    
    for stock in ctx.screened_stocks:
        ticker = stock.get("ticker")
        if ticker in flow_data:
            flow = flow_data[ticker]
            signal, reason, signal_type = generate_flow_signal(
                flow["flow_score"],
                flow["momentum"],
                flow["flow_direction"],
            )
            
            # Boost signal if multiple Prehn Power Moves detected
            power_moves = flow.get("power_moves_count", 0)
            power_moves_breakdown[str(min(power_moves, 3))] += 1
            
            if power_moves >= 2:
                if "STRONG" not in signal:
                    signal = signal.replace("BUY", "STRONG BUY").replace("HOLD", "BUY")
                reason = f"{reason} [Felix Prehn: {power_moves}/3 Power Moves]"
            elif power_moves == 1:
                reason = f"{reason} [Felix Prehn: {power_moves}/3 Power Moves]"
            
            stock["flow_score"] = flow["flow_score"]
            stock["flow_direction"] = flow["flow_direction"]
            stock["flow_momentum"] = flow["momentum"]
            stock["power_moves"] = power_moves
            stock["institutional_spike"] = flow.get("institutional_spike", False)
            stock["heartbeat_pattern"] = flow.get("heartbeat_pattern", False)
            stock["record_quarter"] = flow.get("record_quarter", False)
            stock["flow_signal"] = signal
            stock["flow_reason"] = reason
            stock["flow_signal_type"] = signal_type
            
            flow_analysis[ticker] = {
                "ticker": ticker,
                "name": stock.get("name"),
                "sector": stock.get("sector"),
                "score": stock.get("score"),
                "flow_score": flow["flow_score"],
                "flow_direction": flow["flow_direction"],
                "momentum": flow["momentum"],
                "accumulation": flow["accumulation"],
                "power_moves_count": power_moves,
                "institutional_spike": flow.get("institutional_spike", False),
                "spike_magnitude": flow.get("spike_magnitude", 0),
                "heartbeat_pattern": flow.get("heartbeat_pattern", False),
                "record_quarter": flow.get("record_quarter", False),
                "signal": signal,
                "reason": reason,
                "signal_type": signal_type,
            }

    ctx.money_flow_analysis = flow_analysis

    # ─────────────────────────────────────────────────────────────────────────
    # IDENTIFY ENTRY OPPORTUNITIES (INFLOWS)
    # ─────────────────────────────────────────────────────────────────────────
    entry_opportunities = flag_entry_opportunities(ctx.screened_stocks)
    ctx.entry_opportunities = entry_opportunities
    
    entry_by_priority = {
        "URGENT": [e for e in entry_opportunities if e["priority"] == "URGENT"],
        "HIGH": [e for e in entry_opportunities if e["priority"] == "HIGH"],
        "MEDIUM": [e for e in entry_opportunities if e["priority"] == "MEDIUM"],
        "MONITOR": [e for e in entry_opportunities if e["priority"] == "MONITOR"],
    }
    
    if entry_by_priority["URGENT"]:
        logger.info("  🟢 URGENT BUY OPPORTUNITIES (Strong Inflows):")
        for opp in entry_by_priority["URGENT"][:5]:
            logger.info("    %s: %s (flow: %.0f, power moves: %d/3)",
                       opp["ticker"], opp["signal"], opp["flow_score"], opp["power_moves"])

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYZE SECTOR-LEVEL FLOWS
    # ─────────────────────────────────────────────────────────────────────────
    holdings_with_flow = {}
    for ticker, flow_info in flow_analysis.items():
        screened = next((s for s in ctx.screened_stocks if s.get("ticker") == ticker), None)
        if screened:
            holdings_with_flow[ticker] = {
                "sector": flow_info.get("sector"),
                "flow_score": flow_info.get("flow_score"),
                "flow_direction": flow_info.get("flow_direction"),
            }

    sector_flows = sector_flow_analysis(holdings_with_flow)
    ctx.sector_flows = sector_flows
    
    # Log sector signals
    sector_entries = [s for s in sector_flows.values() if s.get("signal_type") == "ENTRY"]
    sector_exits = [s for s in sector_flows.values() if s.get("signal_type") == "EXIT"]
    
    if sector_entries:
        logger.info("  🟢 SECTOR INFLOW OPPORTUNITIES:")
        for sector in sector_entries:
            logger.info("    %s: %s", sector["sector"], sector["reason"])
    
    if sector_exits:
        logger.warning("  🔴 SECTOR OUTFLOW WARNINGS:")
        for sector in sector_exits:
            logger.warning("    %s: %s", sector["sector"], sector["reason"])

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYZE INDUSTRY-LEVEL FLOWS (MORE GRANULAR THAN SECTOR)
    # ─────────────────────────────────────────────────────────────────────────
    industry_flows = analyze_industry_flows(ctx.screened_stocks)
    ctx.industry_flows = industry_flows
    
    industry_entries = [ind for ind in industry_flows.values() if ind.get("signal_type") == "ENTRY"]
    industry_exits = [ind for ind in industry_flows.values() if ind.get("signal_type") == "EXIT"]
    
    if industry_entries:
        logger.info("  🟢 INDUSTRY INFLOW OPPORTUNITIES:")
        for industry in industry_entries[:3]:
            logger.info("    %s: %s", industry["industry"], industry["reason"])
    
    if industry_exits:
        logger.warning("  🟠 INDUSTRY DISTRIBUTION PRESSURE:")
        for industry in industry_exits[:3]:
            logger.warning("    %s: %s", industry["industry"], industry["reason"])

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYZE PORTFOLIO EXIT RISKS (IF PORTFOLIO PROVIDED)
    # ─────────────────────────────────────────────────────────────────────────
    exit_risks = []
    if ctx.portfolio_analysis:
        portfolio_with_flows = []
        for holding in ctx.portfolio_analysis:
            ticker = holding.get("ticker")
            if ticker in flow_data:
                flow = flow_data[ticker]
                holding["flow_score"] = flow["flow_score"]
                holding["flow_direction"] = flow["flow_direction"]
                holding["flow_momentum"] = flow.get("momentum", "STABLE")
                portfolio_with_flows.append(holding)

        exit_risks = flag_exit_risks(portfolio_with_flows)
        ctx.portfolio_exit_risks = exit_risks
        
        if exit_risks:
            logger.warning("  🚨 PORTFOLIO EXIT ALERTS:")
            for i, risk in enumerate(exit_risks[:5], 1):
                logger.warning("    %d. %s: %s [%s]", i, risk["ticker"], risk["signal"], risk["urgency"])
                logger.warning("       → %s", risk["action"])
    else:
        ctx.portfolio_exit_risks = []
    
    ctx.exit_risks = exit_risks

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    strong_buys = sum(1 for f in flow_analysis.values() if "STRONG BUY" in f.get("signal", ""))
    buys = sum(1 for f in flow_analysis.values() if "BUY" in f.get("signal", "") and "STRONG" not in f.get("signal", ""))
    sells = sum(1 for f in flow_analysis.values() if "SELL" in f.get("signal", "") or "EXIT" in f.get("signal", ""))
    
    logger.info("✔ MoneyFlowAnalystAgent done")
    logger.info("  Entry Signals: %d STRONG BUY, %d BUY", strong_buys, buys)
    logger.info("  Exit Signals: %d positions to EXIT/SELL", sells)
    logger.info("  Sector Inflows: %d hot sectors | Sector Outflows: %d cold sectors", 
                len(sector_entries), len(sector_exits))
    logger.info("  Prehn Power Moves: 3/3=%d, 2/3=%d, 1/3=%d, 0/3=%d",
                power_moves_breakdown.get("3", 0), power_moves_breakdown.get("2", 0),
                power_moves_breakdown.get("1", 0), power_moves_breakdown.get("0", 0))

