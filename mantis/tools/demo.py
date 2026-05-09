"""Smoke test: run all data tools against Mantle mainnet."""

from __future__ import annotations

import json
import sys
import time

from mantis.config import load_config
from mantis.tools.chain_client import MantleClient
from mantis.tools.data_fetchers import (
    get_address_profile,
    get_bridge_deposits,
    get_price,
    get_recent_large_transfers,
)
from mantis.tools.analysis import calc_net_flow, detect_volume_anomaly


def pp(label: str, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str)[:2000])


def main():
    cfg = load_config()
    print("Connecting to Mantle mainnet...")
    client = MantleClient(cfg)
    print(f"Connected. Latest block: {client.latest_block:,}")

    # 1. Price check
    t0 = time.time()
    price = get_price("MNT")
    pp(f"get_price('MNT') [{time.time()-t0:.1f}s]", price)

    price_eth = get_price("ETH")
    pp(f"get_price('ETH')", price_eth)

    # 2. Recent large WMNT transfers (last 1h, lowered threshold for demo)
    t0 = time.time()
    transfers = get_recent_large_transfers(client, token="WMNT", min_value=1000, hours=1)
    pp(f"get_recent_large_transfers(WMNT, min=1000, 1h) [{time.time()-t0:.1f}s] — {len(transfers)} found", transfers[:5])

    # 3. Recent large USDT transfers
    t0 = time.time()
    transfers_usdt = get_recent_large_transfers(client, token="USDT", min_value=1000, hours=1)
    pp(f"get_recent_large_transfers(USDT, min=1000, 1h) [{time.time()-t0:.1f}s] — {len(transfers_usdt)} found", transfers_usdt[:5])

    # 4. Address profile (use a top address from transfers if we got any)
    if transfers:
        addr = transfers[0]["to"]
        t0 = time.time()
        profile = get_address_profile(client, addr)
        pp(f"get_address_profile({addr[:10]}...) [{time.time()-t0:.1f}s]", profile)

    # 5. Bridge deposits
    t0 = time.time()
    deposits = get_bridge_deposits(client, hours=1, min_value=100)
    pp(f"get_bridge_deposits(1h, min=100) [{time.time()-t0:.1f}s] — {len(deposits)} found", deposits[:5])

    # 6. Net flow analysis
    t0 = time.time()
    flow = calc_net_flow(client, token="WMNT", hours=1)
    pp(f"calc_net_flow(WMNT, 1h) [{time.time()-t0:.1f}s]", flow)

    print(f"\n{'='*60}")
    print("  Smoke test complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
