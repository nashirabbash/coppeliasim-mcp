# GUI-first CoppeliaSim launch

## Changed

- Native CoppeliaSim GUI is the default launch mode.
- ROS 2 Docker headless launch now requires `COPPELIASIM_ROS2_MODE=docker`; `auto` remains available explicitly.
- `headless=true` and `--headless` remain explicit headless options.

## Verification

- `.venv/bin/python -m unittest tests.test_sim_connection`: 13 tests pass.
- `bash -n scripts/coppelia_launch.sh coppelia_launch.sh`: syntax checks pass.
