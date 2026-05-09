"""LangChain @tool wrappers around the Mantis data and analysis layer.

Each tool is a thin adapter that:
1. Accepts plain types the LLM can serialize.
2. Dispatches to a Layer 1/2 function with a shared MantleClient.
3. Truncates output to keep agent context manageable.
"""

from __future__ import annotations

import io
import json
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Annotated

from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

from mantis.tools.analysis import calc_net_flow, detect_volume_anomaly
from mantis.tools.chain_client import MantleClient
from mantis.tools.data_fetchers import (
    get_address_profile,
    get_bridge_deposits,
    get_price,
    get_recent_large_transfers,
    get_token_top_holders,
)


def _truncate_json(data, max_chars: int = 4000) -> str:
    """Format JSON output and truncate if too long. Helps keep agent context lean."""
    text = json.dumps(data, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, full length: {len(text)} chars]"


def make_tools(client: MantleClient) -> list:
    """Build all tools, binding them to the given MantleClient instance."""

    # --- Layer 1: Data Access ---

    @tool
    def fetch_recent_large_transfers(
        token: str,
        min_value: float = 10_000,
        hours: float = 1.0,
    ) -> str:
        """Fetch recent ERC20 transfers above min_value on Mantle mainnet.

        Args:
            token: Token symbol. Supported: WMNT, WETH, USDT, USDC, mETH, FBTC.
                   Use empty string "" to scan all tracked tokens.
            min_value: Minimum transfer value in token units (e.g. 10000 for 10k USDT).
            hours: Look-back window in hours. Keep small (<=2) to avoid slow queries.

        Returns:
            JSON list of transfers with tx_hash, block, token, from, to, value.
            Sorted by value descending, capped at 100 entries.
        """
        token_arg = token.strip() if token and token.strip() else None
        result = get_recent_large_transfers(
            client, token=token_arg, min_value=min_value, hours=hours
        )
        return _truncate_json({
            "count": len(result),
            "transfers": result,
        })

    @tool
    def fetch_address_profile(address: str) -> str:
        """Get on-chain profile of an address: native MNT balance, ERC20 balances, tx count.

        Args:
            address: 0x-prefixed Ethereum address.

        Returns:
            JSON with address, tx_count, balances dict, and label (if known).
        """
        return _truncate_json(get_address_profile(client, address))

    @tool
    def fetch_price(token: str) -> str:
        """Get current spot price from Bybit for a token.

        Args:
            token: Token symbol (MNT, ETH, BTC, mETH supported via Bybit).

        Returns:
            JSON with price_usd, change_24h_pct, volume_24h_usd, high/low_24h.
        """
        return _truncate_json(get_price(token))

    @tool
    def fetch_token_top_holders(token: str, limit: int = 10) -> str:
        """Approximate top holders of a token by scanning recent transfer participants.

        Note: This is an approximation, not a complete holder ranking.
        Use this to find candidates for whale analysis.

        Args:
            token: Token symbol (WMNT, WETH, USDT, USDC, mETH, FBTC).
            limit: Number of holders to return (max 50).

        Returns:
            JSON list of {address, balance}, sorted by balance descending.
        """
        return _truncate_json(get_token_top_holders(client, token, min(limit, 50)))

    @tool
    def fetch_bridge_deposits(hours: float = 1.0, min_value: float = 10_000) -> str:
        """Detect large bridge deposits (L1 -> Mantle) in recent hours.

        Identifies tokens minted from the zero address on Mantle, which typically
        represents fresh capital bridged from Ethereum mainnet.

        Args:
            hours: Look-back window. Keep small (<=2) to avoid slow queries.
            min_value: Minimum mint value in token units.

        Returns:
            JSON list of bridge mints sorted by value descending.
        """
        result = get_bridge_deposits(client, hours=hours, min_value=min_value)
        return _truncate_json({
            "count": len(result),
            "deposits": result,
        })

    # --- Layer 2: Analysis Primitives ---

    @tool
    def analyze_volume_anomaly(
        token: str,
        recent_hours: int = 1,
        window_hours: int = 24,
        threshold_sigma: float = 2.0,
    ) -> str:
        """Check if a token's recent transfer volume is statistically anomalous.

        Compares the recent window's volume to a baseline computed from older
        buckets in the analysis window. Returns a z-score and anomaly flag.

        Args:
            token: Token symbol.
            recent_hours: Size of the "recent" window to test (e.g. 1 hour).
            window_hours: Total analysis window for baseline (e.g. 24 hours).
                          Must be > recent_hours.
            threshold_sigma: Z-score threshold for anomaly flag (default 2.0).

        Returns:
            JSON with z_score, is_anomalous, baseline stats, and recent volume.
        """
        return _truncate_json(detect_volume_anomaly(
            client,
            token=token,
            window_hours=window_hours,
            recent_hours=recent_hours,
            threshold_sigma=threshold_sigma,
        ))

    @tool
    def analyze_net_flow(token: str, hours: float = 1.0) -> str:
        """Compute per-address net inflow/outflow for a token in recent hours.

        Identifies which addresses are accumulating (positive net flow) vs
        distributing (negative). Useful for spotting concentrated buying or selling.

        Args:
            token: Token symbol.
            hours: Look-back window.

        Returns:
            JSON with total volume, top accumulators, top distributors, and aggregate stats.
        """
        return _truncate_json(calc_net_flow(client, token=token, hours=hours))

    # --- Layer 3: Free exploration via Python REPL ---

    repl = PythonREPL()

    @tool
    def run_python(code: str) -> str:
        """Execute Python code for ad-hoc analysis. Use ONLY when other tools are insufficient.

        The REPL has these pre-imported: pandas as pd, numpy as np, json.
        You can write any Python code; output captured from stdout.

        Args:
            code: Python source code to execute.

        Returns:
            Captured stdout, or error traceback on failure.
        """
        # Inject helpful preamble
        full_code = (
            "import json\n"
            "import pandas as pd\n"
            "import numpy as np\n"
        ) + code
        try:
            result = repl.run(full_code)
            if not result:
                return "(no stdout output — make sure to print() what you want to see)"
            if len(result) > 4000:
                return result[:4000] + f"\n... [truncated, full length: {len(result)} chars]"
            return result
        except Exception:
            return f"Error:\n{traceback.format_exc()[-1500:]}"

    return [
        fetch_recent_large_transfers,
        fetch_address_profile,
        fetch_price,
        fetch_token_top_holders,
        fetch_bridge_deposits,
        analyze_volume_anomaly,
        analyze_net_flow,
        run_python,
    ]
