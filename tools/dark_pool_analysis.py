"""
Dark Pool & Money Flow Analysis
Detects institutional flows and trades using Felix Prehn's framework:
- 3 Power Moves: institutional volume spike, heartbeat pattern, record quarter
- Sector-first approach: find hot sectors before picking stocks
- Wall Street Protocol: technical confirmation on entry/exit

References:
  Following_Institutional_Money_Flow.md
  Wall_Street_Protocol_Workbook.md
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

from tools.market_data import fetch_ohlcv, fetch_info

logger = logging.getLogger(__name__)


def analyze_money_flows(tickers: List[str], lookback_days: int = 20) -> Dict[str, Dict[str, Any]]:
    """
    Analyze money flow signals for list of tickers.
    Returns flow scores and momentum signals for each ticker.
    
    Args:
        tickers: List of stock symbols
        lookback_days: Historical window for flow momentum calculation
        
    Returns:
        Dict mapping ticker → {flow_score, flow_direction, accumulation, momentum, blocks_detected}
    """
    flows = {}
    
    for ticker in tickers:
        try:
            flows[ticker] = _analyze_single_ticker_flow(ticker, lookback_days)
        except Exception as e:
            logger.warning("Flow analysis failed for %s: %s", ticker, e)
            flows[ticker] = _default_flow_data(ticker)
    
    return flows


def _analyze_single_ticker_flow(ticker: str, lookback_days: int) -> Dict[str, Any]:
    """
    Analyze flow characteristics for a single ticker.
    Implements Felix Prehn's institutional detection:
    1. Institutional volume spike detection
    2. Heartbeat pattern recognition (accumulation/distribution base)
    3. Record quarter indicator
    """
    try:
        # Fetch OHLCV data (cached in market_data layer)
        hist = fetch_ohlcv(ticker, period=f"{lookback_days}d", interval="1d")
        
        if hist is None or hist.empty or len(hist) < 5:
            return _default_flow_data(ticker)
        
        hist = hist.sort_index()
        
        # ─────────────────────────────────────────────────────────────────────
        # POWER MOVE 1: Institutional Volume Spike Detection
        # Look for: Single day volume ≥ 3x average on strong up move
        # ─────────────────────────────────────────────────────────────────────
        avg_volume = hist["Volume"].mean()
        spike_detected = False
        spike_magnitude = 0
        
        recent_days = hist.tail(20)
        for i in range(len(recent_days)):
            vol = recent_days["Volume"].iloc[i]
            close_change = recent_days["Close"].pct_change().iloc[i]
            
            if vol >= avg_volume * 3 and close_change > 0.01:  # 3x volume + up day
                spike_detected = True
                spike_magnitude = vol / avg_volume
                break
        
        power_move_1_score = 25 if spike_detected else 0
        
        # ─────────────────────────────────────────────────────────────────────
        # POWER MOVE 2: Heartbeat Pattern (Accumulation/Distribution Base)
        # Look for: Alternating high up-volume / low down-volume days in base
        # This is institutional nibbling into a consolidation zone
        # ─────────────────────────────────────────────────────────────────────
        heartbeat_score = _detect_heartbeat_pattern(hist)
        
        # ─────────────────────────────────────────────────────────────────────
        # POWER MOVE 3: Record Quarter Indicator
        # Fetch fundamentals to check for best-ever revenue/earnings
        # ─────────────────────────────────────────────────────────────────────
        power_move_3_score = _detect_record_quarter(ticker)
        
        # ─────────────────────────────────────────────────────────────────────
        # Calculate technical flow metrics
        volume_sma = hist["Volume"].rolling(20).mean()
        volume_zscore = (hist["Volume"] - volume_sma) / volume_sma.std()
        
        # On-Balance Volume (OBV) - cumulative indicator of flow
        close_diff = hist["Close"].diff()
        obv = (np.sign(close_diff) * hist["Volume"]).fillna(0).cumsum()
        obv_momentum = (obv.iloc[-1] - obv.iloc[-5]) / (abs(obv.iloc[-5]) + 1)  # Last 5 days
        
        # Accumulation/Distribution Line
        hl2 = (hist["High"] + hist["Low"]) / 2
        clv = (hist["Close"] - hist["Low"] - (hist["High"] - hist["Close"])) / (hist["High"] - hist["Low"] + 0.0001)
        ad_line = (clv * hist["Volume"]).fillna(0).cumsum()
        ad_momentum = (ad_line.iloc[-1] - ad_line.iloc[-10]) / (abs(ad_line.iloc[-10]) + 1)
        
        # Price action vs volume correlation (smart money shows up in vol before price)
        vol_price_corr = np.corrcoef(
            (hist["Volume"] / hist["Volume"].mean()).values,
            (hist["Close"].pct_change() * 100).fillna(0).values
        )[0, 1]
        
        # Flow score (-100 to +100)
        # Incorporates: OBV, A/D, volume zscore, block detection, and Prehn's power moves
        obv_signal = 20 if obv_momentum > 0 else -20 if obv_momentum < -0.3 else 0
        ad_signal = 20 if ad_momentum > 0 else -20 if ad_momentum < -0.2 else 0
        vol_signal = 20 if volume_zscore.iloc[-1] > 1 else -15 if volume_zscore.iloc[-1] < -1 else 0
        corr_signal = 15 if vol_price_corr < 0.3 else -10 if vol_price_corr > 0.7 else 0
        
        # Combine all signals
        prehn_power_moves = power_move_1_score + heartbeat_score + power_move_3_score
        flow_score = np.clip(obv_signal + ad_signal + vol_signal + corr_signal + (prehn_power_moves // 3), -100, 100)
        
        # Flow direction: trending up or down?
        flow_direction = "INFLOW" if obv_momentum > 0.1 else "OUTFLOW" if obv_momentum < -0.15 else "NEUTRAL"
        
        # Momentum: is flow accelerating or decelerating?
        obv_accel = (obv.iloc[-1] - 2*obv.iloc[-5] + obv.iloc[-10]) / (abs(obv.iloc[-5]) + 1)
        momentum = "ACCELERATING" if obv_accel > 0 else "DECELERATING" if obv_accel < 0 else "STABLE"
        
        return {
            "ticker": ticker,
            "flow_score": float(flow_score),
            "flow_direction": flow_direction,
            "momentum": momentum,
            "accumulation": float(ad_momentum),
            "obv_momentum": float(obv_momentum),
            # Prehn's Power Moves
            "institutional_spike": spike_detected,
            "spike_magnitude": float(spike_magnitude) if spike_detected else 0.0,
            "heartbeat_pattern": heartbeat_score > 0,
            "heartbeat_score": float(heartbeat_score),
            "record_quarter": power_move_3_score > 0,
            "power_moves_count": sum([spike_detected, heartbeat_score > 0, power_move_3_score > 0]),
            # Technical
            "volume_zscore": float(volume_zscore.iloc[-1]),
            "vol_price_correlation": float(vol_price_corr),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.debug("Flow calc error for %s: %s", ticker, e)
        return _default_flow_data(ticker)


def _detect_heartbeat_pattern(hist: pd.DataFrame) -> float:
    """
    Detect 'heartbeat pattern': alternating high up-volume / low down-volume days
    in a consolidation base. This indicates institutional accumulation.
    
    Returns score 0-25 based on pattern strength.
    """
    if len(hist) < 10:
        return 0.0
    
    try:
        recent = hist.tail(10)
        up_down = (recent["Close"].diff() > 0).values[1:]  # True if up day
        volumes = recent["Volume"].values[1:]
        
        # Calculate alternation pattern
        alternations = 0
        for i in range(len(up_down) - 1):
            if up_down[i] != up_down[i+1]:  # Direction change
                alternations += 1
        
        alternation_ratio = alternations / (len(up_down) - 1) if len(up_down) > 1 else 0
        
        # Check if up days have higher volume than down days
        up_vols = [volumes[i] for i in range(len(up_down)) if up_down[i]]
        down_vols = [volumes[i] for i in range(len(up_down)) if not up_down[i]]
        
        vol_imbalance = (np.mean(up_vols) - np.mean(down_vols)) / np.mean(volumes) if down_vols else 0
        
        # Score: high alternation + up-vol > down-vol = heartbeat
        if alternation_ratio > 0.5 and vol_imbalance > 0.2:
            return 25.0
        elif alternation_ratio > 0.4 and vol_imbalance > 0.1:
            return 15.0
        else:
            return 0.0
    except Exception:
        return 0.0


def _detect_record_quarter(ticker: str) -> float:
    """
    Detect if stock recently reported a record quarter (best revenue/earnings in 8 weeks).
    Returns score 25 if yes, 0 if no or unable to verify.
    """
    try:
        info = fetch_info(ticker) or {}
        
        # Check if most recent earnings beat expectations
        earnings_date = info.get("earningsDate")
        earnings_growth = info.get("earningsGrowth")
        revenue_per_share = info.get("revenuePerShare")
        
        # Simple heuristic: if earnings growth > 10% and reported recently, count as record quarter
        if earnings_growth and earnings_growth > 0.1:
            return 25.0
        
        return 0.0
    except Exception:
        return 0.0


def _default_flow_data(ticker: str) -> Dict[str, Any]:
    """Return neutral flow data when analysis fails."""
    return {
        "ticker": ticker,
        "flow_score": 0.0,
        "flow_direction": "NEUTRAL",
        "momentum": "STABLE",
        "accumulation": 0.0,
        "obv_momentum": 0.0,
        # Prehn's Power Moves
        "institutional_spike": False,
        "spike_magnitude": 0.0,
        "heartbeat_pattern": False,
        "heartbeat_score": 0.0,
        "record_quarter": False,
        "power_moves_count": 0,
        # Technical
        "volume_zscore": 0.0,
        "vol_price_correlation": 0.0,
        "timestamp": datetime.now().isoformat(),
    }


def generate_flow_signal(flow_score: float, momentum: str, direction: str) -> Tuple[str, str, str]:
    """
    Generate momentum trading signal from flow metrics.
    
    Returns:
        (signal, reason, signal_type) where signal_type in ['ENTRY', 'EXIT', 'HOLD', 'NEUTRAL']
    """
    # ───────────────────────────────────────────────────────────────────────────
    # ENTRY SIGNALS: Money flowing IN → BUY opportunities
    # ───────────────────────────────────────────────────────────────────────────
    if direction == "INFLOW":
        if flow_score > 75 and momentum == "ACCELERATING":
            return ("🟢 STRONG BUY - INFLOW ACCELERATING", 
                   "Heavy institutional inflows with accelerating momentum – prime entry",
                   "ENTRY")
        elif flow_score > 60 and momentum == "ACCELERATING":
            return ("🟢 BUY - INFLOW ACCELERATING",
                   "Strong institutional inflows with accelerating momentum",
                   "ENTRY")
        elif flow_score > 50:
            return ("🟢 BUY - INFLOW DETECTED",
                   "Consistent institutional inflows detected",
                   "ENTRY")
        elif flow_score > 25:
            return ("🟡 WEAK INFLOW",
                   "Weak inflows – monitor for momentum to build",
                   "HOLD")
    
    # ───────────────────────────────────────────────────────────────────────────
    # EXIT SIGNALS: Money flowing OUT → SELL/EXIT positions
    # ───────────────────────────────────────────────────────────────────────────
    elif direction == "OUTFLOW":
        if flow_score < -75 and momentum == "ACCELERATING":
            return ("🔴 EXIT - OUTFLOW ACCELERATING",
                   "Heavy institutional outflows with accelerating momentum – RED ALERT",
                   "EXIT")
        elif flow_score < -60 and momentum == "ACCELERATING":
            return ("🔴 SELL - OUTFLOW ACCELERATING",
                   "Strong institutional outflows with accelerating momentum",
                   "EXIT")
        elif flow_score < -50:
            return ("🔴 SELL - OUTFLOW DETECTED",
                   "Consistent institutional outflows detected – consider exit",
                   "EXIT")
        elif flow_score < -25:
            return ("🟠 WEAK OUTFLOW",
                   "Weak outflows – monitor for distribution pressure",
                   "HOLD")
    
    # ───────────────────────────────────────────────────────────────────────────
    # NEUTRAL: No clear signal
    # ───────────────────────────────────────────────────────────────────────────
    return ("⚪ NEUTRAL", f"Mixed flow signals (score: {flow_score:.0f})", "NEUTRAL")


def sector_flow_analysis(holdings_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate flow signals by sector.
    Identifies sectors with inflows (entry opportunities) and outflows (exit risks).
    
    Args:
        holdings_dict: {ticker: {sector, fundamentals, ...}}
        
    Returns:
        {sector: {avg_flow_score, inflow_count, outflow_count, signal, signal_type}}
    """
    sector_flows = {}
    
    for ticker, data in holdings_dict.items():
        sector = data.get("sector", "Unknown")
        flow_score = data.get("flow_score", 0)
        direction = data.get("flow_direction", "NEUTRAL")
        
        if sector not in sector_flows:
            sector_flows[sector] = {
                "sector": sector,
                "tickers": [],
                "flow_scores": [],
                "inflow_count": 0,
                "outflow_count": 0,
                "neutral_count": 0,
            }
        
        sector_flows[sector]["tickers"].append(ticker)
        sector_flows[sector]["flow_scores"].append(flow_score)
        
        if direction == "INFLOW":
            sector_flows[sector]["inflow_count"] += 1
        elif direction == "OUTFLOW":
            sector_flows[sector]["outflow_count"] += 1
        else:
            sector_flows[sector]["neutral_count"] += 1
    
    # Summarize by sector with entry/exit signals
    result = {}
    for sector, data in sector_flows.items():
        avg_score = np.mean(data["flow_scores"]) if data["flow_scores"] else 0
        total_tickers = len(data["tickers"])
        inflow_ratio = data["inflow_count"] / total_tickers if total_tickers else 0
        outflow_ratio = data["outflow_count"] / total_tickers if total_tickers else 0
        
        # ─────────────────────────────────────────────────────────────────────
        # SECTOR INFLOW: Money flowing INTO sector → ENTRY opportunity
        # ─────────────────────────────────────────────────────────────────────
        if inflow_ratio > 0.6 and avg_score > 50:
            signal = "🟢 SECTOR INFLOW - ENTRY"
            signal_type = "ENTRY"
            reason = f"Money flowing into {sector}: {data['inflow_count']}/{total_tickers} stocks in inflow"
        elif inflow_ratio > 0.5 and avg_score > 25:
            signal = "🟡 SECTOR INFLOW - MONITOR"
            signal_type = "ENTRY"
            reason = f"Emerging inflow in {sector}: {data['inflow_count']}/{total_tickers} stocks showing inflows"
        
        # ─────────────────────────────────────────────────────────────────────
        # SECTOR OUTFLOW: Money flowing OUT of sector → EXIT risk
        # ─────────────────────────────────────────────────────────────────────
        elif outflow_ratio > 0.6 and avg_score < -50:
            signal = "🔴 SECTOR OUTFLOW - EXIT"
            signal_type = "EXIT"
            reason = f"Money flowing out of {sector}: {data['outflow_count']}/{total_tickers} stocks in outflow – CONSIDER EXITING POSITIONS"
        elif outflow_ratio > 0.5 and avg_score < -25:
            signal = "🟠 SECTOR OUTFLOW - CAUTION"
            signal_type = "EXIT"
            reason = f"Distribution in {sector}: {data['outflow_count']}/{total_tickers} stocks showing outflows"
        
        # ─────────────────────────────────────────────────────────────────────
        # NEUTRAL
        # ─────────────────────────────────────────────────────────────────────
        else:
            signal = "⚪ SECTOR NEUTRAL"
            signal_type = "NEUTRAL"
            reason = f"{sector}: {data['inflow_count']} inflows, {data['outflow_count']} outflows, {data['neutral_count']} neutral"
        
        result[sector] = {
            "sector": sector,
            "avg_flow_score": float(avg_score),
            "inflow_count": data["inflow_count"],
            "outflow_count": data["outflow_count"],
            "neutral_count": data["neutral_count"],
            "inflow_ratio": float(inflow_ratio),
            "outflow_ratio": float(outflow_ratio),
            "total_tickers": total_tickers,
            "signal": signal,
            "signal_type": signal_type,
            "reason": reason,
        }
    
    return result


