---
id: TICKET-05
title: "End-to-End Verification: House with 5m walls, roof, and mobile robot"
status: open
blockers:
  - TICKET-04
labels:
  - ready-for-agent
---

# TICKET-05: End-to-End Verification: House with 5m walls, roof, and mobile robot

## Objective
Execute the exact user scenario requested:
- Construct a house with 5-meter high walls and a roof.
- Spawn a mobile robot inside.
- Run simulation and verify physics / snapshot visually.

## Completion Criteria
- Runner executes scenario script without error.
- Verified `/tmp/coppelia_snapshot.png` contains 5m house with roof and robot inside.
