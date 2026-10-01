---
id: coppeliatools-1
title: "Spec: Agent-Driven CoppeliaSim Control Tooling"
status: ready-for-agent
labels:
  - ready-for-agent
  - specification
---

# Spec: Agent-Driven CoppeliaSim Control Tooling

Specification file: `specs/0001-coppeliatools-agent-control.md`

## Summary
Implements an execution runner (`runner.py`) using an isolated Python virtualenv to connect directly to CoppeliaSim via ZeroMQ Remote API (`sim.*`). Injects standard handles, pre-built model loader helpers, persistent scene state across runs, automated observation camera snapshots (`/tmp/coppelia_snapshot.png`), and registers an agent skill for `omp` integration.
