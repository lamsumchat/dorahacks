# Mantis Constitution

## Core Principles

### I. ReAct-First Agent Design
The system uses a single ReAct main agent with tool-calling, not a multi-agent pipeline.
Sub-agents (Critic, Self-Reviewer) are spawned only for specific adversarial or reflective tasks
and run in isolated contexts. No fixed-role agent teams.

### II. Tool-Layered Architecture
Tools are organized in layers with clear boundaries:
- Layer 1 (Data Access): Raw data fetchers, no judgment
- Layer 2 (Analysis Primitives): Structured analysis on raw data, deterministic where possible
- Layer 3 (Free Exploration): `run_python` for agent-authored code, sandboxed
- Layer 4 (Sub-Agents): Critic and Self-Reviewer with independent contexts

Each layer only depends on layers below it. Tools are independently testable.

### III. Anomaly-Driven Discovery
Smart money identification is based on behavioral anomaly detection, not pre-curated address lists.
Known entity labels are enrichment, not the primary signal source.
The system discovers "who is doing unusual things" rather than "what are known whales doing."

### IV. Verifiable Signals
Every signal produced must be verifiable:
- Structured output format with content hash
- On-chain recording (Mantle) of signal hash + metadata
- Full reasoning chain stored off-chain, hash-linked to on-chain record
- Self-review mechanism for retrospective accuracy assessment

### V. Minimal On-Chain Footprint
Smart contracts store only what's necessary for verification (hashes, timestamps, metadata).
Full content lives off-chain. Gas efficiency over on-chain completeness.

### VI. Configurable LLM Backend
All LLM calls go through a unified config. Provider and model are swappable without code changes.
Default to strong models for main agent, lightweight models for sub-agents.
Never hardcode API keys or model names in source code.

## Technology Stack

- **Language**: Python 3.11+
- **Agent Framework**: LangGraph (minimal, `create_react_agent`)
- **LLM Interface**: LangChain `init_chat_model` (multi-provider)
- **Chain Interaction**: web3.py
- **Smart Contracts**: Solidity ^0.8.20
- **Dashboard**: Streamlit
- **Testing**: pytest
- **Target Chain**: Mantle Network (Mainnet: 5000, Testnet: 5003)

## Development Workflow

- Milestone-based delivery: each milestone produces a runnable artifact
- AI-assisted development with human review at milestone boundaries
- Brainstorm decisions documented in `notes/brainstorm-log.md`
- No premature optimization; working system first, polish second

## Governance

Constitution guides all architectural decisions. Deviations require documented justification.

**Version**: 1.0.0 | **Ratified**: 2026-05-09
