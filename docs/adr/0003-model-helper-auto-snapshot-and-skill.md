# ADR 0003: Model Helper, Auto-Snapshot Default, and Agent Skill Package

## Status
Accepted

## Context
Decisions from ADR 0001 and ADR 0002 left questions about convenience abstractions for robot loading, camera snapshot timing, and harness-level discoverability for `omp`.

## Decision
1. **Injected Model Helper (`load_robot`)**: `runner.py` provides a built-in helper `load_robot(name, position=[0,0,0])` mapping aliases (e.g. `'pioneer'`, `'youbot'`, `'hexapod'`, `'humanoid'`) to `.ttm` paths in `/home/myarchlinux/.local/opt/coppeliaSim/models/`.
2. **Auto-Snapshot Default**: Every runner execution automatically captures an observation frame from `Agent_Observer_Cam` into `/tmp/coppelia_snapshot.png` and outputs the image path, with a `--no-snapshot` CLI escape hatch.
3. **Agent Skill Integration**: Define an omp skill at `/home/myarchlinux/.agents/skills/coppeliasim/SKILL.md` exposing runner CLI syntax, model helpers, and feedback interpretation to the agent harness.

## Consequences
- Agent scripts avoid hardcoded filesystem paths.
- Every tool invocation returns visual multimodal evidence automatically.
- Any future agent session in `omp` immediately knows how to drive CoppeliaSim.
