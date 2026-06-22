# Money Flow Trading Signals Guide

## Overview

The refactored Money Flow Analyst generates **ENTRY** and **EXIT** signals based on institutional money flows using Felix Prehn's framework. This enables momentum-driven trading strategies.

---

## Entry Signals (INFLOWS) 🟢

### What Triggers Entry Signals?

**When institutional money flows INTO a sector, industry, or stock:**

- **Flow Score > 75 + Momentum = ACCELERATING**
  - Signal: `🟢 STRONG BUY - INFLOW ACCELERATING`
  - Confidence: `VERY_HIGH`
  - Priority: `URGENT`
  - → **Action: ENTER IMMEDIATELY** - Best momentum setup

- **Flow Score 60-75 + Momentum = ACCELERATING**
  - Signal: `🟢 BUY - INFLOW ACCELERATING`
  - Confidence: `HIGH`
  - Priority: `HIGH`
  - → **Action: ENTER SOON** - Strong inflow with acceleration

- **Flow Score 50-60**
  - Signal: `🟢 BUY - INFLOW DETECTED`
  - Confidence: `MEDIUM`
  - Priority: `MEDIUM`
  - → **Action: MONITOR & PREPARE ENTRY** - Consistent inflows

- **Flow Score 25-50**
  - Signal: `🟡 WEAK INFLOW`
  - Confidence: `LOW`
  - Priority: `MONITOR`
  - → **Action: WATCH & WAIT** - Monitor for momentum buildup

### Multi-Level Entry Identification

**3-Tier Analysis helps identify best entries:**

1. **Stock Level** (`money_flow_analysis`)
   - Individual stock flow scores
   - Power move count (0-3)
   - Technical confirmation

2. **Industry Level** (`industry_flows`)
   - More granular than sector
   - Identifies hot industries before broad sector moves
   - Shows exact inflow count

3. **Sector Level** (`sector_flows`)
   - Broadest view of capital rotation
   - Shows which sectors are "on fire"
   - Helps avoid sector-wide downtrends

**Example Entry Decision Flow:**
```
Sector: Technology      → SECTOR INFLOW ENTRY (8/12 stocks)
  └─ Industry: AI/ML  → INFLOW OPPORTUNITY (5/6 stocks in inflow)
      └─ Stock: ADPT  → STRONG BUY - INFLOW ACCELERATING (score: 78)
                → ENTER: Confirmed at stock, industry & sector level
```

---

## Exit Signals (OUTFLOWS) 🔴

### What Triggers Exit Signals?

**When institutional money flows OUT of a sector, industry, or stock:**

- **Flow Score < -75 + Momentum = ACCELERATING**
  - Signal: `🔴 EXIT - OUTFLOW ACCELERATING`
  - Urgency: `CRITICAL`
  - Action: `EXIT IMMEDIATELY`
  - → **RED ALERT** - Sell now, ask questions later

- **Flow Score -60 to -75 + Momentum = ACCELERATING**
  - Signal: `🔴 SELL - OUTFLOW ACCELERATING`
  - Urgency: `HIGH`
  - Action: `EXIT SOON`
  - → **URGENT EXIT** - Distribution is heavy

- **Flow Score -50 to -60**
  - Signal: `🔴 SELL - OUTFLOW DETECTED`
  - Urgency: `HIGH`
  - Action: `PLAN EXIT`
  - → **PREPARE FOR EXIT** - Money leaving the position

- **Flow Score -25 to -50**
  - Signal: `🟠 WEAK OUTFLOW`
  - Urgency: `MEDIUM`
  - Action: `MONITOR CLOSELY`
  - → **WATCH & SET STOP LOSS** - Distribution pressure building

### Portfolio-Level Exit Management

**Each position flagged with:**
- Current flow score
- Flow direction (INFLOW/OUTFLOW/NEUTRAL)
- Momentum state (ACCELERATING/DECELERATING/STABLE)
- Recommended action (EXIT IMMEDIATELY → MONITOR)
- Priority order (CRITICAL positions listed first)

**Example Exit Decision:**
```
Position: TSLA (1000 shares, $180/share)
  ├─ Flow Score: -82
  ├─ Direction: OUTFLOW
  ├─ Momentum: ACCELERATING
  ├─ Signal: 🔴 EXIT - OUTFLOW ACCELERATING
  └─ Action: EXIT IMMEDIATELY (Urgency: CRITICAL)
     → Institutional money fleeing, don't wait
```

