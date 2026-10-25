# P1: typed sensors, mechanism inspection, and experiments

## Added MCP tools
- `coppelia_sensors`: read proximity, vision RGB, metric depth, force/torque, and sampled metric point clouds.
- `coppelia_mechanism`: summarize robot subtree joints, limits, current/target positions, sensors, and base/end-effector candidates.
- `coppelia_experiments`: run up to 20 episodes and 10000 combined simulation steps; report completed/diagnostic-stopped results.

## Added modules
- `sensor_tools.py`: sensor type validation, image/depth retrieval, force/proximity reads, and bounded point-cloud projection.
- `mechanism_tools.py`: mechanism subtree summary.
- `experiment_tools.py`: bounded episode validation, joint initialization, result comparison.
- `p1_mcp_tools.py`: MCP handlers and error logging.
- `test_p1_tools.py`: sensor, mechanism, experiment budget, and episode aggregation checks.

## Verified
- Unit tests: `test_p1_tools` and `test_trajectory_tools` pass; MCP module imports and tool registration load.
- Live CoppeliaSim version `41000`: inspected Franka's 7 joints and force sensor; RGB and metric depth returned at `1024x768`; point-cloud sampling returned 30 points with `max_points=32`.
- Live batch: 2 and 3 step episodes completed; joint-seeded episode completed 2 steps.
- Force sensor correctly reported `available=false` before valid filtered samples existed.
- Temporary Franka objects were removed; scene returned to its original Floor hierarchy and simulation stopped.
- Both scene images were inspected. The mounted `coppelia_step` wrapper also reported snapshot errors (`name 'base64' is not defined`) despite writing readable images.

## Limits
- End-effector output lists leaf shape/dummy candidates; no semantic tool-frame inference.
- Experiment episodes reset only named joints; remaining simulation state persists.
- Diagnostic stop marks episode unsuccessful; full step completion does not prove task success.
- Simulation evidence does not establish hardware safety.
