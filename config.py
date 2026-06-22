"""
Configuration for the Stock & Sector Analysis System.
Edit CUSTOM_WATCHLIST to add your personal tickers.
"""

import json
import os

from tools.universe_data import get_dynamic_universe

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM WATCHLIST  ← add your personal picks here
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_WATCHLIST = [
    # e.g. "ASML.AS", "HIMS", "PLTR"
]

CUSTOM_WATCHLIST_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "custom_watchlist.json",
)


def _normalize_ticker_list(values) -> list:
    out = []
    seen = set()
    for raw in values or []:
        t = str(raw).strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def get_custom_watchlist() -> list:
    """Load user watchlist from disk, fallback to static CUSTOM_WATCHLIST."""
    try:
        if os.path.exists(CUSTOM_WATCHLIST_FILE):
            with open(CUSTOM_WATCHLIST_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                tickers = _normalize_ticker_list(payload.get("tickers", []))
            elif isinstance(payload, list):
                tickers = _normalize_ticker_list(payload)
            else:
                tickers = []
            if tickers:
                return tickers
    except Exception:
        pass
    return _normalize_ticker_list(CUSTOM_WATCHLIST)


def save_custom_watchlist(tickers: list) -> list:
    """Persist user watchlist and update in-memory config for current process."""
    clean = _normalize_ticker_list(tickers)
    os.makedirs(os.path.dirname(CUSTOM_WATCHLIST_FILE), exist_ok=True)
    with open(CUSTOM_WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump({"tickers": clean}, f, indent=2)

    global CUSTOM_WATCHLIST
    CUSTOM_WATCHLIST = clean
    return clean

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

# US Large-cap fallback (used when dynamic fetch is unavailable)
# Covers the full S&P 500 via 5 existing lists; deduplication happens in get_universe().
# Use as static base only – dynamic source fills the real 500.
US_LARGECAP_FALLBACK = list(dict.fromkeys(
    SP500_TOP100 + NASDAQ_100_SELECTED
))

# US Extra-large / Mega-cap fallback (top ~50 by market cap)
US_XLARGECAP_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
    "AVGO", "JPM", "LLY", "UNH", "ORCL", "V", "XOM", "MA", "COST",
    "JNJ", "PG", "WMT", "HD", "NFLX", "CRM", "BAC", "ABBV", "AMD",
    "MCD", "PEP", "KO", "CSCO", "ACN", "TMO", "ABT", "WFC", "MRK",
    "ADBE", "LIN", "DHR", "MS", "TXN", "AMGN", "NKE", "CVX", "NEE",
    "RTX", "MDT", "BMY", "ISRG", "GE", "INTU",
]

# Russell 2000 / US small-cap representative subset
RUSSELL_2000_SELECTED = [
    "CROX", "ELF", "PINS", "SMCI", "RKLB", "SOFI", "CELH", "IOT", "APPF", "FSLY",
    "RVLV", "ONON", "DUOL", "CHWY", "RIVN", "CVNA", "SFM", "ONTO", "LTH", "PCVX",
    "ATI", "MARA", "RIOT", "RUN", "ARRY", "JOBY", "ACHR", "HIMS", "UPST", "BILL",
    "PAYO", "ALGM", "PLMR", "BOOT", "SHAK", "WSC", "ASO", "PCTY", "FIVE", "EXLS",
    "SITM", "ACLS", "ANF", "DDS", "VRTS", "SLAB", "INSP", "DOCN", "CVLT", "PENN",
]

# US mid-cap representative subset (S&P 400 style mix)
US_MIDCAP_SELECTED = [
    "DKNG", "RDDT", "WSM", "RGLD", "WING", "NYT", "AUR", "WOLF", "NVT", "ONTO",
    "AA", "PR", "EMN", "RDN", "KMX", "JBLU", "ALSN", "OSK", "BWXT", "RHP",
    "SAIA", "RNR", "RLI", "RGA", "NLY", "BEN", "PB", "KBR", "MTH", "BLDR",
    "LEN", "DHI", "TOL", "MGM", "CZR", "WYNN", "BURL", "ULTA", "LKQ", "GPK",
    "EME", "WTRG", "MUSA", "GATX", "MATX", "PNW", "AIZ", "JAZZ", "ITRI", "EEFT",
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
    "russell2000": RUSSELL_2000_SELECTED,
    "midcap": US_MIDCAP_SELECTED,
    "largecap": US_LARGECAP_FALLBACK,
    "xlargecap": US_XLARGECAP_FALLBACK,
    "allassets": [],  # resolved dynamically in get_universe()
    "broad": (DAX_40 + MDAX_SELECTED + EURO_STOXX_EX_DE + SWISS_SELECTED +
              FTSE_100_SELECTED + SP500_TOP100 + NASDAQ_100_SELECTED +
              RUSSELL_2000_SELECTED + US_MIDCAP_SELECTED),
}

# Dynamic universe cache settings
DYNAMIC_UNIVERSE_TTL_HOURS = 24 * 7

# Runtime guardrails for dynamically fetched universes.
# Constituents are taken from the top of each source ordering.
# For Russell 2000 this is ordered by iShares holding weight (liquidity proxy).
DYNAMIC_UNIVERSE_MAX_CONSTITUENTS = {
    "russell2000": 300,
    "midcap": 400,
    "largecap": 510,   # keep full S&P 500
    "xlargecap": 50,   # top 50 by iShares weight = mega caps
}

# Validate fetched dynamic symbols against recent Yahoo price availability.
DYNAMIC_UNIVERSE_YAHOO_PREFILTER = {
    "russell2000": True,
    "midcap": True,
    "largecap": False,   # S&P 500 constituents are reliably listed in Yahoo
    "xlargecap": False,  # mega caps are definitely tradable
}


def _get_all_assets_universe() -> list:
    """
    Build one simplified universe that includes most stocks and ETFs we track.
    Uses dynamic universes with cache-first behavior to reduce Yahoo/API requests.
    """
    stock_static = (
        DAX_40 + MDAX_SELECTED + EURO_STOXX_EX_DE + SWISS_SELECTED + FTSE_100_SELECTED +
        SP500_TOP100 + NASDAQ_100_SELECTED + RUSSELL_2000_SELECTED + US_MIDCAP_SELECTED
    )

    dynamic_large = get_dynamic_universe(
        universe_name="largecap",
        fallback=US_LARGECAP_FALLBACK,
        ttl_hours=DYNAMIC_UNIVERSE_TTL_HOURS,
        max_constituents=DYNAMIC_UNIVERSE_MAX_CONSTITUENTS.get("largecap"),
        yahoo_prefilter=DYNAMIC_UNIVERSE_YAHOO_PREFILTER.get("largecap", False),
    )
    dynamic_mid = get_dynamic_universe(
        universe_name="midcap",
        fallback=US_MIDCAP_SELECTED,
        ttl_hours=DYNAMIC_UNIVERSE_TTL_HOURS,
        max_constituents=DYNAMIC_UNIVERSE_MAX_CONSTITUENTS.get("midcap"),
        yahoo_prefilter=DYNAMIC_UNIVERSE_YAHOO_PREFILTER.get("midcap", False),
    )
    dynamic_small = get_dynamic_universe(
        universe_name="russell2000",
        fallback=RUSSELL_2000_SELECTED,
        ttl_hours=DYNAMIC_UNIVERSE_TTL_HOURS,
        max_constituents=DYNAMIC_UNIVERSE_MAX_CONSTITUENTS.get("russell2000"),
        yahoo_prefilter=DYNAMIC_UNIVERSE_YAHOO_PREFILTER.get("russell2000", False),
    )

    etf_tickers = list(US_SECTOR_ETFS.values()) + list(EU_SECTOR_ETFS.values()) + list(INDUSTRY_ETFS.values())

    return list(dict.fromkeys(stock_static + dynamic_large + dynamic_mid + dynamic_small + etf_tickers))

def get_universe(name: str = "broad") -> list:
    name = (name or "broad").strip().lower()
    custom_watchlist = get_custom_watchlist()

    if name in ("all", "allassets"):
        base = _get_all_assets_universe()
        return list(dict.fromkeys(base + custom_watchlist))

    base = UNIVERSES.get(name, UNIVERSES["broad"])
    if name in ("russell2000", "midcap", "largecap", "xlargecap"):
        base = get_dynamic_universe(
            universe_name=name,
            fallback=base,
            ttl_hours=DYNAMIC_UNIVERSE_TTL_HOURS,
            max_constituents=DYNAMIC_UNIVERSE_MAX_CONSTITUENTS.get(name),
            yahoo_prefilter=DYNAMIC_UNIVERSE_YAHOO_PREFILTER.get(name, False),
        )
    all_tickers = list(dict.fromkeys(base + custom_watchlist))  # dedup, preserve order
    return all_tickers

# ─────────────────────────────────────────────────────────────────────────────
# INDUSTRY ETFs  (best-effort mapping from yfinance industry string → ETF ticker)
# Used for mini sparklines in the Industries drill-down view.
# Industries not listed here are still shown in the table — just without a chart.
# ─────────────────────────────────────────────────────────────────────────────

INDUSTRY_ETFS = {
    # ── Technology ────────────────────────────────────────────────────────────
    "Semiconductors":                    "SOXX",   # iShares PHLX Semiconductor
    "Semiconductor Equipment & Materials": "SOXX",
    "Software—Application":              "IGV",    # iShares S&P Software & Services
    "Software—Infrastructure":           "IGV",
    "Information Technology Services":   "IGV",
    "Electronic Components":             "SOXX",
    "Computer Hardware":                 "XLK",
    # ── Healthcare ────────────────────────────────────────────────────────────
    "Biotechnology":                     "XBI",    # SPDR S&P Biotech
    "Drug Manufacturers—General":        "PJP",    # Invesco Pharma
    "Drug Manufacturers—Specialty":      "PJP",
    "Medical Devices":                   "IHI",    # iShares Medical Devices
    "Medical Instruments & Supplies":    "IHI",
    "Diagnostics & Research":            "IHI",
    "Health Care Plans":                 "IHF",    # iShares Healthcare Providers
    "Medical Care Facilities":           "IHF",
    "Health Information Services":       "IHF",
    # ── Financials ────────────────────────────────────────────────────────────
    "Banks—Diversified":                 "KBE",    # SPDR Bank
    "Banks—Regional":                    "KRE",    # SPDR Regional Banking
    "Asset Management":                  "IAI",    # iShares Broker-Dealers
    "Capital Markets":                   "IAI",
    "Insurance—Diversified":             "KIE",    # SPDR Insurance
    "Insurance—Life":                    "KIE",
    "Insurance—Property & Casualty":     "KIE",
    "Financial Data & Stock Exchanges":  "IAI",
    # ── Energy ────────────────────────────────────────────────────────────────
    "Oil & Gas E&P":                     "XOP",    # SPDR Oil & Gas E&P
    "Oil & Gas Integrated":              "XLE",    # SPDR Energy
    "Oil & Gas Equipment & Services":    "OIH",    # VanEck Oil Services
    "Oil & Gas Refining & Marketing":    "CRAK",   # VanEck Oil Refiners
    "Oil & Gas Midstream":               "AMLP",   # Alerian MLP
    # ── Consumer Discretionary ───────────────────────────────────────────────
    "Specialty Retail":                  "XRT",    # SPDR Retail
    "Internet Retail":                   "IBUY",   # Amplify Online Retail
    "Auto Manufacturers":                "CARZ",   # Global X Autonomous & EV
    "Restaurants":                       "BITE",
    "Apparel Manufacturing":             "XRT",
    "Footwear & Accessories":            "XRT",
    "Luxury Goods":                      "LUXE",
    # ── Consumer Staples ─────────────────────────────────────────────────────
    "Beverages—Non-Alcoholic":           "PBJ",    # Invesco Food & Beverage
    "Beverages—Alcoholic":               "PBJ",
    "Food Distribution":                 "PBJ",
    "Grocery Stores":                    "XLP",    # SPDR Consumer Staples
    "Household & Personal Products":     "XLP",
    "Tobacco":                           "XLP",
    # ── Industrials ──────────────────────────────────────────────────────────
    "Aerospace & Defense":               "ITA",    # iShares Aerospace & Defense
    "Airlines":                          "JETS",   # US Global Jets
    "Trucking":                          "IYT",    # iShares Transportation
    "Railroads":                         "IYT",
    "Air Freight & Logistics":           "IYT",
    "Specialty Industrial Machinery":    "XLI",    # SPDR Industrials
    "Electrical Equipment & Parts":      "XLI",
    "Engineering & Construction":        "XLI",
    # ── Real Estate ──────────────────────────────────────────────────────────
    "REIT—Residential":                  "REZ",    # iShares Residential REIT
    "REIT—Retail":                       "RTL",
    "REIT—Industrial":                   "INDS",   # Pacer Industrial REIT
    "REIT—Office":                       "NURE",
    "REIT—Healthcare Facilities":        "CURE",
    "REIT—Diversified":                  "VNQ",    # Vanguard Real Estate
    "Real Estate Services":              "VNQ",
    # ── Materials ────────────────────────────────────────────────────────────
    "Gold":                              "GDX",    # VanEck Gold Miners
    "Silver":                            "SIL",    # Global X Silver Miners
    "Steel":                             "SLX",    # VanEck Steel
    "Chemicals":                         "XLB",    # SPDR Materials
    "Specialty Chemicals":               "XLB",
    "Agricultural Inputs":               "MOO",    # VanEck Agribusiness
    "Copper":                            "COPX",   # Global X Copper Miners
    # ── Communication ────────────────────────────────────────────────────────
    "Internet Content & Information":    "SOCL",   # Global X Social Media
    "Telecom Services":                  "IYZ",    # iShares US Telecom
    "Entertainment":                     "IYZ",
    "Electronic Gaming & Multimedia":    "HERO",   # Global X Video Games
    "Broadcasting":                      "IYZ",
    # ── Utilities ────────────────────────────────────────────────────────────
    "Utilities—Regulated Electric":      "XLU",    # SPDR Utilities
    "Utilities—Renewable":               "ICLN",   # iShares Global Clean Energy
    "Utilities—Diversified":             "XLU",
    "Solar":                             "TAN",    # Invesco Solar
}

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

# Universe-specific calibration to avoid penalizing smaller-cap universes.
# Values here override the global SCREENING defaults where relevant.
UNIVERSE_CALIBRATION = {
    "default": {
        "min_market_cap": SCREENING["min_market_cap"],
        "blended_prehn_weight": 0.85,
        "blended_filter_weight": 0.15,
        "single_stock_filters": {
            "runway_months": [6, 12, 24],
            "institutional_levels": [0.20, 0.35, 0.60],
            "revenue_growth_levels": [0.00, 0.10, 0.20],
            "gross_margin_strong": 0.40,
        },
    },
    "sp500": {
        "min_market_cap": 2_000_000_000,
        "blended_prehn_weight": 0.85,
        "blended_filter_weight": 0.15,
    },
    "nasdaq": {
        "min_market_cap": 1_000_000_000,
    },
    "focused": {
        "min_market_cap": 500_000_000,
    },
    "broad": {
        "min_market_cap": 500_000_000,
    },
    "dax": {
        "min_market_cap": 1_000_000_000,
    },
    "custom": {
        "min_market_cap": 300_000_000,
    },
    "midcap": {
        "min_market_cap": 300_000_000,
        "single_stock_filters": {
            "runway_months": [6, 12, 24],
            "institutional_levels": [0.15, 0.30, 0.50],
            "revenue_growth_levels": [0.00, 0.08, 0.16],
            "gross_margin_strong": 0.35,
        },
    },
    "russell2000": {
        "min_market_cap": 150_000_000,
        "blended_prehn_weight": 0.90,
        "blended_filter_weight": 0.10,
        "single_stock_filters": {
            "runway_months": [4, 9, 18],
            "institutional_levels": [0.10, 0.20, 0.35],
            "revenue_growth_levels": [-0.02, 0.06, 0.15],
            "gross_margin_strong": 0.30,
        },
    },
    "largecap": {
        "min_market_cap": 10_000_000_000,   # $10B+
        "blended_prehn_weight": 0.80,
        "blended_filter_weight": 0.20,      # fundamentals carry more weight
        "single_stock_filters": {
            "runway_months": [12, 24, 36],
            "institutional_levels": [0.50, 0.65, 0.80],
            "revenue_growth_levels": [0.02, 0.10, 0.18],
            "gross_margin_strong": 0.40,
        },
    },
    "xlargecap": {
        "min_market_cap": 50_000_000_000,   # $50B+ (mega cap threshold)
        "blended_prehn_weight": 0.75,
        "blended_filter_weight": 0.25,      # ownership and profitability very important
        "single_stock_filters": {
            "runway_months": [24, 36, 60],
            "institutional_levels": [0.60, 0.75, 0.85],
            "revenue_growth_levels": [0.03, 0.08, 0.15],
            "gross_margin_strong": 0.45,
        },
    },
}


def get_universe_calibration(universe_name: str) -> dict:
    """Return merged calibration profile for a given universe name."""
    base = dict(UNIVERSE_CALIBRATION.get("default", {}))
    override = UNIVERSE_CALIBRATION.get(universe_name, {})

    # Merge nested single-stock filters explicitly.
    base_filters = dict(base.get("single_stock_filters", {}))
    ov_filters = override.get("single_stock_filters", {})
    base_filters.update(ov_filters)

    base.update(override)
    base["single_stock_filters"] = base_filters
    return base

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