---

## Signal Confidence & Reliability

### High Confidence Signals

**Strongest when combined with Felix Prehn Power Moves:**

- **Power Move 1: Institutional Volume Spike**
  - 3x+ average volume on up day
  - Score bonus: +25 points
  - Indicates institutional buying

- **Power Move 2: Heartbeat Pattern**
  - Alternating high volume up / low volume down days
  - Score bonus: +15 points
  - Institutional accumulation base

- **Power Move 3: Record Quarter**
  - Best earnings/revenue in recent quarters
  - Score bonus: +25 points
  - Fundamental confirmation

**Example:**
```
Stock with 2/3 Power Moves + Score 75 → VERY HIGH confidence entry
Stock with 3/3 Power Moves + Score 85 → EXTREMELY HIGH confidence entry
```

### Signal Strength Visualization

```
ENTRY CONFIDENCE:
VERY_HIGH   ████████░░  Flow: 75-100, Momentum: ACCELERATING, Power Moves: 2+
HIGH        ██████░░░░  Flow: 60-75,  Momentum: ACCELERATING
MEDIUM      ████░░░░░░  Flow: 50-60,  Any momentum
LOW         ██░░░░░░░░  Flow: 25-50,  Monitor only

EXIT URGENCY:
CRITICAL    ████████░░  Flow: <-75, Momentum: ACCELERATING, Exit NOW
HIGH        ██████░░░░  Flow: -60 to -50, High urgency
MEDIUM      ████░░░░░░  Flow: -50 to -25, Monitor closely
```

---

## How to Use These Signals

### Daily Workflow

**Morning Check:**
1. Review `entry_opportunities` (sorted by URGENT/HIGH priority)
2. Check `portfolio_exit_risks` (CRITICAL positions first)
3. Look at `sector_flows` and `industry_flows` for macro trends

**Entry Decision:**
- If URGENT entry with 2+ Power Moves → High probability, consider full position
- If HIGH entry with confirmation → Good opportunity, scale in
- If MEDIUM or MONITOR → Wait for acceleration signal

**Exit Decision:**
- If CRITICAL exit → Don't hesitate, exit immediately
- If HIGH exit → Plan exit, but can wait for better price
- If MEDIUM exit → Set tight stop loss, prepare exit
- If portfolio showing SECTOR/INDUSTRY outflow → Exit related positions

### Integration with Felix Prehn Strategy

The signals align with Felix Prehn's momentum approach:

1. **Sector-First**: Look at sector flows FIRST
   - Find "hot" sectors with inflows
   - Then pick best stocks within those sectors

2. **Momentum Entry**: Use INFLOW + ACCELERATING signals
   - Stock must be in inflow sector
   - Stock flow score > 50
   - Momentum must be ACCELERATING
   - Technical confirmation (Weinstein Stage 2, RS > market)

3. **Momentum Exit**: Use OUTFLOW signals as exit triggers
   - Money leaving = institutional selling
   - Don't fight the flow
   - Exit before sector rotation completes

4. **Profit Taking**: Monitor for ACCELERATION ending
   - When momentum changes to DECELERATING
   - When inflow ratio drops below 50%
   - Take profits on momentum trades

---

## Data Structure Reference

### Stock-Level Entry Opportunity
```python
{
    "ticker": "ADPT",
    "name": "Adaptive Biotechnologies",
    "sector": "Healthcare",
    "score": 78,  # Felix Prehn score
    "flow_score": 82,  # Inflow strength
    "flow_direction": "INFLOW",
    "momentum": "ACCELERATING",
    "power_moves": 2,  # 0-3 Power Moves detected
    "confidence": "VERY_HIGH",  # Entry confidence
    "priority": "URGENT",  # High priority entry
    "signal": "🟢 STRONG BUY - INFLOW ACCELERATING",
    "reason": "Heavy institutional inflows with accelerating momentum – prime entry"
}
```

