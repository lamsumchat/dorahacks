"""Critic Sub-Agent — independent Devil's Advocate that challenges draft signals."""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from mantis.agent.llm import build_critic_llm
from mantis.agent.prompts import CRITIC_SYSTEM_PROMPT
from mantis.agent.research_agent import _extract_json_object
from mantis.agent.schema import SignalDraft
from mantis.agent.tools import make_tools
from mantis.config import MantisConfig
from mantis.tools.chain_client import MantleClient


class CriticVerdict(BaseModel):
    verdict: Literal["PASS", "CHALLENGE"]
    concerns: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    suggested_action: Literal[
        "accept_as_is", "reduce_confidence", "flip_direction", "mark_neutral"
    ] = "accept_as_is"


class CriticAgent:
    """Independent-context critic that challenges a draft signal using its own tools.

    Key design choices (from constitution):
    - Independent context: receives only the draft + evidence, NOT the analyst's reasoning.
    - Tool subset: data fetchers only (no run_python, no spawn_critic — no recursion).
    - Smaller LLM: cheaper model is fine; the task is focused.
    """

    def __init__(self, config: MantisConfig, client: MantleClient):
        self.config = config
        self.llm = build_critic_llm(config, temperature=0.2)
        # Filter out run_python — critic should not generate code
        all_tools = make_tools(client)
        self.tools = [t for t in all_tools if t.name != "run_python"]
        self.graph = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=CRITIC_SYSTEM_PROMPT,
        )

    def review(
        self,
        draft: SignalDraft,
        recursion_limit: int = 25,
        verbose: bool = False,
    ) -> tuple[CriticVerdict | None, dict]:
        """Run the critic on a draft signal. Returns the verdict + raw state."""
        prompt = self._build_review_prompt(draft)
        messages = [HumanMessage(content=prompt)]

        last_state: dict = {"messages": list(messages)}
        try:
            for chunk in self.graph.stream(
                {"messages": messages},
                config={"recursion_limit": recursion_limit},
                stream_mode="values",
            ):
                last_state = chunk
        except Exception as e:
            print(f"\n[!] Critic execution stopped: {type(e).__name__}: {e}\n")

        if verbose:
            self._print_trace(last_state)

        verdict = self._parse_verdict(last_state)
        return verdict, last_state

    @staticmethod
    def _build_review_prompt(draft: SignalDraft) -> str:
        evidence_block = "\n".join(f"  - {b}" for b in draft.key_evidence) or "  (none)"
        return f"""\
A Mantis Research Analyst has produced this draft signal. Review it skeptically.

Draft signal:
  asset:        {draft.asset}
  direction:    {draft.direction}
  confidence:   {draft.confidence}
  time_horizon: {draft.time_horizon}

Key evidence cited by the analyst:
{evidence_block}

Reasoning summary:
  {draft.reasoning_summary}

Your task: actively look for counter-evidence using your data tools. Then output your
verdict in the required JSON format.
"""

    @staticmethod
    def _parse_verdict(state: dict) -> CriticVerdict | None:
        # Try to find a parseable JSON verdict in any AIMessage (most recent first)
        for msg in reversed(state.get("messages", [])):
            if msg.__class__.__name__ != "AIMessage":
                continue
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            obj = _extract_json_object(content)
            if obj is None:
                continue
            try:
                return CriticVerdict.model_validate(obj)
            except Exception:
                continue

        # Fallback: critic ran tools but didn't produce JSON (e.g. recursion limit hit).
        # If it called >=2 tools, mark as CHALLENGE with their narrative as concerns.
        # This salvages real critique work rather than discarding it.
        tool_call_count = 0
        last_narrative = ""
        for msg in state.get("messages", []):
            if msg.__class__.__name__ == "AIMessage":
                tool_calls = getattr(msg, "tool_calls", None) or []
                tool_call_count += len(tool_calls)
                if isinstance(msg.content, str) and msg.content.strip():
                    last_narrative = msg.content.strip()

        if tool_call_count >= 2 and last_narrative:
            snippet = last_narrative[:400]
            return CriticVerdict(
                verdict="CHALLENGE",
                concerns=[f"Critic exhausted budget without final JSON. Last note: {snippet}"],
                counter_evidence=[],
                suggested_action="reduce_confidence",
            )

        return None

    @staticmethod
    def _print_trace(state: dict) -> None:
        print("\n" + "-" * 70)
        print("  Critic Trace")
        print("-" * 70)
        for msg in state.get("messages", []):
            cls = msg.__class__.__name__
            if cls == "AIMessage":
                tool_calls = getattr(msg, "tool_calls", None) or []
                for tc in tool_calls:
                    args = json.dumps(tc.get("args", {}), default=str)
                    print(f"\n  [CRITIC → tool] {tc['name']}({args[:150]})")
                if isinstance(msg.content, str) and msg.content.strip():
                    text = msg.content.strip()
                    if len(text) > 600:
                        text = text[:600] + "... [truncated]"
                    print(f"\n  [CRITIC]\n  {text}")
            elif cls == "ToolMessage":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if len(content) > 400:
                    content = content[:400] + "... [truncated]"
                print(f"\n  [TOOL: {getattr(msg, 'name', '?')}]\n  {content}")
        print("-" * 70 + "\n")
