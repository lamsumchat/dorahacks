"""Structured output schema for Mantis signals."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """A trading signal produced by the Mantis agent."""

    signal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    asset: str = Field(description="Token symbol (e.g. WMNT, mETH, USDT)")
    direction: Literal["bullish", "bearish", "neutral"] = Field(
        description="Predicted price direction"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence 0-1. Lower below 0.5 if Critic challenged.",
    )
    time_horizon: str = Field(
        default="24h",
        description="Time window the signal is valid for: 1h, 4h, 24h, 7d",
    )
    key_evidence: list[str] = Field(
        default_factory=list,
        description="Bullet points of the strongest evidence",
    )
    reasoning_summary: str = Field(
        description="2-4 sentence summary of the analysis logic",
    )
    critic_result: Literal["PASS", "CHALLENGE_RESOLVED", "CHALLENGE_UNRESOLVED", "NOT_REVIEWED"] = "NOT_REVIEWED"
    critic_notes: str | None = None

    def content_hash(self) -> str:
        """SHA-256 hash of the canonical JSON representation, used for on-chain anchoring."""
        canonical = json.dumps(
            self.model_dump(exclude={"signal_id"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def direction_int(self) -> int:
        return {"bullish": 1, "bearish": -1, "neutral": 0}[self.direction]


class SignalDraft(BaseModel):
    """Intermediate draft used while the agent is reasoning."""

    asset: str
    direction: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon: str = "24h"
    key_evidence: list[str]
    reasoning_summary: str
