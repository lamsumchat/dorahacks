"""Mantis Research Analyst — main ReAct agent that produces signals."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from mantis.agent.llm import build_main_llm
from mantis.agent.prompts import (
    REFLEXION_REVISION_PROMPT_TEMPLATE,
    RESEARCH_ANALYST_SYSTEM_PROMPT,
)
from mantis.agent.schema import Signal, SignalDraft
from mantis.agent.tools import make_tools
from mantis.config import MantisConfig
from mantis.tools.chain_client import MantleClient


def _extract_json_object(text: str) -> dict | None:
    """Extract the last JSON object from text. Handles fences and trailing prose."""
    fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    matches = fence_re.findall(text)
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError:
            pass

    # Find balanced top-level JSON objects greedily, scanning right to left
    depth = 0
    end = -1
    for i in range(len(text) - 1, -1, -1):
        c = text[i]
        if c == "}":
            if depth == 0:
                end = i
            depth += 1
        elif c == "{":
            depth -= 1
            if depth == 0 and end != -1:
                candidate = text[i : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    end = -1
                    continue
    return None


class ResearchAgent:
    """Main analyst agent: builds tools, runs ReAct loop, parses structured output."""

    def __init__(self, config: MantisConfig):
        self.config = config
        self.client = MantleClient(config)
        self.llm = build_main_llm(config, temperature=0.3)
        self.tools = make_tools(self.client)
        self.graph = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=RESEARCH_ANALYST_SYSTEM_PROMPT,
        )

    def analyze(
        self,
        focus: str | None = None,
        verbose: bool = True,
        recursion_limit: int = 30,
        use_critic: bool = True,
        max_critic_rounds: int | None = None,
    ) -> tuple[Signal | None, dict]:
        """Run a full analysis cycle, optionally with Critic reflexion.

        Args:
            focus: Optional user hint to focus the analysis.
            verbose: Print tool calls and assistant turns.
            recursion_limit: Max ReAct iterations per round.
            use_critic: Whether to run the Critic reflexion loop after the draft.
            max_critic_rounds: Override config default for max critic rounds.

        Returns:
            (Signal or None, raw_state).
        """
        user_message = focus or (
            "Run a fresh on-chain research cycle on Mantle. "
            "Look for any unusual activity in the last 1-2 hours that warrants a signal. "
            "Investigate whatever stands out, and produce a final JSON signal."
        )

        last_state: dict = self._run_react(user_message, recursion_limit)

        if verbose:
            self._print_trace(last_state)

        draft_signal = self._parse_final_signal(last_state)

        if not use_critic or draft_signal is None:
            return draft_signal, last_state

        # Reflexion loop
        rounds = max_critic_rounds if max_critic_rounds is not None else self.config.max_critic_rounds
        final_signal = self._run_critic_loop(
            draft_signal, last_state, rounds, recursion_limit, verbose
        )
        return final_signal, last_state

    def _run_react(self, user_message: str, recursion_limit: int) -> dict:
        messages = [HumanMessage(content=user_message)]
        last_state: dict = {"messages": list(messages)}
        try:
            for chunk in self.graph.stream(
                {"messages": messages},
                config={"recursion_limit": recursion_limit},
                stream_mode="values",
            ):
                last_state = chunk
        except Exception as e:
            print(f"\n[!] Agent execution stopped: {type(e).__name__}: {e}\n")
        return last_state

    def _run_critic_loop(
        self,
        draft: Signal,
        prior_state: dict,
        max_rounds: int,
        recursion_limit: int,
        verbose: bool,
    ) -> Signal:
        """Run up to max_rounds of Critic challenges + analyst revision."""
        from mantis.agent.critic import CriticAgent

        critic = CriticAgent(self.config, self.client)
        current_signal = draft
        rounds_used = 0
        last_verdict = None

        for round_idx in range(max_rounds):
            rounds_used = round_idx + 1
            if verbose:
                print(f"\n>>> Critic round {rounds_used}/{max_rounds}")

            verdict, _critic_state = critic.review(
                self._signal_to_draft(current_signal),
                recursion_limit=25,
                verbose=verbose,
            )
            last_verdict = verdict

            if verdict is None:
                if verbose:
                    print("[!] Critic did not produce a parseable verdict; accepting draft as-is.")
                current_signal.critic_result = "NOT_REVIEWED"
                current_signal.critic_notes = "Critic output unparseable"
                break

            if verdict.verdict == "PASS":
                current_signal.critic_result = (
                    "CHALLENGE_RESOLVED" if rounds_used > 1 else "PASS"
                )
                current_signal.critic_notes = (
                    "; ".join(verdict.concerns) if verdict.concerns else None
                )
                break

            # CHALLENGE — try to revise (unless we're at the last round)
            if rounds_used >= max_rounds:
                # Final round still challenged → degrade and exit
                current_signal = self._degrade_signal(current_signal, verdict)
                current_signal.critic_result = "CHALLENGE_UNRESOLVED"
                current_signal.critic_notes = "; ".join(
                    verdict.concerns + verdict.counter_evidence
                )[:500]
                break

            revision_prompt = REFLEXION_REVISION_PROMPT_TEMPLATE.format(
                verdict=verdict.verdict,
                concerns="\n".join(f"  - {c}" for c in verdict.concerns) or "  (none)",
                counter_evidence="\n".join(
                    f"  - {e}" for e in verdict.counter_evidence
                ) or "  (none)",
                suggested_action=verdict.suggested_action,
            )

            # Continue the same conversation: revision is a follow-up message
            revised_state = self._continue_react(prior_state, revision_prompt, recursion_limit)
            prior_state = revised_state
            if verbose:
                self._print_trace(revised_state)

            revised = self._parse_final_signal(revised_state)
            if revised is None:
                if verbose:
                    print("[!] Revision did not parse; keeping previous draft.")
                current_signal.critic_result = "CHALLENGE_UNRESOLVED"
                current_signal.critic_notes = "Revision parse failure; " + "; ".join(
                    verdict.concerns
                )[:300]
                current_signal = self._degrade_signal(current_signal, verdict)
                break

            current_signal = revised

        return current_signal

    def _continue_react(self, prior_state: dict, follow_up: str, recursion_limit: int) -> dict:
        new_messages = list(prior_state.get("messages", []))
        new_messages.append(HumanMessage(content=follow_up))
        last_state: dict = {"messages": new_messages}
        try:
            for chunk in self.graph.stream(
                {"messages": new_messages},
                config={"recursion_limit": recursion_limit},
                stream_mode="values",
            ):
                last_state = chunk
        except Exception as e:
            print(f"\n[!] Revision execution stopped: {type(e).__name__}: {e}\n")
        return last_state

    @staticmethod
    def _signal_to_draft(signal: Signal) -> SignalDraft:
        return SignalDraft(
            asset=signal.asset,
            direction=signal.direction,
            confidence=signal.confidence,
            time_horizon=signal.time_horizon,
            key_evidence=signal.key_evidence,
            reasoning_summary=signal.reasoning_summary,
        )

    @staticmethod
    def _degrade_signal(signal: Signal, verdict) -> Signal:
        """Apply confidence degradation based on the Critic's suggested action."""
        action = verdict.suggested_action if verdict else "reduce_confidence"

        if action == "mark_neutral":
            signal.direction = "neutral"
            signal.confidence = min(signal.confidence, 0.3)
        elif action == "flip_direction":
            signal.direction = (
                "bearish" if signal.direction == "bullish"
                else "bullish" if signal.direction == "bearish"
                else "neutral"
            )
            signal.confidence = signal.confidence * 0.5
        else:
            signal.confidence = round(signal.confidence * 0.6, 3)

        return signal

    def _parse_final_signal(self, state: dict) -> Signal | None:
        for msg in reversed(state.get("messages", [])):
            if msg.__class__.__name__ != "AIMessage":
                continue
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            obj = _extract_json_object(content)
            if obj is None:
                continue
            try:
                draft = SignalDraft.model_validate(obj)
                return Signal(
                    asset=draft.asset,
                    direction=draft.direction,
                    confidence=draft.confidence,
                    time_horizon=draft.time_horizon,
                    key_evidence=draft.key_evidence,
                    reasoning_summary=draft.reasoning_summary,
                )
            except Exception:
                continue
        return None

    @staticmethod
    def _print_trace(state: dict) -> None:
        print("\n" + "=" * 70)
        print("  Agent Reasoning Trace")
        print("=" * 70)
        for i, msg in enumerate(state.get("messages", [])):
            cls = msg.__class__.__name__
            if cls == "HumanMessage":
                print(f"\n[USER]\n{msg.content}")
            elif cls == "AIMessage":
                tool_calls = getattr(msg, "tool_calls", None) or []
                if tool_calls:
                    for tc in tool_calls:
                        args = json.dumps(tc.get("args", {}), default=str)
                        print(f"\n[AGENT → tool] {tc['name']}({args[:200]})")
                if isinstance(msg.content, str) and msg.content.strip():
                    text = msg.content.strip()
                    if len(text) > 800:
                        text = text[:800] + "... [truncated]"
                    print(f"\n[AGENT]\n{text}")
            elif cls == "ToolMessage":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if len(content) > 600:
                    content = content[:600] + "... [truncated]"
                print(f"\n[TOOL: {getattr(msg, 'name', '?')}]\n{content}")
        print("\n" + "=" * 70 + "\n")
