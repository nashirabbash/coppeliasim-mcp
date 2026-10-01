# ADR 0002: CLI Runner with Injected Context and Floating Observer Camera

## Status
Accepted

## Context
Following ADR 0001, we evaluated how the agent invokes Python code and gathers multimodal feedback. Manually importing boilerplate and finding appropriate camera angles per command increases token overhead and failure rates. Additionally, handling scene state across multiple user instructions requires an explicit persistence strategy.

## Decision
1. **CLI Runner (`runner.py`)**: A dedicated executable wrapping the virtualenv. It auto-connects to ZeroMQ (`client`, `sim`), injects standard global objects into user code, intercepts runtime errors, and formats output cleanly.
2. **Floating Observer Camera**: The runner maintains a dedicated Vision Sensor named `Agent_Observer_Cam` positioned above/diagonally looking toward the scene origin or active robot, exporting frames to `/tmp/coppelia_snapshot.png`.
3. **Cumulative State**: Scenes persist across commands by default. Resetting or clearing the scene is strictly opt-in via code or `--reset` flag.

## Consequences
- Agent scripts stay minimal (direct logic, zero connection boilerplate).
- Deterministic multimodal inspection without hijacking user GUI camera manipulations.
- Iterative multi-turn scene building is fully supported.
