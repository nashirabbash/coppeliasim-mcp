# Context Glossary: CoppeliaTools

Domain vocabulary for agent-driven CoppeliaSim automation via ZeroMQ Remote API.

## Core Entities

- **Simulator Host**: CoppeliaSim application instance running with the ZeroMQ remote API addon active (default port `23000`).
- **Bridge Client**: Python client environment (`coppeliasim-zmqremoteapi-client` backed by `pyzmq` and `cbor2`) executing code against the simulator host.
- **Scene Script**: User/agent-generated Python script utilizing `sim.*` APIs to manipulate shapes, models, physics, and simulation states.
- **Model Catalog**: Pre-built validated CoppeliaSim robot models (`.ttm` files, e.g. `pioneer p3dx.ttm`, `ant hexapod.ttm`, `Asti.ttm`, `KUKA YouBot.ttm`) loaded directly instead of manual primitive assembly.
- **Model Helper**: Injected convenience function (`load_robot(name, position)`) that resolves common robot names directly to their `.ttm` path in the CoppeliaSim installation.
- **Execution Runner**: Command-line interface (`runner.py`) executing scene scripts in the project virtualenv, injecting `sim` handles, catching errors, managing cumulative scene state, and triggering observation snapshots.
- **Agent Observer Camera**: Programmatically managed floating Vision Sensor (`Agent_Observer_Cam`) positioned overhead/isometrically to deliver visual feedback independently of the GUI viewport.
- **Observation Snapshot**: Visual inspection capture from the Agent Observer Camera saved to disk (`/tmp/coppelia_snapshot.png`), paired with numerical state logs (`sim.getObjectPosition`, simulation errors).
- **Cumulative Scene**: Preserved simulator state across subsequent agent invocations, reset only on explicit user/agent instruction.
- **Coppelia Skill**: Agent harness capability specification (`.agents/skills/coppeliasim/SKILL.md`) guiding agents on invoking `runner.py`, available robot models, and interpreting visual snapshots.
