# The 90-Day Playbook - Summary and Precise Rules

## Scope and intent
This note summarizes the key ideas from *The 90-Day Playbook* (Goat Academy) and translates them into practical, rules-based investment and trading actions.

This is educational content, not financial advice.

## Core wisdoms

1. Follow money flow, not opinions.
- The playbook's central edge is institutional flow detection via volume and price behavior.
- Signal quality increases when multiple independent signals agree.

2. High-probability setups are rare and should be filtered aggressively.
- Most stocks are noise most of the time.
- Use strict filters to reduce decisions and avoid overtrading.

3. A repeatable process beats predictions.
- The 90-day structure is meant to build skill in sequence: setup -> application -> execution.
- Consistency and journaling are treated as part of the strategy, not admin work.

4. Risk management is non-negotiable.
- Entry quality matters, but survival is determined by stop placement, position sizing, and discipline.
- Every trade must be pre-risked before entry.

5. Psychology is part of execution risk.
- Emotional impulses (FOMO, hope, fear, revenge) are expected and must be constrained by system rules.

## The 3 primary setup signals ("triple confirmation")

A candidate is strongest when all 3 are present:

1. Volume spike
- A day with volume >= 300% of recent average.
- Prefer spikes on up days (green candles), indicating accumulation.

2. Heartbeat pattern
- Sideways consolidation (range) for at least about 3 months (longer often stronger).
- Clear resistance and support boundaries can be drawn.

3. Record quarter
- Best-ever earnings or meaningful fundamental inflection (for example, EPS turns from negative to positive).

## Exact trade rules (entry, risk, management, exit)

## A. Universe and watchlist rules

1. Build and maintain a watchlist of at least 15 names across sectors.
2. For each name, store:
- resistance level
- support level
- heartbeat duration
- latest volume status
- record-quarter status
- moving-average slope state
3. Remove names that lose structure (no longer consolidating or trend quality deteriorates).

## B. Entry rules (must all pass)

Enter only when all of these are true:

1. Volume rule: Latest breakout attempt has volume >= 300% of average.
2. Directional volume rule: Breakout volume is mostly on up candles, not down candles.
3. Structure rule: Price closes above the upper range boundary (confirmed breakout close).
4. Trend filter: Relevant moving average slope is upward (do not buy downward slope setups).
5. Fundamental filter: Record quarter or clear earnings inflection is present.
6. Order protocol: Buy order and stop-loss order are placed at the same time.
7. Risk cap: Position is sized so max loss at stop is <= 1% of total portfolio.

If any item fails, no trade.

## C. Entry execution model

1. Use a conditional buy above resistance (the "pay more" principle):
- Example: if resistance is 20.00, trigger near 20.50 after confirmation.
2. Optional phased entry:
- Tranche 1 at breakout trigger.
- Tranche 2 only on orderly pullback/retest that holds breakout area.

## D. Stop-loss calibration rules

Do not use one fixed stop % for all stocks. Calibrate to volatility.

Reference bands from the playbook:

- High-volatility names (about 3-4%+ daily movement): initial stop about 20-25% below entry.
- Medium-volatility names (about 1-2% daily movement): initial stop about 10-15% below entry.
- Low-volatility names (less than 1% daily movement): initial stop about 5-8% below entry.

If stop is routinely hit by normal noise, it is too tight. If loss is too large at stop, size is too big.

## E. Position sizing formula

1. Define portfolio risk per trade:
- R = 1% of total portfolio value.
2. Define per-share risk:
- S = Entry price - Stop price.
3. Position size in shares:
- Shares = floor(R / S).
4. Final check:
- If resulting position creates concentration risk, reduce size.

## F. Post-entry management rules

1. Review positions once per day max (or weekly system review cadence), not continuously.
2. If trade moves favorably:
- after first clear rally, raise stop toward breakeven.
- after second rally, trail stop to lock part of gains.
3. Monitor volume behavior:
- repeated heavy red volume spikes are warning signs.
4. Consider adds only on controlled pullbacks/retests, never on random weakness.

## G. Exit rules

Exit when any occurs:

1. Price hits stop-loss (automatic exit).
2. Clear distribution appears (heavy institutional selling) and setup quality is broken.
3. Original thesis invalidates (breakout fails structurally and does not recover).

Never widen stops after entry to avoid taking a planned loss.

## Weekly operating protocol (15-30 minutes)

Run this checklist once per week:

1. Validate each active position still meets system rules.
2. Review all volume alerts from the week.
3. Refresh watchlist (add new, remove invalid names).
4. Adjust trailing stops on winners.
5. Pre-place conditional buys for qualified breakout candidates.
6. Journal mistakes, wins, and one process improvement for next week.

## 90-day implementation roadmap (compressed)

## Weeks 1-4 (Foundation)

1. Set up broker/charting/screener.
2. Train volume reading on at least 10 charts.
3. Train heartbeat identification on at least 10 charts.
4. Start watchlist and weekly review routine.

## Weeks 5-8 (Application)

1. Build sector-diversified watchlist (15+).
2. Execute at least 6 paper trades using full protocol.
3. Document rationale, stop, size, and outcome for each trade.
4. Identify personal error pattern (entry timing, stop placement, or sizing).

## Weeks 9-12 (Execution)

1. Start live with smallest size model.
2. Keep 1% risk cap and simultaneous stop placement on every trade.
3. Complete at least 12 total trades (paper + live).
4. Compare results against a passive index benchmark.

## Hard risk commandments

1. No trade without a predefined stop.
2. No stop, no position.
3. No single position risk above 1% portfolio.
4. No averaging down into invalidated setups.
5. No buying when moving-average slope is down.
6. No impulse trades outside checklist rules.

## Practical interpretation for this project

If you want to operationalize these rules in your analyzer pipeline:

1. Add a signal score requiring:
- volume spike >= 3x baseline
- breakout close above resistance
- non-negative or improving earnings regime
- upward moving-average slope
2. Enforce a risk module that rejects trade candidates if stop-implied risk > 1% budget.
3. Track weekly process metrics:
- number of qualified setups
- number of checklist violations
- stop adherence rate
- average R multiple per trade

That converts the playbook from motivation into a measurable, testable system.
