<div align="center">

# CoppeliaSim MCP Server

**Build and inspect CoppeliaSim scenes from an AI assistant through one MCP tool.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

Connect an MCP client to CoppeliaSim's ZeroMQ Remote API. `coppelia_step` runs Python against the current scene and returns execution output, floor information, scene objects, and paths to top-down and isometric snapshots. The scene persists between calls, so an agent can inspect and refine it without recreating everything.

![Architecture: MCP client calls the server, runner uses CoppeliaSim, and snapshots are saved locally](docs/images/architecture.png)

[View editable architecture diagram](docs/images/architecture.html).

## What you can do

- Create shapes, load bundled robot models by alias, and control simulation with CoppeliaSim's `sim` API.
- Inspect the current floor and scene hierarchy before adding objects.
- Check both camera views after each successful execution: `/tmp/coppelia_topdown.png` and `/tmp/coppelia_snapshot.png`.
- Use the same runner directly from the command line or through an MCP client.

## Get started

### Requirements

- Python 3.10 or newer and [CoppeliaSim](https://www.coppeliarobotics.com/) with its ZeroMQ Remote API addon available on port `23000`.
- A local CoppeliaSim installation with the bundled Python client and robot models. Set `COPPELIASIM_ROOT` to its installation directory if it is not at `/home/myarchlinux/.local/opt/coppeliaSim`.
- An MCP-compatible client for agent use; the command-line runner works without one.
- Docker Engine is only needed for the optional ROS 2 Humble integration.

### Install

```bash
git clone https://github.com/nashirabbash/coppeliasim-mcp.git
cd coppeliasim-mcp
bash setup_env.sh
.venv/bin/python -m pip install -e .
```

`setup_env.sh` creates `.venv` and installs runner dependencies; `pip install -e .` also installs the MCP server dependency. `bash coppelia_launch.sh` launches the simulator with GUI by default; pass `--headless` only when needed.

For installations elsewhere, set `COPPELIASIM_ROOT` before running the CLI or starting the MCP client (or set it in the client's server environment):

```bash
export COPPELIASIM_ROOT=/path/to/coppeliaSim
```

Try the local runner without changing the scene:

```bash
./coppelia_run --code 'print(get_floor_info())'
```

It prints JSON with `success`, captured output, floor and scene objects, and snapshot paths when image capture succeeds. Open **both** snapshot files to check actual placement; `success: true` only confirms Python code ran, not that geometry or physics is correct. If no simulator is connected, the command reports a connection error instead.

### Connect an MCP client

Find the absolute path to this checkout, then replace `/absolute/path/to/coppeliasim-mcp` below. For `omp`, add this server to `~/.omp/agent/mcp.json` (merge it with existing `mcpServers` entries):

```json
{
  "mcpServers": {
    "coppeliasim": {
      "type": "stdio",
      "command": "/absolute/path/to/coppeliasim-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/coppeliasim-mcp/coppelia_mcp.py"],
      "enabled": true
    }
  }
}
```

For Claude Desktop, use its `claude_desktop_config.json` (`~/.config/Claude/` on Linux or `~/Library/Application Support/Claude/` on macOS) with the same `command` and `args` under `mcpServers`; omit `type` and `enabled`. Other stdio MCP clients can use the same executable and script paths. Restart your client after editing its configuration.

## Use the tool

Ask your client to call `coppelia_step` with Python source in `code`. Example:

```python
# coppelia_step(code="...")
print(get_floor_info())
print(get_scene_hierarchy())
robot = load_robot('pioneer', [0.0, 0.0, 0.3])
print(sim.getObjectPosition(robot, -1))
```

Check `scene_objects` before creating objects; it contains root nodes with recursive `children`, including every non-system descendant. Each node includes `name`, unique `path`, transient `handle`, object `type`, `is_model`, world `pos`, and `children`. Handles are valid only for the current scene. If response contains `scene_hierarchy_error`, do not assume scene is empty.

| Parameter | Default | Behavior |
| --- | --- | --- |
| `code` | `""` | Python executed with `sim`, `client`, `simIK`, `simOMPL`, `solve_ik`, `plan_joint_path`, `load_robot`, scene helpers, and snapshot helpers. Empty code captures the current scene. |
| `reset` | `false` | Stops a running simulation before executing code; **does not clear scene objects**. |
| `headless` | `false` | Requests headless mode only if the server needs to launch CoppeliaSim. |
| `diagnostics` | `null` | Optional checks: `{ "kind": "collision", "objects": ["/A", "/B"] }`, `{ "kind": "distance", "objects": ["/A", "/B"], "threshold": 0.1 }`, or `{ "kind": "floor_bounds", "object": "/A" }`. |
| `timeout` | `30.0` | Maximum seconds for user script execution. Expiry interrupts the script and returns a failed result. |
Canceling the MCP request terminates the isolated runner process; only the worker is canceled, not the simulator process itself.

Response includes JSON text plus image content for each successful snapshot. Paths remain in the JSON response. Diagnostic results use `clear`, `issue`, or `unavailable`; checks inspect the post-script scene without advancing simulation time. Floor-boundary checks test each transformed object bounding-box corner against detected floor XY bounds. Distance checks always return the measured minimum distance and closest points; `threshold` only selects `issue` versus `clear`.

![Execution flow: code errors, successful snapshot capture, and snapshot warnings return different results](docs/images/execution-flow.png)

[View editable execution-flow diagram](docs/images/execution-flow.html).

### Structured simulation, catalog, and scene tools

`coppelia_simulate` advances the simulation in steps and returns sampled JSON state. It runs the simulator with stepping enabled, then leaves stepping off and the simulation running.

| Parameter | Default | Behavior |
| --- | --- | --- |
| `steps` | `100` | Number of steps to run, max `10000`. |
| `observe` | `null` | Object paths whose absolute positions are sampled, e.g. `["/PioneerP3DX"]`. |
| `sensors` | `null` | Proximity sensor paths read each sample; returns `detected` and `distance` (`null` when nothing detected). |
| `sample_every` | `1` | Record a sample every N steps. |
| `until` | `null` | Stop early when a diagnostic becomes `issue`: `{ "kind": "distance", "objects": ["/A", "/B"], "threshold": 0.1 }` or `collision`/`floor_bounds` as in `coppelia_step`. |
| `export_path` | `null` | Also write the full result JSON to this path. |
| `headless` | `false` | Requests headless mode only if the server launches CoppeliaSim. |

Object paths are CoppeliaSim absolute paths. Root objects need a leading slash: `/Shape` resolves, `Shape` returns "Object not found". Result includes `stopped_by` (`steps` or `condition`), `steps_run`, `final_time`, and `samples`.

`coppelia_catalog` searches `.ttm` models and `.ttt` scenes under `COPPELIASIM_ROOT` without contacting the simulator. Parameters: `query` (space-separated terms, all must match path or alias), `kind` (`all`, `model`, or `scene`), `limit` (default `50`). Results include `kind`, `name`, `path`, `relative`, and `alias`.

`coppelia_scene` saves or loads a scene. `action` is `save` or `load`; `path` is the `.ttt` file. Save requires an existing parent directory. Load stops a running simulation first, then replaces the current scene (unsaved objects are lost).

`coppelia_import_model` imports existing URDF, SDF, STL, OBJ, or DAE files. Optional `position` and `orientation` place every new root; `scale` applies to meshes. Results include created roots and joint counts. URDF `package_root` replaces `package://` resource prefixes. Imports modify the active scene.

`coppelia_ros2_status` checks whether CoppeliaSim can load `simROS2`. ROS 2 Humble runs in an isolated Docker image, avoiding host package changes. Build and start it with `./coppelia_ros2_container.sh build` and `./coppelia_ros2_container.sh start`. CoppeliaSim launches in GUI mode by default. Set `COPPELIASIM_ROS2_MODE=docker` to launch through the headless ROS 2 container, or `auto` to select that container when its image exists.

`coppelia_ros2` supports `publish`, `echo`, `service_call`, and `action_goal`. Pass `operation`, absolute ROS name, `interface_type` such as `std_msgs/msg/String`, and a JSON-object `payload` except for `echo`. Each operation uses Docker with host networking and shared IPC; `ROS_DOMAIN_ID` defaults to `0`.

### P2 floor plans, signals, and physics comparison

`coppelia_import_floorplan` converts a grayscale image into static cuboid segments. Pass `image_path`, `pixel_size`, `wall_height`, `door_height`, `window_height`, and non-overlapping grayscale ranges `wall_range`, `door_range`, and `window_range` as `[minimum, maximum]`. Pixels outside those ranges are ignored. `respondable` defaults to `true`. Inputs are limited to 1,000,000 pixels and 10,000 horizontal segments. This is an MCP image converter, not a wrapper around the CoppeliaSim GUI add-on.

`coppelia_signals` uses `operation="get"` or `"set"`, `signal_type="integer"|"float"|"string"`, and `name`; `value` is required for writes. A missing signal read returns `found=false`. Signals are simulator-local; this tool is not a PLC, OPC UA, or Modbus adapter.

`coppelia_physics_engine` reports and can set the scene's `dynamicsEngine` `[index, version]` pair and `dynamicsStepSize`; settings change only while simulation is stopped. `coppelia_physics_benchmark` accepts `scenes` as 2–5 engine-name to `.ttt` path entries plus identical `episodes`. Each scene must already be configured for its named engine; labels are caller-supplied and are not checked against scene properties. The tool reloads each scene and runs the same bounded episode definitions; save unsaved scene work first. Results compare task outcomes and elapsed simulation time, not equivalent solver parameters or hardware safety.

### Runtime health and typed motion

`coppelia_health` checks the active ZeroMQ endpoint, simulator version, and whether `simIK` and `simOMPL` load. It does not launch CoppeliaSim or alter the scene.

`coppelia_motion` provides two typed operations:

- `operation="ik"` requires `base`, `tip`, and `target` absolute object paths. Optional `constraints` accepts `pose`, `position`, or `orientation`; `method` accepts `damped_least_squares` or `pseudo_inverse`. A solved result is applied to the scene.
- `operation="plan"` requires `joints` paths and a numeric `goal` state. Optional `collision_pairs` contains pairs of object paths; `algorithm`, `max_time`, `simplify_time`, and `path_states` tune planning. The returned path is not applied to the robot.

Both operations return structured JSON and fail explicitly when plugins or object paths are unavailable.

`coppelia_trajectory` executes the `path` returned by `coppelia_motion`, passed as `trajectory`, in the same joint order. It interpolates each state over `steps_per_waypoint`, checks each joint's configured position and `max_velocity` limits, and requires at least one `collision_pairs` pair checked after every simulation step.

`gripper_actions` contains `{ "waypoint": 0, "joint": "/GripperJoint", "position": 0.0, "settle_steps": 5 }` entries. `grasp` requires `object`, `gripper`, `min_normal_force`, `hold_until_waypoint`, `min_lift`, `max_slip`, `max_rotation_rad`, and `wrench_sweep: { "force_n": 0.2, "torque_nm": 0.02, "steps_per_direction": 2 }`. The executor checks contact, translation and quaternion rotation relative to the gripper, then applies positive and negative force and torque on all three world axes. Failed contact, slip, lift, collision, or any tested wrench stops simulation. The 12-direction sweep measures only bounded wrench resistance; it is not an analytic force-closure proof or hardware-safety validation. `place` remains a geometric distance check. Successful execution leaves simulation running.

Live verification on CoppeliaSim 4.10.0: a Panda joint trajectory ran 80 steps toward 0.2 rad and reported 0.19711282 rad. Excess velocity was rejected; an intentional surface collision stopped the simulation (state `0`). Both camera captures were inspected and temporary models were removed. This run did not verify gripper manipulation.

P0 live grasp verification first used a synthetic lift fixture, not a commercial finger gripper. A later four-wall dynamic clamp passed a 12-direction sweep at ±0.05 N and ±0.001 N·m; measured translation and rotation stayed below `2.6e-7 m` and `4.9e-6 rad`. That fixture had no actuated arm or lift, and camera snapshots were black. The sweep does not prove analytic force closure, real-world friction, safe hardware, or successful release. See [P0 verification and REA evidence](docs/changes/p0-reset-contact-verification.md).

### Typed sensors, mechanism inspection, and experiments

`coppelia_sensors` accepts `sensors=[{"path": "/Robot/Camera", "type": "vision_rgb"}]`. Supported types: `proximity`, `vision_rgb`, `vision_depth`, `force_torque`, and `point_cloud`. RGB is RGB8 base64; depth values are metric float32 in sensor pixel order. Point clouds use metric depth and coordinates with +X right, +Y up, and +Z forward; `max_points` defaults to `4096` and caps sampled output. Vision sensor data is refreshed before each read. Sensor paths must match requested CoppeliaSim object types.

`coppelia_mechanism(root_path="/Robot")` reports descendant joints with type, interval, position, and target, plus sensors. The selected root is the base candidate. Leaf shapes and dummies are end-effector candidates only; the tool does not infer semantic tool frames.

`coppelia_experiments(initial_scene="/absolute/baseline.ttt", episodes=[...])` runs at most 20 episodes and 10000 combined steps. **Each episode replaces the current scene with that baseline**, removing objects and dynamic state from preceding episodes. Save unsaved scene work first. Per-episode `joint_positions` map absolute joint paths to positions applied while stopped, including position targets. Shared `observe`, `sensors` (proximity), and `sample_every` apply to all episodes.

Every episode requires nonempty `success_conditions`: `{ "kind": "object_position", "object": "/Part", "position": [0, 0, 0.5], "tolerance": 0.01 }` or `{ "kind": "proximity", "sensor": "/Sensor", "detected": true }`. All assertions must pass and no `until` diagnostic may trigger. Top-level `success` means the batch ran; inspect episode `success` and summary counts for task outcomes. Results include baseline `initial_state`, a step-zero sample, subsequent samples, elapsed simulation time, and `success_checks`. Assertions run while stepping remains enabled; the batch finishes stopped with stepping disabled. Reload does not reset external controllers or ROS 2 state.

These observation and batch tools return structured JSON and emit JSON event logs. They do not establish hardware safety.


### Command-line runner

```bash
./coppelia_run --code 'print(get_scene_hierarchy())'
./coppelia_run --file path/to/scene.py
./coppelia_run --reset --code 'sim.startSimulation()'
```

Runner accepts `--host` and `--port` for an existing remote simulator; MCP tool uses its default localhost port `23000`. `--reset` stops simulation, not object removal. For CLI options, run `./coppelia_run --help`.

## Troubleshooting

- **Cannot connect to `localhost:23000`:** Set `COPPELIASIM_ROOT`, run `bash coppelia_launch.sh --headless`, and inspect `/tmp/coppelia_stdout.log`. The launcher disables interactive Commander (`-GsimCmd.autoStart=false`): Commander exits on closed stdin during unattended startup. It also suppresses startup dialogs and selects `.venv/bin/python` for simulator scripts.
- **`Failed to import coppeliasim_zmqremoteapi_client`:** Check `COPPELIASIM_ROOT` points to the CoppeliaSim directory containing `programming/zmqRemoteApi/clients/python/src`, then rerun with the project virtual environment.
- **Robot model not found:** Check the model exists beneath `COPPELIASIM_ROOT/models`. Use `./coppelia_run --list-robots` to inspect alias paths or pass an existing `.ttm` path to `load_robot`.
- **No snapshots:** Check `stderr` in the tool response. Snapshots are written to `/tmp` only after successful code execution and capture; they are local to the machine running the server.

## Contributing

Issues and pull requests are welcome at [github.com/nashirabbash/coppeliasim-mcp](https://github.com/nashirabbash/coppeliasim-mcp). For local development, use the install steps above and verify basic CLI behavior with `./coppelia_run --list-robots`. A live simulator is required to verify scene changes and camera output. The optional `./run_benchmark.sh` exercises agent-driven scenes and requires a configured `omp` client; it changes the active simulation, so use a disposable scene.

## License

[MIT](LICENSE).
