"""Layer 2: Analysis tools — structured analysis primitives on raw data."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone

from mantis.tools.chain_client import MantleClient, TransferEvent
from mantis.tools.constants import TOKENS


def detect_volume_anomaly(
    client: MantleClient,
    token: str,
    window_hours: int = 168,
    recent_hours: int = 24,
    threshold_sigma: float = 2.0,
) -> dict:
    """Detect if recent transfer volume is anomalous compared to baseline.

    Compares the total transfer volume in the last `recent_hours` against
    a baseline computed from the full `window_hours` period, split into
    `recent_hours`-sized buckets.

    Returns dict with is_anomalous flag, z_score, and volumes.
    """
    token_address = TOKENS.get(token.upper())
    if not token_address:
        return {"error": f"Unknown token: {token}"}

    from_block = client.estimate_block_at(window_hours)
    recent_from_block = client.estimate_block_at(recent_hours)
    latest = client.latest_block

    transfers = client.get_erc20_transfers(
        token_address=token_address,
        from_block=from_block,
    )

    blocks_per_bucket = (latest - from_block) * recent_hours // max(window_hours, 1)
    buckets: dict[int, float] = defaultdict(float)
    for t in transfers:
        bucket_idx = (t.block_number - from_block) // max(blocks_per_bucket, 1)
        buckets[bucket_idx] += t.value_human

    recent_bucket_idx = (recent_from_block - from_block) // max(blocks_per_bucket, 1)
    historical_volumes = [v for k, v in buckets.items() if k < recent_bucket_idx]
    recent_volume = sum(v for k, v in buckets.items() if k >= recent_bucket_idx)

    if len(historical_volumes) < 2:
        return {
            "token": token,
            "recent_volume": round(recent_volume, 2),
            "is_anomalous": False,
            "reason": "insufficient historical data for comparison",
            "z_score": 0,
        }

    mean = statistics.mean(historical_volumes)
    stdev = statistics.stdev(historical_volumes)

    if stdev == 0:
        z_score = 0.0 if recent_volume == mean else float("inf")
    else:
        z_score = (recent_volume - mean) / stdev

    is_anomalous = abs(z_score) >= threshold_sigma

    return {
        "token": token,
        "window_hours": window_hours,
        "recent_hours": recent_hours,
        "recent_volume": round(recent_volume, 2),
        "baseline_mean": round(mean, 2),
        "baseline_stdev": round(stdev, 2),
        "z_score": round(z_score, 2),
        "threshold_sigma": threshold_sigma,
        "is_anomalous": is_anomalous,
        "num_historical_buckets": len(historical_volumes),
        "num_transfers_total": len(transfers),
    }


def calc_net_flow(
    client: MantleClient,
    token: str,
    hours: float = 24,
) -> dict:
    """Calculate net flow of a token: total inflows vs outflows to unique addresses.

    "Inflow" = address received tokens. "Outflow" = address sent tokens.
    Net flow per address = received - sent.
    Positive aggregate = more buying/accumulation. Negative = more selling/distribution.
    """
    token_address = TOKENS.get(token.upper())
    if not token_address:
        return {"error": f"Unknown token: {token}"}

    from_block = client.estimate_block_at(hours)
    transfers = client.get_erc20_transfers(
        token_address=token_address,
        from_block=from_block,
    )

    address_flows: dict[str, float] = defaultdict(float)
    total_volume = 0.0

    for t in transfers:
        address_flows[t.from_address] -= t.value_human
        address_flows[t.to_address] += t.value_human
        total_volume += t.value_human

    sorted_by_inflow = sorted(address_flows.items(), key=lambda x: x[1], reverse=True)
    sorted_by_outflow = sorted(address_flows.items(), key=lambda x: x[1])

    top_accumulators = [
        {"address": addr, "net_flow": round(flow, 4)}
        for addr, flow in sorted_by_inflow[:10]
        if flow > 0
    ]
    top_distributors = [
        {"address": addr, "net_flow": round(flow, 4)}
        for addr, flow in sorted_by_outflow[:10]
        if flow < 0
    ]

    total_inflow = sum(f for f in address_flows.values() if f > 0)
    total_outflow = sum(f for f in address_flows.values() if f < 0)

    return {
        "token": token,
        "hours": hours,
        "total_volume": round(total_volume, 2),
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_aggregate": round(total_inflow + total_outflow, 2),
        "num_transfers": len(transfers),
        "unique_addresses": len(address_flows),
        "top_accumulators": top_accumulators,
        "top_distributors": top_distributors,
    }
