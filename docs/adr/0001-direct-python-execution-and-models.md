# ADR 0001: Direct Python Script Execution with Pre-built Models and Multimodal Feedback

## Status
Accepted

## Context
The agent needs to interact with CoppeliaSim dynamically based on natural language requests (e.g. building a house with 5m walls and deploying a mobile robot inside). We evaluated whether to wrap the simulator in rigid schema-bound tools (like `build_wall`, `create_roof`) or expose direct Python script execution using the native `sim.*` ZeroMQ API. We also evaluated whether the agent should assemble robots from primitives or leverage CoppeliaSim's model library.

## Decision
1. **Script Execution Interface**: The agent writes Python scripts executing directly against the CoppeliaSim ZeroMQ Remote API (`sim.*`).
2. **Model Strategy**: Robot requests resolve to CoppeliaSim's pre-built `.ttm` model catalog (e.g., Pioneer P3DX, Asti humanoid, hexapods, KUKA YouBot) for physics stability.
3. **Multimodal Feedback**: Execution responses pair console output / numerical state with automatic or on-demand camera snapshots saved to disk for visual verification.
4. **Environment Isolation**: A dedicated `.venv` in `/home/myarchlinux/Documents/CoppeliaTools/.venv` manages `pyzmq`, `cbor2`, and client bindings without touching host system packages.

## Consequences
- Full expressiveness of CoppeliaSim API is preserved.
- No need to hand-roll unstable physics joints for complex robots.
- Agent gets both programmatic return values and visual confirmation.
