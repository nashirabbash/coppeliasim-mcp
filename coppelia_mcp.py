#!/usr/bin/env python3
"""CoppeliaSim Unified High-Efficiency MCP Server.

Provides a self-documenting tool (`coppelia_step`) that embeds the exact
API cheat-sheet, signatures, constants, and pre-built robot models directly
in the tool description so the agent never wastes turns researching or trial-and-erroring.
"""

import math
import json
import base64
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult, ImageContent, TextContent
import asyncio

import sys
DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from runner import ROBOT_ALIASES
from scene_catalog import search_catalog
from scene_io import run_scene_action
from sim_run import run_simulation
from motion_tools import run_motion, runtime_health
from json_log import log
from trajectory_tools import run_trajectory
from p1_mcp_tools import register_p1_tools
from p2_mcp_tools import register_p2_tools


server = MCPServer("coppeliasim")

TOOL_DESCRIPTION = """🚨 STRICT SUPREME DIRECTIVE FOR AI AGENT (READ THIS FIRST):
NEVER CONCLUDE OR REPORT SUCCESS BASED SOLELY ON CODE LOGS OR EXIT STATUS!
You are interacting with a physical 3D simulation environment. Code that executes without error often produces physically broken scenes (e.g. walls collapsing under gravity, objects intersecting, robots falling through floors or flipped upside-down).

THEREFORE, YOU ARE STRICTLY REQUIRED TO USE YOUR EYES:
Every call returns TWO visual snapshots:
1. `/tmp/coppelia_topdown.png` (TOP-DOWN BIRD'S-EYE VIEW of entire board)
2. `/tmp/coppelia_snapshot.png` (ISOMETRIC 3D PERSPECTIVE VIEW of structures)

MANDATORY PROTOCOL AFTER EVERY CALL:
1. You MUST explicitly read and inspect BOTH image files using your image viewing / file inspection capabilities.
2. Check `/tmp/coppelia_topdown.png` to verify: 2D room dimensions, obstacle spacing, robot heading, and boundary clearance.
3. Check `/tmp/coppelia_snapshot.png` to verify: wall heights (e.g. 5m), roof alignment, upright robot stability, and no physical sagging or collision clipping.
4. IF YOUR EYES SEE ANY VISUAL DEFECT (collapsed wall, misplaced robot, clipping mesh), YOU MUST NOT CLAIM COMPLETION. You must immediately self-correct your script coordinates and run again!
Reporting "Task complete" without having visually verified both screenshots is a fatal protocol violation.

--------------------------------------------------------------------------------
TOOL SUMMARY:
Execute Python code directly inside CoppeliaSim simulator.
Auto-launches simulator if closed, runs physics/scene code, auto-captures dual camera snapshots, and returns execution result in ONE single call.

SCENE HIERARCHY AWARENESS RULE (PREVENT DUPLICATE MODELS):
Every call returns `"scene_objects"` as root nodes. Each node includes `name`, `path`, `handle`, `type`, `is_model`, `pos`, and recursive `children`; this covers every non-system object.
ALWAYS inspect the full hierarchy before creating or spawning:
1. DO NOT spawn a robot if a matching model already exists anywhere under `scene_objects`.
2. To reuse existing robot: `robot = sim.getObject('/PioneerP3DX')` (or use existing handle).
3. To remove duplicate/old objects: `sim.removeObject(sim.getObject('/OldName'))`.
If `scene_hierarchy_error` is present, scene inventory failed; do not treat an empty list as an empty scene.

WALLS & ENCLOSURE VISIBILITY RULE (PREVENT GREY VOID BLINDNESS):
NEVER build solid block labyrinths or closed rooms that entomb the camera/robot in solid gray geometry!
1. DO NOT spawn 50+ individual solid wall cuboids for mazes. Use thin perimeter borders instead (thickness 0.1m - 0.2m, NOT 0.8m thick blocks!).
2. Color your walls and floor distinctly (e.g. walls = light blue `[0.3, 0.6, 0.9]`, floor = dark grey `[0.2, 0.2, 0.2]`). NEVER leave all shapes default uncolored grey!
3. If creating rooms or houses with roofs: DO NOT seal roofs with solid opaque material. Either leave roof off, or make it high and distinctly colored so internal contents remain visible.


INJECTED OBJECTS IN CODE:
- `sim`: CoppeliaSim ZeroMQ API module.
- `simIK`: CoppeliaSim Inverse/Forward Kinematics solver module.
- `simOMPL`: Open Motion Planning Library module (RRT, RRT*, PRM path planners).
- `load_robot(alias, position=[x,y,z], orientation=[a,b,g])`: Loads robot model.
  Valid aliases: ['pioneer', 'youbot', 'hexapod', 'ant_hexapod', 'omni', 'quadcopter', 'asti', 'panda', 'ur5', 'ur10', 'vacuum', 'epuck'].
- `get_scene_hierarchy()`: Returns root objects with nested children for every non-system object type.
- `get_floor_info()`: Returns default floor size, position, and bounding box.
- `client`: RemoteAPIClient instance.

EXACT API CHEAT-SHEET (DO NOT SEARCH OR GUESS - USE THESE DIRECTLY):
1. Shapes & Environment:
   - Create cuboid: `h = sim.createPrimitiveShape(sim.primitiveshape_cuboid, [sizeX, sizeY, sizeZ], 0)`
   - Create cylinder: `h = sim.createPrimitiveShape(sim.primitiveshape_cylinder, [diameter, diameter, height], 0)`
   - Create sphere: `h = sim.createPrimitiveShape(sim.primitiveshape_sphere, [diameter, diameter, diameter], 0)`
   - Make static (walls/floors/roofs): `sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)`
   - Make respondable (solid collisions): `sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 1)`
   - Color shape: `sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse, [R, G, B])` # values 0.0 - 1.0

2. Positions & Hierarchy:
   - Set position: `sim.setObjectPosition(handle, -1, [x, y, z])` # -1 = absolute world coords
   - Get position: `pos = sim.getObjectPosition(handle, -1)` # returns [x, y, z]
   - Set orientation: `sim.setObjectOrientation(handle, -1, [alpha, beta, gamma])`
   - Find object by name: `h = sim.getObject('/ObjectName', {'noError': True})`
   - Remove object: `sim.removeObject(handle)`

3. Collision & Distance Detection:
   - Collision check: `result, collPair = sim.checkCollision(entity1Handle, entity2Handle)` # 1 = colliding, 0 = clear
   - Distance check: `result, distData, pairHandles = sim.checkDistance(entity1Handle, entity2Handle)` returns distance and closest points without a threshold.

Optional `diagnostics` request returns structured results in the JSON text content. Use `{"kind":"distance","objects":["/A","/B"],"threshold":0.1}` to receive `distance`, `closest_points`, `threshold`, and `status`; threshold only controls issue/clear classification. Scripts can also inspect and edit the full scene through `sim.*`.

4. Path & Motion Planning (simOMPL & simIK):
   - simOMPL Task: `task = simOMPL.createTask('task_name')`
   - Set Algorithm: `simOMPL.setAlgorithm(task, simOMPL.Algorithm.RRTConnect)` # or RRTstar, PRM
   - Compute Path: `solved, path = simOMPL.compute(task, maxTime=4.0)`
   - simIK Solver: `env = simIK.createEnvironment(); simIK.addElementFromScene(env, ikGroup, tip, target, base)`
   - Native Path Interpolation: `pathHandle = sim.createPath(ctrlPoints, options)`

5. Simulation & Motors:
   - Start simulation: `sim.startSimulation()`
   - Stop simulation: `sim.stopSimulation()`
   - Set motor velocity: `sim.setJointTargetVelocity(jointHandle, float_val)`
   - Read proximity sensor: `detected, dist, pt, obj, normal = sim.readProximitySensor(sensorHandle)`

```python
sim.stopSimulation()
# House floor
floor = sim.createPrimitiveShape(sim.primitiveshape_cuboid, [10.0, 10.0, 0.2], 0)
sim.setObjectInt32Param(floor, sim.shapeintparam_static, 1)
sim.setObjectInt32Param(floor, sim.shapeintparam_respondable, 1)

# Spawn robot inside
robot = load_robot('pioneer', [0.0, 0.0, 0.3])
sim.startSimulation()
```
"""


