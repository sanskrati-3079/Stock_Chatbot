"""
ticker_resolver.py
Resolves free-text (company names, tickers, chat sentences) into a valid
Yahoo Finance ticker symbol. Because we use yfinance under the hood, this
effectively covers almost EVERY listed stock in the world (NYSE, NASDAQ,
NSE, BSE, LSE, etc.) as long as the correct suffix is used
(e.g. RELIANCE.NS for NSE, TCS.BO for BSE, AAPL for NASDAQ).
"""

import re
import threading

import yfinance as yf
from cachetools import TTLCache

# A curated map of common company names -> Yahoo Finance tickers.
# This is only a convenience layer for chat-style queries like
# "should I buy reliance" -> resolves to RELIANCE.NS directly
# without needing to hit the network search API.
COMMON_NAME_MAP = {
    # ---- Indian stocks (NSE) ----
    "reliance": "RELIANCE.NS", "tcs": "TCS.NS", "infosys": "INFY.NS",
    "infy": "INFY.NS", "hdfc bank": "HDFCBANK.NS", "hdfc": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS", "icici": "ICICIBANK.NS",
    "sbi": "SBIN.NS", "state bank": "SBIN.NS", "itc": "ITC.NS",
    "bharti airtel": "BHARTIARTL.NS", "airtel": "BHARTIARTL.NS",
    "wipro": "WIPRO.NS", "hcl tech": "HCLTECH.NS", "hcl": "HCLTECH.NS",
    "maruti": "MARUTI.NS", "maruti suzuki": "MARUTI.NS",
    "tata motors": "TATAMOTORS.NS", "tata steel": "TATASTEEL.NS",
    "adani enterprises": "ADANIENT.NS", "adani": "ADANIENT.NS",
    "adani power": "ADANIPOWER.NS", "adani green": "ADANIGREEN.NS",
    "axis bank": "AXISBANK.NS", "axis": "AXISBANK.NS",
    "kotak bank": "KOTAKBANK.NS", "kotak": "KOTAKBANK.NS",
    "asian paints": "ASIANPAINT.NS", "bajaj finance": "BAJFINANCE.NS",
    "bajaj auto": "BAJAJ-AUTO.NS", "sun pharma": "SUNPHARMA.NS",
    "titan": "TITAN.NS", "ntpc": "NTPC.NS", "ongc": "ONGC.NS",
    "power grid": "POWERGRID.NS", "l&t": "LT.NS", "larsen": "LT.NS",
    "zomato": "ZOMATO.NS", "paytm": "PAYTM.NS", "nykaa": "NYKAA.NS",
    "irctc": "IRCTC.NS", "dmart": "DMART.NS", "avenue supermarts": "DMART.NS",
    "vedanta": "VEDL.NS", "coal india": "COALINDIA.NS",
    "yes bank": "YESBANK.NS", "idea": "IDEA.NS", "vodafone idea": "IDEA.NS",
    "nifty": "^NSEI", "sensex": "^BSESN", "bank nifty": "^NSEBANK",

    # ---- US stocks (NASDAQ / NYSE) ----
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
    "alphabet": "GOOGL", "amazon": "AMZN", "tesla": "TSLA",
    "meta": "META", "facebook": "META", "nvidia": "NVDA",
    "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
    "ibm": "IBM", "oracle": "ORCL", "salesforce": "CRM",
    "coca cola": "KO", "coke": "KO", "pepsi": "PEP",
    "walmart": "WMT", "disney": "DIS", "boeing": "BA",
    "jpmorgan": "JPM", "jp morgan": "JPM", "goldman sachs": "GS",
    "visa": "V", "mastercard": "MA", "paypal": "PYPL",
    "berkshire": "BRK-B", "berkshire hathaway": "BRK-B",
    "exxon": "XOM", "chevron": "CVX", "pfizer": "PFE",
    "johnson & johnson": "JNJ", "johnson and johnson": "JNJ",
    "starbucks": "SBUX", "mcdonalds": "MCD", "nike": "NKE",
    "uber": "UBER", "airbnb": "ABNB", "shopify": "SHOP",
    "spacex": "SPACEX", "palantir": "PLTR", "snowflake": "SNOW",
    "s&p 500": "^GSPC", "sp500": "^GSPC", "dow jones": "^DJI",
    "nasdaq": "^IXIC",

    # ---- Crypto (bonus, also served by yfinance) ----
    "bitcoin": "BTC-USD", "ethereum": "ETH-USD", "dogecoin": "DOGE-USD",
}

