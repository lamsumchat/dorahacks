"""E2E test: compile → deploy → emit signal → verify on-chain.

Requires AGENT_PRIVATE_KEY with testnet MNT in .env.
"""

from __future__ import annotations

import json
import sys

from mantis.agent.schema import Signal
from mantis.config import load_config
from mantis.contracts.registry import SignalRegistry


def run_e2e():
    cfg = load_config()

    if not cfg.agent_private_key:
        print("[!] AGENT_PRIVATE_KEY not set in .env")
        print("    Generate one and fund it with testnet MNT:")
        print()
        _gen_wallet()
        sys.exit(1)

    print("=== Step 1: Connect to registry ===")
    registry = SignalRegistry(cfg)
    count_before = registry.get_signal_count()
    print(f"  Signals on-chain: {count_before}")

    print("\n=== Step 2: Create test signal ===")
    test_signal = Signal(
        asset="WMNT",
        direction="bullish",
        confidence=0.72,
        time_horizon="4h",
        key_evidence=[
            "Large 500K WMNT transfer detected",
            "Volume anomaly z-score 3.2 in last hour",
        ],
        reasoning_summary="Significant whale accumulation pattern on WMNT with "
        "above-average volume, suggesting short-term bullish momentum.",
        critic_result="PASS",
        critic_notes="Critic verified volume anomaly via independent tool call.",
    )
    print(f"  Asset:      {test_signal.asset}")
    print(f"  Direction:  {test_signal.direction}")
    print(f"  Confidence: {test_signal.confidence}")
    print(f"  Hash:       {test_signal.content_hash()[:32]}...")

    print("\n=== Step 3: Emit signal on-chain ===")
    result = registry.emit_signal(test_signal)
    print(f"  Tx Hash:     0x{result['tx_hash']}")
    print(f"  Signal ID:   {result['signal_id']}")
    print(f"  Block:       {result['block']}")
    print(f"  Explorer:    {result['explorer_url']}")

    print("\n=== Step 4: Read back from chain ===")
    on_chain = registry.get_signal(result["signal_id"])
    print(f"  Content hash: {on_chain['content_hash']}")
    print(f"  Asset:        {on_chain['asset']}")
    print(f"  Direction:    {on_chain['direction']}")
    print(f"  Confidence:   {on_chain['confidence']}%")
    print(f"  Time horizon: {on_chain['time_horizon']}")

    print("\n=== Step 5: Verify content hash ===")
    canonical = json.dumps(
        test_signal.model_dump(exclude={"signal_id"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    is_valid = registry.verify_signal(result["signal_id"], canonical)
    print(f"  Verification: {'PASS' if is_valid else 'FAIL'}")

    count_after = registry.get_signal_count()
    print(f"\n  Signals on-chain: {count_before} → {count_after}")

    print("\n" + "=" * 50)
    if is_valid:
        print("  E2E TEST PASSED")
    else:
        print("  E2E TEST FAILED — hash mismatch")
        sys.exit(1)
    print("=" * 50)


def _gen_wallet():
    """Helper: generate a new Ethereum wallet for testing."""
    from web3 import Web3

    w3 = Web3()
    acct = w3.eth.account.create()
    print(f"  New wallet address: {acct.address}")
    print(f"  Private key:        {acct.key.hex()}")
    print()
    print(f"  1. Add to .env:  AGENT_PRIVATE_KEY={acct.key.hex()}")
    print(f"  2. Fund with testnet MNT: https://faucet.sepolia.mantle.xyz")
    print(f"     (paste address: {acct.address})")


if __name__ == "__main__":
    run_e2e()