async def execute_step(script: str, reset: bool, headless: bool, timeout: float, diagnostics: list[dict] | None) -> dict:
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        return {"success": False, "error": "timeout must be a finite positive number", "stdout": "", "stderr": ""}
    runner = Path(__file__).with_name("runner.py")
    command = [sys.executable, str(runner), "--timeout", str(timeout)]
    command.append("--launch-headless" if headless else "--launch")
    if diagnostics is not None:
        command.extend(["--diagnostics", json.dumps(diagnostics)])
    if reset:
        command.append("--reset")
    process = await asyncio.create_subprocess_exec(
        *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(script.encode()), timeout=timeout + 35)
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        log("info", "simulator.script_cancelled")
        raise
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        log("error", "simulator.request_timed_out", timeout=timeout)
        return {"success": False, "error": "CoppeliaSim request timed out", "stdout": "", "stderr": ""}
    try:
        return json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"success": False, "error": f"Runner exited with status {process.returncode}", "stdout": "", "stderr": ""}


@server.tool(
    name="coppelia_step",
    description=TOOL_DESCRIPTION
)
async def coppelia_step(code: str = "", reset: bool = False, headless: bool = False, diagnostics: list[dict] | None = None, timeout: float = 30.0) -> CallToolResult:
    """Run script with timeout in seconds; timeout interrupts user Python execution."""
    script = code.strip() if code.strip() else "pass"
    result = await execute_step(script, reset, headless, timeout, diagnostics)

    snapshot_errors = []
    payload = {
        "topdown_snapshot": result.get("topdown_path"),
        "snapshot": result.get("snapshot_path"),
        "success": result["success"],
        "stdout": result["stdout"].strip(),
        "stderr": result["stderr"].strip(),
        "error": result["error"],
        "floor": result.get("floor"),
        "scene_objects": result.get("scene_objects"),
        "scene_hierarchy_error": result.get("scene_hierarchy_error"),
        "diagnostics": result.get("diagnostics", []),
        "available_robots": list(ROBOT_ALIASES.keys()) if not result["success"] else None,
        "snapshot_errors": snapshot_errors,
    }
    contents = [TextContent(type="text", text=json.dumps(
        {key: value for key, value in payload.items() if value is not None and value != ""},
        separators=(",", ":")
    ))]
    for key in ("snapshot", "topdown_snapshot"):
        path = result.get("snapshot_path" if key == "snapshot" else "topdown_path")
        if not path:
            continue
        try:
            contents.append(TextContent(type="text", text=f"{key}:"))
            contents.append(ImageContent(
                type="image",
                data=base64.b64encode(Path(path).read_bytes()).decode("ascii"),
                mimeType="image/png"
            ))
        except Exception as error:
            snapshot_errors.append({"snapshot": key, "error": str(error)})
    contents[0] = TextContent(type="text", text=json.dumps(
        {key: value for key, value in payload.items() if value is not None and value != ""},
        separators=(",", ":")
    ))
    return CallToolResult(content=contents)