# Words that are safe to strip out of a chat sentence before ticker matching
_STOPWORDS = {
    "should", "i", "buy", "sell", "hold", "predict", "prediction",
    "price", "of", "the", "stock", "share", "shares", "for", "is",
    "a", "good", "will", "go", "up", "down", "today", "tomorrow",
    "what", "about", "tell", "me", "analyse", "analyze", "check",
    "forecast", "can", "you", "please", "kya", "hai", "batao",
    "karo", "karu", "bech", "bechna", "kharid", "kharidna",
    "how", "doing", "are", "do", "does", "now", "worth", "invest",
    "in", "to", "my", "outlook", "looking", "buying", "selling", "chahiye",
}

_TICKER_REGEX = re.compile(r"^[A-Z0-9.\-\^]{1,15}$")


def _looks_like_ticker(token: str) -> bool:
    return bool(_TICKER_REGEX.match(token.upper()))


# Only successful lookups are cached, so a transient network error or rate
# limit doesn't permanently break a query for the life of the server.
_SEARCH_CACHE: TTLCache = TTLCache(maxsize=512, ttl=24 * 3600)
_SEARCH_LOCK = threading.Lock()


def _yf_search(query: str):
    """Fallback: hit Yahoo Finance's search endpoint via yfinance."""
    with _SEARCH_LOCK:
        if query in _SEARCH_CACHE:
            return _SEARCH_CACHE[query]
    try:
        result = yf.Search(query, max_results=1)
        quotes = getattr(result, "quotes", None) or []
    except Exception:
        return None
    symbol = quotes[0].get("symbol") if quotes else None
    with _SEARCH_LOCK:
        _SEARCH_CACHE[query] = symbol
    return symbol


def resolve_ticker(text: str) -> str | None:
    """
    Try hard to turn free text into a valid ticker symbol.
    Order of attempts:
      1. Exact match in COMMON_NAME_MAP
      2. Raw text already looks like a ticker (e.g. "AAPL", "TCS.NS")
      3. Multi-word substring match against COMMON_NAME_MAP
      4. Single token that looks like a ticker, extracted from a sentence
      5. Yahoo Finance search API fallback (covers virtually any stock)
    """
    if not text:
        return None

    raw = text.strip()
    lowered = raw.lower()

    # 1. direct name map hit
    if lowered in COMMON_NAME_MAP:
        return COMMON_NAME_MAP[lowered]

    # 2. raw text itself is already a valid-looking ticker
    if _looks_like_ticker(raw) and len(raw.split()) == 1:
        return raw.upper()

    # 3. whole-word / whole-phrase match anywhere in the sentence
    #    (word-boundary regex avoids false hits like "bitcoin" matching "itc")
    #    Sort longer names first so multi-word names (e.g. "hdfc bank") are
    #    preferred over shorter overlapping ones (e.g. "hdfc").
    for name in sorted(COMMON_NAME_MAP.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, lowered):
            return COMMON_NAME_MAP[name]

    # 4. scan tokens for a ticker-looking word not in stopwords
    tokens = re.findall(r"[A-Za-z0-9.\-\^]+", raw)
    candidates = [t for t in tokens if t.lower() not in _STOPWORDS]
    for tok in candidates:
        if _looks_like_ticker(tok) and not tok.isalpha() or (tok.isupper() and len(tok) <= 6):
            return tok.upper()

    # 5. last resort — ask Yahoo Finance's search
    guess = " ".join(candidates) if candidates else raw
    found = _yf_search(guess)
    if found:
        return found

    return None
