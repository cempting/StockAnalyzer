"""
Configuration for the Stock & Sector Analysis System.
Edit CUSTOM_WATCHLIST to add your personal tickers.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM WATCHLIST  ← add your personal picks here
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_WATCHLIST = [
    # e.g. "ASML.AS", "HIMS", "PLTR"
]

# ─────────────────────────────────────────────────────────────────────────────
# MARKET UNIVERSES
# ─────────────────────────────────────────────────────────────────────────────

DAX_40 = [
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MUV2.DE",
    "EOAN.DE", "DBK.DE", "IFX.DE", "BMW.DE", "MBG.DE",
    "BAYN.DE", "BAS.DE", "RWE.DE", "ADS.DE", "HEN3.DE",
    "SHL.DE", "FME.DE", "FRE.DE", "CON.DE", "MTX.DE",
    "AIR.DE", "VNA.DE", "ENR.DE", "DHL.DE", "MRK.DE",
    "BEI.DE", "SY1.DE", "DB1.DE", "SRT3.DE", "QIA.DE",
    "ZAL.DE", "PAH3.DE", "VOW3.DE", "CBK.DE", "BNR.DE",
    "DTG.DE", "RHM.DE", "P911.DE", "HFG.DE", "1COV.DE",
]

MDAX_SELECTED = [
    "AFX.DE", "BOSS.DE", "COP.DE", "EVK.DE", "GFT.DE",
    "HLE.DE", "KGX.DE", "LEG.DE", "MDG1.DE", "NDA.DE",
    "PSM.DE", "PUM.DE", "S92.DE", "SMHN.DE", "SOW.DE",
    "TKA.DE", "TAG.DE", "DWS.DE", "WAF.DE", "BC8.DE",
    "SDAX.DE", "TEG.DE", "UTDI.DE", "WUW.DE", "EVD.DE",
    "HAB.DE", "HOT.DE", "JEN.DE", "LXS.DE", "SZG.DE",
]

# Euro Stoxx 50 ex-Germany (German names already in DAX_40)
EURO_STOXX_EX_DE = [
    # Netherlands
    "ASML.AS", "ADYEN.AS", "INGA.AS", "PHIA.AS", "UNA.AS", "HEIA.AS", "WKL.AS",
    # France
    "MC.PA", "OR.PA", "BNP.PA", "SAN.PA", "TTE.PA", "ACA.PA",
    "GLE.PA", "BN.PA", "ENGI.PA", "DG.PA", "RI.PA", "KER.PA", "CS.PA",
    # Spain
    "SAN.MC", "IBE.MC", "ITX.MC", "BBVA.MC", "REP.MC", "AMS.MC",
    # Italy
    "ENEL.MI", "ENI.MI", "ISP.MI", "UCG.MI", "STM.MI",
    # Finland
    "NOKIA.HE",
    # Denmark
    "NOVO-B.CO",
    # Belgium
    "ABI.BR", "UCB.BR",
]

# Swiss blue chips (accessible from German broker)
SWISS_SELECTED = [
    "NESN.SW", "NOVN.SW", "ROG.SW", "ABBN.SW",
    "UBSG.SW", "ZURN.SW", "SREN.SW", "GIVN.SW", "LONN.SW",
]

FTSE_100_SELECTED = [
    "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L",
    "RIO.L", "GSK.L", "LSEG.L", "DGE.L", "NG.L",
    "VOD.L", "BT-A.L", "LLOY.L", "BATS.L", "REL.L",
    "CPG.L", "EXPN.L", "AAL.L", "NWG.L", "FLTR.L",
    "WPP.L", "RKT.L", "TSCO.L", "IMB.L", "BA.L",
    "STAN.L", "JD.L", "MKS.L", "PRU.L", "III.L",
]

# S&P 500 – top 100 by market cap
SP500_TOP100 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
    "AVGO", "JPM", "LLY", "UNH", "ORCL", "V", "XOM", "MA", "COST",
    "JNJ", "PG", "WMT", "HD", "NFLX", "CRM", "BAC", "ABBV", "AMD",
    "MCD", "PEP", "KO", "CSCO", "ACN", "TMO", "ABT", "WFC", "MRK",
    "ADBE", "LIN", "DHR", "MS", "TXN", "AMGN", "NKE", "CVX", "NEE",
    "RTX", "MDT", "BMY", "ISRG", "T", "UNP", "SBUX", "LOW", "SCHW",
    "BLK", "SPGI", "HON", "AXP", "IBM", "GS", "INTU", "AMT", "AMAT",
    "GE", "PM", "NOW", "DE", "PLD", "CAT", "REGN", "ELV", "CI",
    "SYK", "GILD", "TJX", "ZTS", "MDLZ", "MO", "VRTX", "D", "CME",
    "ADI", "CB", "PANW", "DUK", "SO", "COP", "EQIX", "LRCX", "MCO",
    "F", "GM", "UBER", "ABNB", "COIN", "SNOW", "CRWD", "NET", "DDOG",
]

# NASDAQ 100 focused
NASDAQ_100_SELECTED = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL", "AVGO",
    "COST", "ASML", "NFLX", "AMD", "ADBE", "QCOM", "INTU", "AMGN",
    "TXN", "CSCO", "HON", "CMCSA", "AMAT", "ISRG", "BKNG", "SBUX",
    "ADI", "GILD", "MU", "REGN", "VRTX", "LRCX", "MDLZ", "PANW",
    "KLAC", "SNPS", "CDNS", "MAR", "ORLY", "MELI", "NXPI", "CRWD",
    "WDAY", "PYPL", "FTNT", "ADSK", "CTAS", "PCAR", "MNST", "CHTR",
    "CEG", "ON", "IDXX", "EXC", "ROST", "CPRT", "ODFL", "FAST",
    "ZS", "DXCM", "APP", "PLTR", "AXON",
]

# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETFs  (for rotation analysis)
# ─────────────────────────────────────────────────────────────────────────────

US_SECTOR_ETFS = {
    "Technology":             "XLK",
    "Healthcare":             "XLV",
    "Financials":             "XLF",
    "Energy":                 "XLE",
    "Industrials":            "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples":       "XLP",
    "Materials":              "XLB",
    "Utilities":              "XLU",
    "Real Estate":            "XLRE",
    "Communication":          "XLC",
}

EU_SECTOR_ETFS = {
    "EU Banks":       "EXV1.DE",
    "EU Healthcare":  "EXV2.DE",
    "EU Technology":  "EXV3.DE",
    "EU Insurance":   "EXV4.DE",
    "EU Oil & Gas":   "EXV6.DE",
    "EU Consumer":    "EXV7.DE",
    "EU Industrials": "EXV8.DE",
    "EU Utilities":   "EXV9.DE",
}

MAJOR_INDICES = {
    "S&P 500":     "^GSPC",
    "NASDAQ 100":  "^NDX",
    "DAX 40":      "^GDAXI",
    "Euro Stoxx 50": "^STOXX50E",
    "FTSE 100":    "^FTSE",
    "Nikkei 225":  "^N225",
    "SMI":         "^SSMI",
    "MDAX":        "^MDAXI",
}

# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSE PRESETS
# ─────────────────────────────────────────────────────────────────────────────

UNIVERSES = {
    "focused": DAX_40 + EURO_STOXX_EX_DE[:20] + SP500_TOP100[:50] + NASDAQ_100_SELECTED[:30],
    "broad": (DAX_40 + MDAX_SELECTED + EURO_STOXX_EX_DE + SWISS_SELECTED +
              FTSE_100_SELECTED + SP500_TOP100 + NASDAQ_100_SELECTED),
}

def get_universe(name: str = "broad") -> list:
    base = UNIVERSES.get(name, UNIVERSES["broad"])
    all_tickers = list(dict.fromkeys(base + CUSTOM_WATCHLIST))  # dedup, preserve order
    return all_tickers

# ─────────────────────────────────────────────────────────────────────────────
# FELIX PREHN SCREENING THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

SCREENING = {
    # Fundamental minimums (stocks failing these are excluded early)
    "min_market_cap":        500_000_000,   # €500M+
    "min_eps_growth":        0.0,           # any positive EPS growth
    "min_revenue_growth":    0.0,           # any revenue growth
    "max_pe_ratio":          80,            # exclude extreme valuation
    "min_roe":               0.05,          # 5% ROE minimum

    # Technical minimums
    "require_above_ma200":   False,         # softer filter for screening pass 1
    "require_stage_2_or_1":  True,          # no stage 3/4 stocks

    # Top N per universe to deep-analyse (keeps runtime reasonable)
    "max_candidates":        40,
}

# Felix Prehn scoring weights (must sum to 100)
SCORING_WEIGHTS = {
    # Technical (50 pts)
    "stage_2":        20,   # Stage 2 uptrend
    "moving_averages": 15,  # Above MA50/150/200
    "rsi":             5,   # RSI 50–70
    "macd":            5,   # MACD bullish
    "near_52w_high":   5,   # Within 25% of 52W high
    # Fundamental (50 pts)
    "eps_growth":     15,
    "rev_growth":     10,
    "pe_ratio":       10,
    "roe":            10,
    "profit_margin":   5,
}

# Report settings
REPORT_DIR = "reports"
MAX_DETAIL_STOCKS = 20  # stocks with full TA+FA detail in report