### Sector/Industry Entry Signal
```python
{
    "sector": "Technology",
    "total_tickers": 12,
    "inflow_count": 8,  # 8/12 stocks in inflow
    "outflow_count": 2,
    "inflow_ratio": 0.67,  # 67% of sector in inflow
    "avg_flow_score": 62,
    "signal_type": "ENTRY",
    "signal": "🟢 SECTOR INFLOW - ENTRY",
    "reason": "Money flowing into Technology: 8/12 stocks in inflow"
}
```

### Portfolio Exit Risk
```python
{
    "ticker": "TSLA",
    "quantity": 1000,
    "position_value": 180000,
    "flow_score": -82,
    "flow_direction": "OUTFLOW",
    "momentum": "ACCELERATING",
    "urgency": "CRITICAL",
    "action": "EXIT IMMEDIATELY",
    "signal": "🔴 EXIT - OUTFLOW ACCELERATING",
    "reason": "Heavy institutional outflows with accelerating momentum – RED ALERT"
}
```

---

## Best Practices

### DO ✅
- **Combine with technical confirmation** - Use Stage 2 analysis, RS, MACD
- **Follow sector flows first** - Avoid swimming against the tide
- **Scale in with momentum** - Start small, add as ACCELERATING confirms
- **Exit on flow reversal** - Don't wait, momentum can reverse quickly
- **Monitor power moves** - 2-3 Power Moves = very high probability

### DON'T ❌
- **Ignore sector flows** - Buy great stock in cold sector = bad trade
- **Fight the money flows** - If money's leaving, get out
- **Overstay momentum** - Exit when momentum changes to DECELERATING
- **Ignore exit signals** - CRITICAL/HIGH urgency exits are real alerts
- **Enter on single entry signal** - Wait for acceleration confirmation

---

## Examples

### Example 1: Perfect Entry Setup
```
Sector: Semiconductors → 🟢 SECTOR INFLOW (70% inflow)
Industry: Chip Design → 🟢 INFLOW OPPORTUNITY (5/6 stocks)
Stock: ADPT
  ├─ Flow Score: 78
  ├─ Momentum: ACCELERATING
  ├─ Power Moves: 2/3 (Spike + Heartbeat)
  ├─ Felix Prehn Score: 82
  └─ Entry Signal: 🟢 STRONG BUY - INFLOW ACCELERATING [URGENT]

→ ENTRY DECISION: Enter full position or scale in
   Confidence: VERY HIGH
   Risk/Reward: Favorable (sector + industry + stock all inflow)
```

### Example 2: Exit Alert
```
Position: TSLA (bought 3 months ago, up 25%)
  ├─ Sector Flows: 🔴 SECTOR OUTFLOW (60% outflow)
  ├─ Stock Flows:
  │  ├─ Flow Score: -85
  │  ├─ Momentum: ACCELERATING (outflows speeding up)
  │  ├─ Direction: OUTFLOW
  │  └─ Power Moves: Institutional selling detected
  └─ Portfolio Alert: 🔴 EXIT - OUTFLOW ACCELERATING [CRITICAL]

→ EXIT DECISION: Take profits NOW
   Why: Sector is cold, individual stock outflows accelerating
   Don't wait: Institutional money is heading for the exits
```

### Example 3: Monitor & Wait
```
Stock: ACME
  ├─ Flow Score: 35 (weak)
  ├─ Momentum: STABLE (no acceleration)
  ├─ Direction: INFLOW (but weak)
  └─ Signal: 🟡 WEAK INFLOW [MONITOR]

→ DECISION: Don't enter yet
   Why: Inflows present but not accelerating
   Next Step: Watch for momentum to build
   If Flow Score → 60+ AND Momentum → ACCELERATING → Enter
```

---

## Real-Time Monitoring

The Money Flow Analyst now outputs:
1. **Entry Opportunities** - prioritized by confidence/urgency
2. **Exit Risks** - prioritized by criticality
3. **Sector Flows** - which sectors are hot/cold
4. **Industry Flows** - granular sector breakdown
5. **Portfolio Alerts** - specific position action items

Use these for:
- ✅ Momentum entry timing
- ✅ Profit-taking exit signals
- ✅ Position risk management
- ✅ Sector rotation decisions
- ✅ Portfolio rebalancing

---

**Next Steps:** Integrate these signals into a real-time dashboard or alert system for active trading.
