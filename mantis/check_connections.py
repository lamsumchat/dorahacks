"""Smoke-test all external connections: RPC, Explorer, Subgraph, Bybit, LLM."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from mantis.config import load_config


async def check_mantle_rpc(cfg, label: str, url: str) -> tuple[str, bool, str]:
    """Verify Mantle RPC responds to eth_blockNumber."""
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            block = int(data["result"], 16)
            return label, True, f"block #{block:,} ({url})"
    except Exception as e:
        return label, False, str(e)


async def check_explorer_api(cfg) -> tuple[str, bool, str]:
    """Verify Blockscout Explorer API is reachable."""
    url = f"{cfg.chain.explorer_api}?module=block&action=getblocknobytime&timestamp={int(__import__('time').time())}&closest=before"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
            return "Explorer API", True, f"status={data.get('status', '?')} message={data.get('message', '?')}"
    except Exception as e:
        return "Explorer API", False, str(e)


async def check_subgraph(cfg) -> tuple[str, bool, str]:
    """Verify blocks subgraph responds."""
    query = '{"query": "{ _meta { block { number } } }"}'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                cfg.subgraphs.blocks,
                content=query,
                headers={"Content-Type": "application/json"},
            )
            data = resp.json()
            if "data" in data:
                block_num = data["data"]["_meta"]["block"]["number"]
                return "Blocks Subgraph", True, f"indexed up to block #{block_num:,}"
            return "Blocks Subgraph", False, f"unexpected response: {json.dumps(data)[:120]}"
    except Exception as e:
        return "Blocks Subgraph", False, str(e)


async def check_bybit(cfg) -> tuple[str, bool, str]:
    """Verify Bybit public API (no key needed for market data)."""
    url = "https://api.bybit.com/v5/market/tickers?category=spot&symbol=MNTUSDT"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
            if data.get("retCode") == 0:
                ticker = data["result"]["list"][0]
                return "Bybit API", True, f"MNT/USDT last={ticker.get('lastPrice', '?')}"
            return "Bybit API", False, f"retCode={data.get('retCode')}"
    except Exception as e:
        return "Bybit API", False, str(e)


async def check_llm(cfg) -> tuple[str, bool, str]:
    """Verify LLM API key is set and provider is reachable (lightweight ping)."""
    llm_cfg = cfg.main_llm
    label = f"LLM ({llm_cfg.provider}/{llm_cfg.model})"
    key = llm_cfg.api_key
    if not key:
        return label, False, f"API key not set ({llm_cfg.api_key_env_var})"

    base_url = llm_cfg.base_url
    if not base_url:
        return label, False, f"provider '{llm_cfg.provider}' has no base_url configured"

    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": llm_cfg.model,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 5,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)
            data = resp.json()
            if resp.status_code == 200:
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return label, True, f'response: "{content.strip()[:50]}"'
            err = data.get("error", {})
            msg = err.get("message", resp.text[:120]) if isinstance(err, dict) else str(err)[:120]
            return label, False, msg
    except Exception as e:
        return label, False, str(e)


async def main():
    cfg = load_config()
    checks = [
        check_mantle_rpc(cfg, "Mantle Mainnet RPC", cfg.chain.mainnet_rpc),
        check_mantle_rpc(cfg, "Mantle Testnet RPC", cfg.chain.testnet_rpc),
        check_explorer_api(cfg),
        check_subgraph(cfg),
        check_bybit(cfg),
        check_llm(cfg),
    ]
    results = await asyncio.gather(*checks)

    print("\n" + "=" * 60)
    print("  Mantis Connection Check")
    print("=" * 60)

    optional = {"Explorer API"}
    all_ok = True
    for name, ok, detail in results:
        is_optional = name in optional
        status = "OK" if ok else ("WARN" if is_optional else "FAIL")
        icon = "\u2705" if ok else ("\u26a0\ufe0f" if is_optional else "\u274c")
        print(f"  {icon} [{status:4s}] {name}")
        print(f"         {detail}")
        if not ok and not is_optional:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("  All critical connections verified.")
    else:
        print("  Some critical connections failed. Check .env and network.")
    print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
