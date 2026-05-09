"""Deploy AlphaSignalRegistry to Mantle testnet via web3.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from web3 import Web3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mantis.config import load_config

ARTIFACT = Path(__file__).parent / "AlphaSignalRegistry.json"


def deploy(private_key: str | None = None) -> str:
    cfg = load_config()
    pk = private_key or cfg.agent_private_key
    if not pk:
        raise ValueError(
            "No private key. Set AGENT_PRIVATE_KEY in .env or pass --key"
        )

    rpc_url = cfg.chain.deploy_rpc_url
    chain_id = cfg.chain.deploy_chain_id
    print(f"Deploying to {'testnet' if cfg.chain.deploy_on_testnet else 'mainnet'} "
          f"({rpc_url}, chain_id={chain_id})")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    assert w3.is_connected(), f"Cannot connect to {rpc_url}"

    acct = w3.eth.account.from_key(pk)
    print(f"Deployer: {acct.address}")

    balance = w3.eth.get_balance(acct.address)
    print(f"Balance:  {w3.from_wei(balance, 'ether')} MNT")
    if balance == 0:
        raise ValueError(
            f"Zero balance. Fund {acct.address} with testnet MNT from faucet: "
            "https://faucet.sepolia.mantle.xyz"
        )

    artifact = json.loads(ARTIFACT.read_text())
    contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])

    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.constructor().build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "chainId": chain_id,
        "gas": 800_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Tx sent:  {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    addr = receipt["contractAddress"]
    print(f"Contract deployed at: {addr}")
    print(f"Explorer: https://explorer.sepolia.mantle.xyz/address/{addr}")

    deployed_file = Path(__file__).parent / "deployed_address.txt"
    deployed_file.write_text(addr)
    print(f"Address saved to {deployed_file}")
    return addr


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--key", help="Override deployer private key")
    args = parser.parse_args()
    deploy(private_key=args.key)
