"""Mantis Research Analyst — main ReAct agent that produces signals."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from mantis.agent.llm import build_main_llm
from mantis.agent.prompts import RESEARCH_ANALYST_SYSTEM_PROMPT
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
    ) -> tuple[Signal | None, dict]:
        """Run a full analysis cycle.

        Args:
            focus: Optional user hint to focus the analysis. None = let agent explore.
            verbose: Print tool calls and assistant turns as they happen.
            recursion_limit: Max ReAct iterations.

        Returns:
            (Signal or None, raw_state). Signal is None if final output failed to parse.
        """
        user_message = focus or (
            "Run a fresh on-chain research cycle on Mantle. "
            "Look for any unusual activity in the last 1-2 hours that warrants a signal. "
            "Investigate whatever stands out, and produce a final JSON signal."
        )

        messages = [HumanMessage(content=user_message)]
        state = {"messages": messages}

        # Stream so we can capture the latest state even on recursion-limit errors.
        last_state: dict = {"messages": list(messages)}
        try:
            for chunk in self.graph.stream(
                state,
                config={"recursion_limit": recursion_limit},
                stream_mode="values",
            ):
                last_state = chunk
        except Exception as e:
            print(f"\n[!] Agent execution stopped: {type(e).__name__}: {e}\n")

        if verbose:
            self._print_trace(last_state)

        signal = self._parse_final_signal(last_state)
        return signal, last_state

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
