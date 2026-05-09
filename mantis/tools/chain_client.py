"""Low-level Mantle chain client — wraps web3.py with helpers for common queries."""

from __future__ import annotations

import time
from dataclasses import dataclass

from web3 import Web3

from mantis.config import MantisConfig
from mantis.tools.constants import ADDRESS_TO_SYMBOL, ERC20_ABI, ERC20_TRANSFER_TOPIC, TOKENS


@dataclass
class TransferEvent:
    tx_hash: str
    block_number: int
    timestamp: int
    token_symbol: str
    token_address: str
    from_address: str
    to_address: str
    value_raw: int
    value_human: float
    log_index: int


class MantleClient:
    """Thin wrapper over web3.py for Mantle mainnet data queries."""

    def __init__(self, config: MantisConfig):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.chain.data_rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {config.chain.data_rpc_url}")

    @property
    def latest_block(self) -> int:
        return self.w3.eth.block_number

    def get_block(self, block_number: int | str = "latest") -> dict:
        return dict(self.w3.eth.get_block(block_number))

    def estimate_block_at(self, hours_ago: float) -> int:
        """Estimate block number N hours ago. Mantle ~2s block time."""
        blocks_per_hour = 3600 // 2
        return max(0, self.latest_block - int(hours_ago * blocks_per_hour))

    def get_erc20_transfers(
        self,
        token_address: str | None = None,
        from_block: int | None = None,
        to_block: int | str = "latest",
        address: str | None = None,
        max_blocks_per_query: int = 2000,
    ) -> list[TransferEvent]:
        """Query ERC20 Transfer events from chain logs.

        Args:
            token_address: Filter to a specific token. None = all tracked tokens.
            from_block: Start block. None = 1 hour ago.
            to_block: End block.
            address: Filter transfers involving this address (as sender or receiver).
            max_blocks_per_query: Chunk size to avoid RPC limits.
        """
        if from_block is None:
            from_block = self.estimate_block_at(1.0)

        if to_block == "latest":
            to_block = self.latest_block

        if token_address:
            token_address = Web3.to_checksum_address(token_address)

        token_addresses = [token_address] if token_address else list(TOKENS.values())

        all_transfers = []
        current = from_block
        while current <= to_block:
            chunk_end = min(current + max_blocks_per_query - 1, to_block)
            filter_params: dict = {
                "fromBlock": hex(current),
                "toBlock": hex(chunk_end),
                "topics": [ERC20_TRANSFER_TOPIC],
            }
            if len(token_addresses) == 1:
                filter_params["address"] = token_addresses[0]
            else:
                filter_params["address"] = token_addresses

            try:
                logs = self.w3.eth.get_logs(filter_params)
            except Exception:
                # Some RPCs reject large ranges; halve the chunk
                if max_blocks_per_query > 100:
                    smaller = self.get_erc20_transfers(
                        token_address=token_address,
                        from_block=current,
                        to_block=chunk_end,
                        address=address,
                        max_blocks_per_query=max_blocks_per_query // 2,
                    )
                    all_transfers.extend(smaller)
                    current = chunk_end + 1
                    continue
                raise

            for log in logs:
                transfer = self._parse_transfer_log(log)
                if transfer is None:
                    continue
                if address:
                    addr_lower = address.lower()
                    if transfer.from_address.lower() != addr_lower and transfer.to_address.lower() != addr_lower:
                        continue
                all_transfers.append(transfer)

            current = chunk_end + 1

        return all_transfers

    def _parse_transfer_log(self, log) -> TransferEvent | None:
        topics = log.get("topics", [])
        if len(topics) < 3:
            return None

        token_addr = log["address"].lower()
        symbol = ADDRESS_TO_SYMBOL.get(token_addr, "UNKNOWN")

        from mantis.tools.constants import TOKEN_DECIMALS
        decimals = TOKEN_DECIMALS.get(symbol, 18)

        from_addr = "0x" + topics[1].hex()[-40:]
        to_addr = "0x" + topics[2].hex()[-40:]
        value_raw = int(log["data"].hex(), 16) if log["data"] else 0
        value_human = value_raw / (10**decimals)

        return TransferEvent(
            tx_hash=log["transactionHash"].hex(),
            block_number=log["blockNumber"],
            timestamp=0,  # filled in batch later if needed
            token_symbol=symbol,
            token_address=token_addr,
            from_address=Web3.to_checksum_address(from_addr),
            to_address=Web3.to_checksum_address(to_addr),
            value_raw=value_raw,
            value_human=value_human,
            log_index=log["logIndex"],
        )

    def get_native_balance(self, address: str) -> float:
        """Get MNT balance in human-readable units."""
        bal = self.w3.eth.get_balance(Web3.to_checksum_address(address))
        return bal / 1e18

    def get_token_balance(self, token_address: str, holder: str) -> float:
        """Get ERC20 token balance."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        raw = contract.functions.balanceOf(Web3.to_checksum_address(holder)).call()
        symbol = ADDRESS_TO_SYMBOL.get(token_address.lower(), "UNKNOWN")
        from mantis.tools.constants import TOKEN_DECIMALS
        decimals = TOKEN_DECIMALS.get(symbol, 18)
        return raw / (10**decimals)

    def get_transaction_count(self, address: str) -> int:
        return self.w3.eth.get_transaction_count(Web3.to_checksum_address(address))
