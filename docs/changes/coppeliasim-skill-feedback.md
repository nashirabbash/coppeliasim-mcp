# CoppeliaSim skill and example corrections

## Changed

- Fixed CLI launch output parsing: launcher stdout/stderr are captured, and launch failures retain captured diagnostics.
- Replaced raw TCP health probing with a Remote API handshake and simulator program-version query; health now reports handshake errors.
- Runner reset, scene loading, dataset stop-on-finish, and trajectory failure cleanup use bounded stop completion; `coppelia_step` injects no-argument `stop_simulation()`. Execution errors include Python traceback and remote Lua diagnostics in stderr.
- Updated the skill and README with persistent in-scene controller guidance, optional persistent sensor display, stop completion, launch/connection diagnostics, CLI evidence limits, camera framing, supported spheroid constant, and current simulation-time API.
- Changed obstacle-avoidance example to advance its bounded control loop using simulation time and stepping; changed house example to use injected `stop_simulation()` before scene edits.

## Validation

- Example syntax check passed: `.venv/bin/python -m py_compile examples/robot_obstacle_avoidance.py examples/build_house_and_robot.py`.
- Focused runtime checks passed: 43 tests across packaging resources, simulator connection, scene I/O, runner CLI, dataset tools, and P1 tools.
- Trajectory checks passed: `.venv/bin/python -m unittest tests.test_trajectory_tools` (15 tests).
- Independent review found an injected-helper signature mismatch and missing trajectory stop waits; both were corrected.
- Initial live smoke timed out after the launched simulator exited. A persistent launcher service resolved the lifecycle issue.
- Fresh `execute_step` subprocess smoke passed for successful execution, an intentional Python error with traceback, explicit stop completion, and `reset=True` reaching the stopped state without replacing the scene.
- Both live captures were inspected: the default checkered floor is visible in top-down and isometric views. No robot behavior or keyboard input was exercised.
- The mounted MCP process was not reloaded; reconnect the MCP client to load updated server code and tool descriptions.
