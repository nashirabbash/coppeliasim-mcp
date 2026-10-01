---
id: TICKET-02
title: "Implement CLI Runner and Model Helper"
status: open
blockers:
  - TICKET-01
labels:
  - ready-for-agent
---

# TICKET-02: Implement CLI Runner and Model Helper

## Objective
Implement `runner.py` capable of:
- Auto-injecting `client` and `sim` handles from ZeroMQ API.
- Injected `load_robot(name, pos)` helper mapping aliases to `.ttm` models in CoppeliaSim.
- Managing persistent / cumulative scene state.
- Executing Python code strings or script files.
- Catching exceptions gracefully and formatting JSON output (`success`, `stdout`, `stderr`, `snapshot_path`).

## Completion Criteria
- `python runner.py --code "print(sim.getSimulationTime())"` executes and returns valid JSON.
- Proper error reporting when simulator is disconnected or code fails.