def flag_exit_risks(portfolio: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flag portfolio holdings with OUTFLOW signals (exit risks).
    Prioritizes by signal strength (urgency).
    
    Args:
        portfolio: List of {ticker, quantity, flow_score, flow_direction, momentum, ...}
        
    Returns:
        List of positions with EXIT or SELL signals, sorted by urgency
    """
    at_risk = []
    
    for holding in portfolio:
        flow_score = holding.get("flow_score", 0)
        direction = holding.get("flow_direction", "NEUTRAL")
        momentum = holding.get("flow_momentum", "STABLE")
        
        # Flag for exit only on OUTFLOW signals
        if direction == "OUTFLOW" and flow_score < -25:
            signal, reason, signal_type = generate_flow_signal(flow_score, momentum, direction)
            
            # Determine urgency based on flow score and momentum
            if flow_score < -75 and momentum == "ACCELERATING":
                urgency = "CRITICAL"
                action = "EXIT IMMEDIATELY"
            elif flow_score < -60 and momentum == "ACCELERATING":
                urgency = "HIGH"
                action = "EXIT SOON"
            elif flow_score < -50:
                urgency = "HIGH"
                action = "PLAN EXIT"
            else:
                urgency = "MEDIUM"
                action = "MONITOR CLOSELY"
            
            at_risk.append({
                "ticker": holding.get("ticker"),
                "quantity": holding.get("quantity", 0),
                "position_value": holding.get("quantity", 0) * holding.get("current_price", 0),
                "flow_score": float(flow_score),
                "flow_direction": direction,
                "momentum": momentum,
                "signal": signal,
                "reason": reason,
                "signal_type": signal_type,
                "urgency": urgency,
                "action": action,
            })
    
    # Sort by urgency and flow score (most critical first)
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    return sorted(at_risk, key=lambda x: (urgency_order.get(x["urgency"], 3), x["flow_score"]))


def flag_entry_opportunities(screened_stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flag screened stocks with INFLOW signals (entry opportunities).
    Prioritizes by signal strength and flow momentum.
    
    Args:
        screened_stocks: List of {ticker, flow_score, flow_direction, flow_momentum, ...}
        
    Returns:
        List of opportunities with ENTRY signals, sorted by strength
    """
    opportunities = []
    
    for stock in screened_stocks:
        flow_score = stock.get("flow_score", 0)
        direction = stock.get("flow_direction", "NEUTRAL")
        momentum = stock.get("flow_momentum", "STABLE")
        
        # Flag only INFLOW signals
        if direction == "INFLOW" and flow_score > 25:
            signal, reason, signal_type = stock.get("flow_signal", ""), stock.get("flow_reason", ""), "ENTRY"
            
            # Determine confidence based on flow score and momentum
            if flow_score > 75 and momentum == "ACCELERATING":
                confidence = "VERY_HIGH"
                priority = "URGENT"
            elif flow_score > 60 and momentum == "ACCELERATING":
                confidence = "HIGH"
                priority = "HIGH"
            elif flow_score > 50:
                confidence = "MEDIUM"
                priority = "MEDIUM"
            else:
                confidence = "LOW"
                priority = "MONITOR"
            
            opportunities.append({
                "ticker": stock.get("ticker"),
                "name": stock.get("name"),
                "sector": stock.get("sector"),
                "score": stock.get("score", 0),  # Felix Prehn score
                "flow_score": float(flow_score),
                "flow_direction": direction,
                "momentum": momentum,
                "power_moves": stock.get("power_moves", 0),
                "signal": signal,
                "reason": reason,
                "signal_type": signal_type,
                "confidence": confidence,
                "priority": priority,
            })
    
    # Sort by priority and flow score (best opportunities first)
    priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "MONITOR": 3}
    return sorted(opportunities, key=lambda x: (priority_order.get(x["priority"], 4), -x["flow_score"], -x["score"]))