SIMULATE_DESCRIPTION = "Step CoppeliaSim N times (or until a diagnostic issue). Returns positions and proximity sensor samples as JSON. until: {kind: collision|distance|floor_bounds, objects, threshold?}. export_path: .json file to write results."
CATALOG_DESCRIPTION = "Search CoppeliaSim model (.ttm) and scene (.ttt) files by space-separated terms matched against relative path and robot alias. kind: all|model|scene."
SCENE_DESCRIPTION = "Save or load a CoppeliaSim scene. action: save|load. path: absolute .ttt path. load stops the running simulation and replaces the current scene."


def json_result(payload: dict) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload, indent=2))])


@server.tool(name="coppelia_simulate", description=SIMULATE_DESCRIPTION)
async def coppelia_simulate(steps: int = 100, observe: list[str] | None = None, sensors: list[str] | None = None, sample_every: int = 1, until: dict | None = None, export_path: str | None = None, headless: bool = False) -> CallToolResult:
    """Run structured simulation and return sampled state as JSON."""
    return json_result(run_simulation(steps=steps, observe=observe, sensors=sensors, sample_every=sample_every, until=until, export_path=export_path, headless=headless))


@server.tool(name="coppelia_catalog", description=CATALOG_DESCRIPTION)
async def coppelia_catalog(query: str = "", kind: str = "all", limit: int = 50) -> CallToolResult:
    """Search model and scene catalog; no simulator needed."""
    try:
        return json_result(search_catalog(query, kind, limit))
    except ValueError as error:
        return json_result({"success": False, "error": str(error)})


