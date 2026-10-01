# Specification: Agent-Driven CoppeliaSim Control Tooling

## Problem Statement

When an AI agent (such as an assistant in omp) needs to model, modify, or simulate robotic scenarios inside CoppeliaSim based on natural language requests (for example, constructing a 5-meter-walled house with a roof and operating a mobile robot inside), there is no unified bridge, execution runner, or agent skill available. Generating commands requires manually managing ZeroMQ connection boilerplate, guessing absolute model file paths, risking physics instability from hand-crafted primitives, and operating blindly without visual confirmation of the simulation scene.

## Solution

A complete integration harness for CoppeliaSim that exposes a Python CLI execution runner backed by an isolated virtual environment. The runner connects directly to the CoppeliaSim ZeroMQ Remote API, provides injected context (`sim`, `client`), automatically resolves pre-built robot models via alias helpers, preserves cumulative scene state across iterative turns, and captures overhead observation snapshots to disk for visual verification. This tooling is registered as an agent skill so that coding and assistant agents can autonomously formulate scene scripts, execute them, inspect visual results, and correct issues.

## User Stories

1. As an agent, I want to execute Python commands against a running CoppeliaSim instance without writing ZeroMQ socket connection boilerplate, so that I can directly manipulate the scene with minimal token overhead.
2. As an agent, I want a persistent cumulative scene across script invocations, so that I can iteratively build an environment (e.g. walls, roof, furniture) before placing a robot.
3. As an agent, I want an injected model helper function to load pre-built robot models using simple aliases (such as "pioneer", "youbot", "hexapod"), so that I do not need to memorize or hardcode absolute filesystem paths.
4. As an agent, I want to receive an automatic visual snapshot of the scene after executing commands, so that I can verify whether objects were correctly positioned, oriented, and physically stable.
5. As an agent, I want numerical state and error outputs returned alongside visual snapshots, so that I can immediately detect and fix physics simulation or API syntax errors.
6. As a user, I want the agent to use validated pre-built robot models rather than unstable raw joint primitives, so that the robot can move reliably without collapsing due to physical misconfiguration.
7. As a developer, I want all client dependencies (such as pyzmq and cbor2) isolated in a dedicated project virtual environment, so that the host Arch Linux system packages remain clean and unaffected.
8. As an agent harness, I want a discoverable skill specification in the skills directory, so that any agent session immediately knows how to invoke the simulator runner and interpret its feedback.
9. As an agent, I want to explicitly reset or clear the simulation scene via an argument or command when starting a completely new task, so that previous experiments do not interfere.
10. As a user, I want to prompt the agent with high-level spatial requests (e.g., "build a house with 5m walls and a roof, then put a robot inside"), so that the agent handles all spatial calculation and API calls end-to-end.

## Implementation Decisions

- **Single CLI Runner Interface**: A Python execution entrypoint that accepts either inline code or a script file path, executing it within the virtual environment context and printing standard JSON output containing stdout, stderr, and snapshot path.
- **Injected Execution Context**: The runner injects standard global references (`client`, `sim`) into the script namespace before execution, eliminating repetitive imports.
- **Model Alias Resolver**: A helper function (`load_robot`) mapping common names to the CoppeliaSim pre-installed mobile and non-mobile robot models.
- **Dedicated Observer Camera**: A programmatically ensured Vision Sensor named `Agent_Observer_Cam` positioned at an elevated perspective facing the scene center, ensuring consistent visual captures regardless of user GUI interaction.
- **Dedicated Virtualenv**: A `.venv` directory hosting the Python dependencies, triggered transparently by the runner executable or helper wrapper.
- **Agent Skill Packaging**: An agent skill definition under the local skills registry documenting execution commands, available models, coordinate conventions, and self-correction workflows.

## Testing Decisions

- **Testing Seam**: The highest-level public seam is the CLI runner command itself. Tests will execute scripts via the CLI runner against a running or mocked simulator endpoint and assert on:
  - Exit code and structured output (stdout, stderr).
  - Snapshot generation and file validity on disk.
  - Return values of scene queries (e.g. object position, existence of created shapes).
- **Good Test Criteria**: Tests must verify observable outcomes (object exists in scene, snapshot image created, script errors reported) rather than internal runner abstractions.
- **Prior Art**: Standard subprocess CLI integration tests and headless remote API sample scripts provided in the CoppeliaSim programming directory.

## Out of Scope

- Developing custom mesh assets or external 3D CAD modeling.
- Controlling external real-world physical robots (focus is strictly on the CoppeliaSim simulator).
- Modifying CoppeliaSim core source code or binary plugins.
- Packaging as a GUI desktop application (interface is strictly agent CLI / skill).

## Further Notes

- CoppeliaSim ZeroMQ remote API uses port 23000 by default.
- CoppeliaSim must be running with the remote API active for execution to succeed. The runner should provide an actionable error message if the simulator is unreachable.
