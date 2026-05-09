"""Python wrapper for AlphaSignalRegistry on-chain interactions."""

from __future__ import annotations

import json
import time
from pathlib import Path
from collections.abc import Callable
from typing import TypeVar

from web3 import Web3
from web3.contract import Contract

from mantis.agent.schema import Signal
from mantis.config import MantisConfig

ARTIFACT = Path(__file__).parent / "AlphaSignalRegistry.json"
DEPLOYED_ADDR_FILE = Path(__file__).parent / "deployed_address.txt"
T = TypeVar("T")


def _retry_call(fn: Callable[[], T], attempts: int = 5, delay: float = 1.5) -> T:
    """Retry short-lived RPC read inconsistencies after freshly mined txs."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                time.sleep(delay)
    assert last_error is not None
    raise last_error


class SignalRegistry:
    """Read/write interface to AlphaSignalRegistry contract."""

    def __init__(self, cfg: MantisConfig, contract_address: str | None = None):
        self.cfg = cfg
        rpc = cfg.chain.deploy_rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc))

        addr = contract_address or self._load_deployed_address()
        if not addr:
            raise ValueError(
                "No contract address. Deploy first with `python -m mantis.contracts.deploy`"
            )

        artifact = json.loads(ARTIFACT.read_text())
        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(addr),
            abi=artifact["abi"],
        )

        pk = cfg.agent_private_key
        self.account = self.w3.eth.account.from_key(pk) if pk else None

    def _load_deployed_address(self) -> str | None:
        if DEPLOYED_ADDR_FILE.exists():
            return DEPLOYED_ADDR_FILE.read_text().strip()
        return None

    def emit_signal(self, signal: Signal) -> dict:
        """Record a signal on-chain. Returns tx receipt dict."""
        if not self.account:
            raise ValueError("No AGENT_PRIVATE_KEY configured, cannot send tx")

        content_hash = bytes.fromhex(signal.content_hash())
        direction = signal.direction_int()
        confidence_pct = min(100, max(0, int(signal.confidence * 100)))

        tx = self.contract.functions.emitSignal(
            content_hash,
            signal.asset,
            direction,
            confidence_pct,
            signal.time_horizon,
        ).build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": self.cfg.chain.deploy_chain_id,
            "gas": 200_000,
            "gasPrice": self.w3.eth.gas_price,
        })

        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(
                f"emitSignal transaction failed: tx={tx_hash.hex()}, "
                f"gas_used={receipt['gasUsed']}"
            )

        explorer_base = (
            "https://explorer.sepolia.mantle.xyz"
            if self.cfg.chain.deploy_on_testnet
            else "https://explorer.mantle.xyz"
        )

        return {
            "tx_hash": tx_hash.hex(),
            "signal_id": self._extract_signal_id(receipt),
            "block": receipt["blockNumber"],
            "explorer_url": f"{explorer_base}/tx/0x{tx_hash.hex()}",
        }

    def _extract_signal_id(self, receipt) -> int | None:
        """Parse SignalEmitted event from receipt to get the signal ID."""
        try:
            logs = self.contract.events.SignalEmitted().process_receipt(receipt)
            if logs:
                return logs[0]["args"]["signalId"]
        except Exception:
            pass
        return None

    def verify_signal(self, signal_id: int, content: str) -> bool:
        """Check if content matches the on-chain hash for a given signal ID."""
        return _retry_call(
            lambda: self.contract.functions.verifySignal(
                signal_id, content.encode("utf-8")
            ).call()
        )

    def get_signal(self, signal_id: int) -> dict:
        """Read a signal record from chain."""
        s = _retry_call(lambda: self.contract.functions.signals(signal_id).call())
        return {
            "content_hash": "0x" + s[0].hex(),
            "timestamp": s[1],
            "emitter": s[2],
            "asset": s[3],
            "direction": s[4],
            "confidence": s[5],
            "time_horizon": s[6],
        }

    def get_signal_count(self) -> int:
        return _retry_call(lambda: self.contract.functions.getSignalCount().call())
