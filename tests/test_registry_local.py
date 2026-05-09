"""Local E2E test for AlphaSignalRegistry using py-evm (no real testnet needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from mantis.agent.schema import Signal

ARTIFACT = Path(__file__).resolve().parents[1] / "mantis" / "contracts" / "AlphaSignalRegistry.json"


@pytest.fixture
def w3():
    return Web3(EthereumTesterProvider())


@pytest.fixture
def deployed_contract(w3):
    artifact = json.loads(ARTIFACT.read_text())
    acct = w3.eth.accounts[0]
    Contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx_hash = Contract.constructor().transact({"from": acct})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(address=receipt["contractAddress"], abi=artifact["abi"])


@pytest.fixture
def test_signal():
    return Signal(
        asset="WMNT",
        direction="bullish",
        confidence=0.72,
        time_horizon="4h",
        key_evidence=["Large transfer detected", "Volume anomaly z=3.2"],
        reasoning_summary="Whale accumulation on WMNT with above-average volume.",
        critic_result="PASS",
        critic_notes="Critic verified the anomaly.",
    )


class TestAlphaSignalRegistry:
    def test_initial_count_is_zero(self, deployed_contract):
        assert deployed_contract.functions.getSignalCount().call() == 0

    def test_emit_signal(self, w3, deployed_contract, test_signal):
        acct = w3.eth.accounts[0]
        content_hash = bytes.fromhex(test_signal.content_hash())
        confidence_pct = int(test_signal.confidence * 100)

        tx_hash = deployed_contract.functions.emitSignal(
            content_hash,
            test_signal.asset,
            test_signal.direction_int(),
            confidence_pct,
            test_signal.time_horizon,
        ).transact({"from": acct})

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        assert receipt["status"] == 1

        logs = deployed_contract.events.SignalEmitted().process_receipt(receipt)
        assert len(logs) == 1
        assert logs[0]["args"]["signalId"] == 0
        assert logs[0]["args"]["asset"] == "WMNT"
        assert logs[0]["args"]["direction"] == 1
        assert logs[0]["args"]["confidence"] == 72

        assert deployed_contract.functions.getSignalCount().call() == 1

    def test_read_signal(self, w3, deployed_contract, test_signal):
        acct = w3.eth.accounts[0]
        content_hash = bytes.fromhex(test_signal.content_hash())
        confidence_pct = int(test_signal.confidence * 100)

        deployed_contract.functions.emitSignal(
            content_hash,
            test_signal.asset,
            test_signal.direction_int(),
            confidence_pct,
            test_signal.time_horizon,
        ).transact({"from": acct})

        s = deployed_contract.functions.signals(0).call()
        assert s[0] == content_hash  # contentHash
        assert s[3] == "WMNT"        # asset
        assert s[4] == 1             # direction (bullish)
        assert s[5] == 72            # confidence
        assert s[6] == "4h"          # timeHorizon

    def test_verify_signal_correct_content(self, w3, deployed_contract, test_signal):
        acct = w3.eth.accounts[0]
        content_hash = bytes.fromhex(test_signal.content_hash())
        confidence_pct = int(test_signal.confidence * 100)

        deployed_contract.functions.emitSignal(
            content_hash,
            test_signal.asset,
            test_signal.direction_int(),
            confidence_pct,
            test_signal.time_horizon,
        ).transact({"from": acct})

        canonical = json.dumps(
            test_signal.model_dump(exclude={"signal_id"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        assert deployed_contract.functions.verifySignal(
            0, canonical.encode("utf-8")
        ).call() is True

    def test_verify_signal_wrong_content(self, w3, deployed_contract, test_signal):
        acct = w3.eth.accounts[0]
        content_hash = bytes.fromhex(test_signal.content_hash())
        confidence_pct = int(test_signal.confidence * 100)

        deployed_contract.functions.emitSignal(
            content_hash,
            test_signal.asset,
            test_signal.direction_int(),
            confidence_pct,
            test_signal.time_horizon,
        ).transact({"from": acct})

        assert deployed_contract.functions.verifySignal(
            0, b"tampered content"
        ).call() is False

    def test_multiple_signals(self, w3, deployed_contract):
        acct = w3.eth.accounts[0]

        for i, (asset, direction) in enumerate([
            ("WMNT", 1),
            ("mETH", -1),
            ("USDT", 0),
        ]):
            deployed_contract.functions.emitSignal(
                b"\x00" * 32,
                asset,
                direction,
                50,
                "1h",
            ).transact({"from": acct})

        assert deployed_contract.functions.getSignalCount().call() == 3
        assert deployed_contract.functions.signals(1).call()[3] == "mETH"
        assert deployed_contract.functions.signals(2).call()[4] == 0  # neutral
