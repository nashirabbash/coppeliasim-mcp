---
id: TICKET-03
title: "Implement Observer Camera and Snapshot Pipeline"
status: open
blockers:
  - TICKET-02
labels:
  - ready-for-agent
---

# TICKET-03: Implement Observer Camera and Snapshot Pipeline

## Objective
Implement auto-provisioning and frame rendering for `Agent_Observer_Cam` in `runner.py`:
- Programmatically ensure `Agent_Observer_Cam` Vision Sensor exists in the scene at an elevated angle.
- Auto-capture image frame and write to `/tmp/coppelia_snapshot.png` upon completion of runner execution.
- Support `--no-snapshot` CLI option.

## Completion Criteria
- Running any scene manipulation script generates `/tmp/coppelia_snapshot.png`.
- Snapshot path is populated in the runner JSON output.
