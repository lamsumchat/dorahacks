"""CLI entrypoint: run the Mantis Research Agent end-to-end."""

from __future__ import annotations

import argparse
import json
import sys

from mantis.agent.research_agent import ResearchAgent
from mantis.config import load_config


def _record_on_chain(signal, cfg):
    """Attempt to record the signal on-chain. Fails gracefully."""
    try:
        from mantis.contracts.registry import SignalRegistry

        registry = SignalRegistry(cfg)
        result = registry.emit_signal(signal)
        print("\n" + "=" * 70)
        print("  On-Chain Recording")
        print("=" * 70)
        print(f"  Signal ID (on-chain): {result['signal_id']}")
        print(f"  Tx Hash:   0x{result['tx_hash']}")
        print(f"  Block:     {result['block']}")
        print(f"  Explorer:  {result['explorer_url']}")
        print("=" * 70)
        return result
    except FileNotFoundError:
        print("\n  [skip] Contract not compiled yet. Run: python -m mantis.contracts.compile")
    except ValueError as e:
        print(f"\n  [skip] On-chain recording skipped: {e}")
    except Exception as e:
        print(f"\n  [warn] On-chain recording failed: {type(e).__name__}: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Run the Mantis Research Agent.")
    parser.add_argument(
        "--focus",
        type=str,
        default=None,
        help="Optional analysis hint, e.g. 'focus on mETH today'.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't print the reasoning trace, only the final signal JSON.",
    )
    parser.add_argument(
        "--recursion-limit",
        type=int,
        default=30,
        help="Maximum ReAct iterations (default 30).",
    )
    parser.add_argument(
        "--no-critic",
        action="store_true",
        help="Skip the Critic reflexion loop after the draft signal.",
    )
    parser.add_argument(
        "--critic-rounds",
        type=int,
        default=None,
        help="Max critic rounds (default from config: 2).",
    )
    parser.add_argument(
        "--no-chain",
        action="store_true",
        help="Skip on-chain signal recording even if wallet is configured.",
    )
    args = parser.parse_args()

    cfg = load_config()
    print(
        f"Loading agent (main LLM: {cfg.main_llm.provider}/{cfg.main_llm.model}, "
        f"critic LLM: {cfg.critic_llm.provider}/{cfg.critic_llm.model})..."
    )

    agent = ResearchAgent(cfg)
    signal, _state = agent.analyze(
        focus=args.focus,
        verbose=not args.quiet,
        recursion_limit=args.recursion_limit,
        use_critic=not args.no_critic,
        max_critic_rounds=args.critic_rounds,
    )

    print("\n" + "=" * 70)
    print("  Final Signal")
    print("=" * 70)
    if signal is None:
        print("\n  [!] Agent did not produce a parseable signal.")
        sys.exit(1)

    output = signal.model_dump()
    output["content_hash"] = signal.content_hash()
    print(json.dumps(output, indent=2))

    if not args.no_chain:
        chain_result = _record_on_chain(signal, cfg)
        if chain_result:
            output["on_chain"] = chain_result

    print()


if __name__ == "__main__":
    main()
