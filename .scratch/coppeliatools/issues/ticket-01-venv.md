---
id: TICKET-01
title: "Setup isolated venv and dependency management"
status: open
blockers: []
labels:
  - ready-for-agent
---

# TICKET-01: Setup isolated venv and dependency management

## Objective
Create script / workflow to initialize `/home/myarchlinux/Documents/CoppeliaTools/.venv` with `pyzmq`, `cbor2`, and local CoppeliaSim ZeroMQ client library.

## Completion Criteria
- Virtualenv exists and `python -c "import zmq, cbor2; from coppeliasim_zmqremoteapi_client import RemoteAPIClient; print('OK')"` exits 0.
- `setup_env.sh` or equivalent exists for automated reproducible setup.
