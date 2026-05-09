"""Layer 1: Data access tools — raw data fetchers for the Agent."""

from __future__ import annotations

import time
from typing import Any

import httpx

from mantis.config import MantisConfig
from mantis.tools.chain_client import MantleClient, TransferEvent
from mantis.tools.constants import ADDRESS_TO_SYMBOL, TOKENS, TOKEN_DECIMALS


def get_recent_large_transfers(
    client: MantleClient,
    token: str | None = None,
    min_value: float = 10_000,
    hours: float = 24,
) -> list[dict]:
    """Get recent large ERC20 transfers on Mantle.

    Args:
        token: Token symbol (e.g. "WMNT", "mETH") or None for all tracked tokens.
        min_value: Minimum transfer value in token units.
        hours: How far back to look.

    Returns:
        List of transfer dicts sorted by value descending.
    """
    token_address = TOKENS.get(token.upper()) if token else None
    from_block = client.estimate_block_at(hours)

    transfers = client.get_erc20_transfers(
        token_address=token_address,
        from_block=from_block,
    )

    large = [t for t in transfers if t.value_human >= min_value]
    large.sort(key=lambda t: t.value_human, reverse=True)

    return [
        {
            "tx_hash": t.tx_hash,
            "block": t.block_number,
            "token": t.token_symbol,
            "from": t.from_address,
            "to": t.to_address,
            "value": round(t.value_human, 4),
        }
        for t in large[:100]  # cap at 100 results
    ]


def get_address_profile(client: MantleClient, address: str) -> dict:
    """Get a profile of an address: balances, tx count, known label.

    Returns a dict with native balance, token balances, and transaction count.
    """
    balances = {}
    balances["MNT"] = round(client.get_native_balance(address), 4)

    for symbol, token_addr in TOKENS.items():
        try:
            bal = client.get_token_balance(token_addr, address)
            if bal > 0:
                balances[symbol] = round(bal, 6)
        except Exception:
            continue

    tx_count = client.get_transaction_count(address)

    return {
        "address": address,
        "tx_count": tx_count,
        "balances": balances,
        "label": None,  # enrichment happens via enrich_with_labels
    }


def get_price(token: str = "MNT", source: str = "bybit") -> dict:
    """Get current price from Bybit.

    Args:
        token: Token symbol.
        source: Data source (currently only "bybit").
    """
    symbol_map = {
        "MNT": "MNTUSDT",
        "WMNT": "MNTUSDT",
        "ETH": "ETHUSDT",
        "WETH": "ETHUSDT",
        "mETH": "METHUSDT",
        "BTC": "BTCUSDT",
        "FBTC": "BTCUSDT",
    }
    bybit_symbol = symbol_map.get(token.upper(), f"{token.upper()}USDT")
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={bybit_symbol}"

    try:
        with httpx.Client(timeout=10) as http:
            resp = http.get(url)
            data = resp.json()
            if data.get("retCode") != 0:
                return {"token": token, "price_usd": None, "error": data.get("retMsg")}

            ticker = data["result"]["list"][0]
            return {
                "token": token,
                "price_usd": float(ticker["lastPrice"]),
                "change_24h_pct": float(ticker.get("price24hPcnt", 0)) * 100,
                "volume_24h_usd": float(ticker.get("turnover24h", 0)),
                "high_24h": float(ticker.get("highPrice24h", 0)),
                "low_24h": float(ticker.get("lowPrice24h", 0)),
                "source": "bybit",
            }
    except Exception as e:
        return {"token": token, "price_usd": None, "error": str(e)}


def get_token_top_holders(client: MantleClient, token: str, limit: int = 20) -> list[dict]:
    """Get top holders of a token by scanning recent large transfers.

    Note: Without an indexer, we approximate by collecting unique addresses
    from recent transfers and checking their balances. This is an approximation.
    """
    token_address = TOKENS.get(token.upper())
    if not token_address:
        return [{"error": f"Unknown token: {token}"}]

    from_block = client.estimate_block_at(72)  # scan 3 days
    transfers = client.get_erc20_transfers(
        token_address=token_address,
        from_block=from_block,
    )

    unique_addresses = set()
    for t in transfers:
        unique_addresses.add(t.to_address)
        unique_addresses.add(t.from_address)

    holders = []
    for addr in list(unique_addresses)[:200]:  # cap addresses to check
        try:
            bal = client.get_token_balance(token_address, addr)
            if bal > 0:
                holders.append({"address": addr, "balance": round(bal, 6)})
        except Exception:
            continue

    holders.sort(key=lambda h: h["balance"], reverse=True)
    return holders[:limit]


def get_bridge_deposits(
    client: MantleClient,
    hours: float = 24,
    min_value: float = 10_000,
) -> list[dict]:
    """Detect large bridge deposits by looking for transfers from the zero address
    or known bridge/mint patterns on L2.

    On Mantle L2, bridged tokens appear as mints (from 0x0) or transfers from
    bridge relay contracts. We detect these by looking for transfers where
    from_address is the zero address.
    """
    from_block = client.estimate_block_at(hours)
    transfers = client.get_erc20_transfers(from_block=from_block)

    zero_addr = "0x" + "0" * 40
    deposits = [
        t for t in transfers
        if t.from_address.lower() == zero_addr and t.value_human >= min_value
    ]
    deposits.sort(key=lambda t: t.value_human, reverse=True)

    return [
        {
            "tx_hash": t.tx_hash,
            "block": t.block_number,
            "token": t.token_symbol,
            "to": t.to_address,
            "value": round(t.value_human, 4),
            "type": "bridge_mint",
        }
        for t in deposits[:50]
    ]
