"""CLI entrypoint: run the Mantis Research Agent end-to-end."""

from __future__ import annotations

import argparse
import json
import sys

from mantis.agent.research_agent import ResearchAgent
from mantis.config import load_config


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
    print()


if __name__ == "__main__":
    main()