@server.tool(name="coppelia_scene", description=SCENE_DESCRIPTION)
async def coppelia_scene(action: str, path: str, headless: bool = False) -> CallToolResult:
    """Save or load a scene through the simulator."""
    return json_result(run_scene_action(action, path, headless=headless))

@server.tool(name="coppelia_health", description="Check active ZeroMQ connection, simulator version, and runtime availability of simIK and simOMPL. Does not launch or modify the scene.")
async def coppelia_health(host: str = "localhost", port: int = 23000) -> CallToolResult:
    result = await asyncio.to_thread(runtime_health, host, port)
    log("info" if result["connected"] else "error", "simulator.health_result", **result)
    return json_result(result)


@server.tool(name="coppelia_motion", description="Typed motion operations: operation='ik' uses base, tip, target, constraints and method; operation='plan' uses joints, goal, collision_pairs, algorithm, max_time, simplify_time and path_states. Planning returns a path and never applies it to robot joints.")
async def coppelia_motion(
    operation: str,
    base: str | None = None,
    tip: str | None = None,
    target: str | None = None,
    constraints: str = "pose",
    method: str = "damped_least_squares",
    damping: float = 0.02,
    iterations: int = 20,
    joints: list[str] | None = None,
    goal: list[float] | None = None,
    collision_pairs: list[list[str]] | None = None,
    algorithm: str = "RRTConnect",
    max_time: float = 4.0,
    simplify_time: float = 0.5,
    path_states: int = 100,
    headless: bool = False,
) -> CallToolResult:
    if operation == "ik":
        parameters = {
            "base": base, "tip": tip, "target": target,
            "constraints": constraints, "method": method,
            "damping": damping, "iterations": iterations
        }
    elif operation == "plan":
        parameters = {
            "joints": joints or [], "goal": goal or [],
            "collision_pairs": collision_pairs or [], "algorithm": algorithm,
            "max_time": max_time, "simplify_time": simplify_time, "path_states": path_states
        }
    else:
        parameters = {}
    result = await asyncio.to_thread(run_motion, operation, headless, **parameters)
    return json_result(result)

@server.tool(name="coppelia_trajectory", description="Execute a joint path with velocity and optional acceleration/jerk limits, per-step collision checks, dynamic-contact grasp checks with post-lift retention and slip limits, and distance-based place checks.")
async def coppelia_trajectory(joints: list[str], trajectory: list[list[float]], collision_pairs: list[list[str]], max_velocity: list[float], steps_per_waypoint: int = 10, gripper_actions: list[dict] | None = None, max_acceleration: list[float] | None = None, max_jerk: list[float] | None = None, headless: bool = False) -> CallToolResult:
    result = await asyncio.to_thread(run_trajectory, headless, joints=joints, trajectory=trajectory, collision_pairs=collision_pairs, max_velocity=max_velocity, steps_per_waypoint=steps_per_waypoint, gripper_actions=gripper_actions or [], max_acceleration=max_acceleration, max_jerk=max_jerk)
    return json_result(result)





register_p1_tools(server, json_result)
register_p2_tools(server, json_result)

if __name__ == "__main__":
    server.run(transport="stdio")
