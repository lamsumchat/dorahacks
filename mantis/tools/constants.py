"""Mantle mainnet token addresses and ABI fragments."""

from web3 import Web3

# --- Mantle Mainnet Token Addresses ---

TOKENS = {
    "WMNT": Web3.to_checksum_address("0x78c1b0c915c4faa5fffa6cabf0219da63d7f4cb8"),
    "WETH": Web3.to_checksum_address("0xdEAddEaDdeadDEadDEADDEAddEADDEAddead1111"),
    "USDT": Web3.to_checksum_address("0x201EBa5CC46D216Ce6DC03F6a759e8E766e956aE"),
    "USDC": Web3.to_checksum_address("0x09Bc4E0D864854c6aFB6eB9A9cdF58aC190D0dF9"),
    "mETH": Web3.to_checksum_address("0xcDA86A272531e8640cD7F1a92c01839911B90bB0"),
    "FBTC": Web3.to_checksum_address("0xC96dE26018A54D51c097160568752c4E3BD6C364"),
}

TOKEN_DECIMALS = {
    "WMNT": 18,
    "WETH": 18,
    "USDT": 6,
    "USDC": 6,
    "mETH": 18,
    "FBTC": 8,
    "MNT": 18,  # native
}

# Reverse lookup: address -> symbol
ADDRESS_TO_SYMBOL = {addr.lower(): sym for sym, addr in TOKENS.items()}

# ERC20 Transfer event topic
ERC20_TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,uint256,uint256)").hex()
# Correct topic for Transfer(address indexed, address indexed, uint256)
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Mantle L1 Bridge (on Ethereum mainnet) — for reference
L1_STANDARD_BRIDGE = "0x95fC37A27a2f68e3A647CDc081F0A89bb47c3012"

# Minimal ERC20 ABI for balance/decimals/symbol queries
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]