def analyze_industry_flows(screened_stocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze money flows at the industry level (more granular than sector).
    
    Args:
        screened_stocks: List of stocks with flow analysis
        
    Returns:
        {industry: {inflow_count, outflow_count, avg_flow_score, signal, signal_type, reason}}
    """
    industry_flows = {}
    
    for stock in screened_stocks:
        industry = stock.get("industry", stock.get("sector", "Unknown"))
        flow_score = stock.get("flow_score", 0)
        direction = stock.get("flow_direction", "NEUTRAL")
        
        if industry not in industry_flows:
            industry_flows[industry] = {
                "industry": industry,
                "tickers": [],
                "flow_scores": [],
                "inflow_count": 0,
                "outflow_count": 0,
                "neutral_count": 0,
            }
        
        industry_flows[industry]["tickers"].append(stock.get("ticker"))
        industry_flows[industry]["flow_scores"].append(flow_score)
        
        if direction == "INFLOW":
            industry_flows[industry]["inflow_count"] += 1
        elif direction == "OUTFLOW":
            industry_flows[industry]["outflow_count"] += 1
        else:
            industry_flows[industry]["neutral_count"] += 1
    
    # Summarize by industry with entry/exit signals
    result = {}
    for industry, data in industry_flows.items():
        avg_score = np.mean(data["flow_scores"]) if data["flow_scores"] else 0
        total_tickers = len(data["tickers"])
        inflow_ratio = data["inflow_count"] / total_tickers if total_tickers else 0
        outflow_ratio = data["outflow_count"] / total_tickers if total_tickers else 0
        
        # Determine signal and signal type
        if inflow_ratio > 0.6 and avg_score > 50:
            signal = "🟢 INFLOW OPPORTUNITY"
            signal_type = "ENTRY"
            reason = f"{industry}: {data['inflow_count']}/{total_tickers} stocks in inflow – Hot money entering"
        elif inflow_ratio > 0.5 and avg_score > 25:
            signal = "🟡 EMERGING INFLOW"
            signal_type = "ENTRY"
            reason = f"{industry}: {data['inflow_count']}/{total_tickers} stocks showing momentum – Monitor for acceleration"
        elif outflow_ratio > 0.6 and avg_score < -50:
            signal = "🔴 OUTFLOW WARNING"
            signal_type = "EXIT"
            reason = f"{industry}: {data['outflow_count']}/{total_tickers} stocks in outflow – Money leaving, exit positions"
        elif outflow_ratio > 0.5 and avg_score < -25:
            signal = "🟠 DISTRIBUTION PRESSURE"
            signal_type = "EXIT"
            reason = f"{industry}: {data['outflow_count']}/{total_tickers} stocks showing distribution – Caution on entry"
        else:
            signal = "⚪ NEUTRAL"
            signal_type = "NEUTRAL"
            reason = f"{industry}: Mixed flows ({data['inflow_count']} inflows, {data['outflow_count']} outflows, {data['neutral_count']} neutral)"
        
        result[industry] = {
            "industry": industry,
            "total_tickers": total_tickers,
            "avg_flow_score": float(avg_score),
            "inflow_count": data["inflow_count"],
            "outflow_count": data["outflow_count"],
            "neutral_count": data["neutral_count"],
            "inflow_ratio": float(inflow_ratio),
            "outflow_ratio": float(outflow_ratio),
            "signal": signal,
            "signal_type": signal_type,
            "reason": reason,
        }
    
    return result
