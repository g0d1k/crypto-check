"""
Small wrapper around the free CoinGecko API (no API key required).

Docs: https://docs.coingecko.com/reference/introduction
"""

from io import BytesIO

import requests
from PIL import Image

from . import __version__

BASE_URL = "https://api.coingecko.com/api/v3"
TIMEOUT = 10  # seconds

_session = requests.Session()
_session.headers.update({"Accept": "application/json", "User-Agent": f"CryptoCheck/{__version__}"})


class CryptoAPIError(Exception):
    """Raised when something goes wrong talking to CoinGecko."""


class CoinNotFoundError(CryptoAPIError):
    """Raised when a search returns no matching coin."""


def _get(path, params=None):
    """GET a CoinGecko endpoint and return the decoded JSON."""
    try:
        response = _session.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
    except requests.ConnectionError:
        raise CryptoAPIError("Can't reach CoinGecko. Check your internet connection.")
    except requests.Timeout:
        raise CryptoAPIError("CoinGecko took too long to respond. Try again.")

    if response.status_code == 429:
        raise CryptoAPIError("Rate limit hit (free API). Wait a minute and try again.")
    if not response.ok:
        raise CryptoAPIError(f"CoinGecko returned an error ({response.status_code}).")
    return response.json()


def search_coins(query):
    """
    Look up coins by name or ticker symbol (e.g. "bitcoin" or "btc").

    Returns a list of matches with the best match first: exact name/symbol
    matches come first, and among those the biggest coin (by market cap rank)
    wins. That way "eth" and "Ethereum" both find Ethereum, not some tiny
    token that happens to use the same ticker.
    """
    query = query.strip()
    if not query:
        raise CoinNotFoundError("Type a coin name or symbol first.")

    coins = _get("/search", {"query": query}).get("coins", [])
    if not coins:
        raise CoinNotFoundError(f'No coin found for "{query}".')

    q = query.lower()

    def score(coin):
        exact = q in (coin["symbol"].lower(), coin["name"].lower(), coin["id"])
        rank = coin.get("market_cap_rank") or float("inf")
        # Exact matches first, then by rank. sorted() is stable, so ties keep CoinGecko's order.
        return (not exact, rank if exact else 0)

    return sorted(coins, key=score)


def get_market_data(coin_id, currency="usd"):
    """Fetch price, stats and a 7-day sparkline for one coin."""
    data = _get(
        "/coins/markets",
        {
            "vs_currency": currency,
            "ids": coin_id,
            "sparkline": "true",
            "price_change_percentage": "1h,24h,7d",
        },
    )
    if not data:
        raise CoinNotFoundError(f'No market data for "{coin_id}".')
    return data[0]


def get_logo(url, size=64):
    """Download a coin logo and return it as a PIL image (or None on failure)."""
    try:
        response = _session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA").resize((size, size), Image.LANCZOS)
    except (requests.RequestException, OSError):
        return None
