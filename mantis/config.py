"""Mantis configuration — LLM providers, chain endpoints, API keys."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    provider: str = "zhipu"
    model: str = "glm-4-plus"

    @property
    def api_key_env_var(self) -> str:
        mapping = {
            "zhipu": "ZHIPU_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        return mapping.get(self.provider, f"{self.provider.upper()}_API_KEY")

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env_var)


@dataclass
class ChainConfig:
    mainnet_rpc: str = field(
        default_factory=lambda: os.getenv("MANTLE_RPC_URL", "https://rpc.mantle.xyz")
    )
    testnet_rpc: str = field(
        default_factory=lambda: os.getenv(
            "MANTLE_TESTNET_RPC_URL", "https://rpc.sepolia.mantle.xyz"
        )
    )
    explorer_api_mainnet: str = field(
        default_factory=lambda: os.getenv(
            "MANTLE_EXPLORER_API_URL", "https://explorer.mantle.xyz/api"
        )
    )
    explorer_api_testnet: str = "https://explorer.sepolia.mantle.xyz/api"
    chain_id_mainnet: int = 5000
    chain_id_testnet: int = 5003
    deploy_on_testnet: bool = True

    @property
    def data_rpc_url(self) -> str:
        """Mainnet RPC for data collection (real whale activity)."""
        return self.mainnet_rpc

    @property
    def deploy_rpc_url(self) -> str:
        """Testnet RPC for contract deployment (free gas)."""
        return self.testnet_rpc if self.deploy_on_testnet else self.mainnet_rpc

    @property
    def deploy_chain_id(self) -> int:
        return self.chain_id_testnet if self.deploy_on_testnet else self.chain_id_mainnet

    @property
    def explorer_api(self) -> str:
        return self.explorer_api_mainnet


@dataclass
class SubgraphConfig:
    blocks: str = "https://subgraph-api.mantle.xyz/subgraphs/name/cryptoalgebra/blocks"


@dataclass
class MantisConfig:
    main_llm: LLMConfig = field(default_factory=LLMConfig)
    critic_llm: LLMConfig = field(
        default_factory=lambda: LLMConfig(provider="zhipu", model="glm-4-flash")
    )
    reviewer_llm: LLMConfig = field(
        default_factory=lambda: LLMConfig(provider="zhipu", model="glm-4-flash")
    )
    chain: ChainConfig = field(default_factory=ChainConfig)
    subgraphs: SubgraphConfig = field(default_factory=SubgraphConfig)

    bybit_api_key: str = field(default_factory=lambda: os.getenv("BYBIT_API_KEY", ""))
    bybit_api_secret: str = field(default_factory=lambda: os.getenv("BYBIT_API_SECRET", ""))
    covalent_api_key: str = field(default_factory=lambda: os.getenv("COVALENT_API_KEY", ""))
    agent_private_key: str = field(default_factory=lambda: os.getenv("AGENT_PRIVATE_KEY", ""))

    max_critic_rounds: int = 2
    signal_time_horizons: list[str] = field(default_factory=lambda: ["1h", "4h", "24h"])

    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)


def load_config(**overrides) -> MantisConfig:
    """Load config with optional overrides for LLM providers etc."""
    cfg = MantisConfig()
    if "main_provider" in overrides:
        cfg.main_llm.provider = overrides["main_provider"]
    if "main_model" in overrides:
        cfg.main_llm.model = overrides["main_model"]
    if "critic_provider" in overrides:
        cfg.critic_llm.provider = overrides["critic_provider"]
    if "critic_model" in overrides:
        cfg.critic_llm.model = overrides["critic_model"]
    if "use_testnet" in overrides:
        cfg.chain.use_testnet = overrides["use_testnet"]
    return cfg
