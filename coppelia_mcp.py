#!/usr/bin/env python3
"""CoppeliaSim Unified High-Efficiency MCP Server.

Provides a self-documenting tool (`coppelia_step`) that embeds the exact
API cheat-sheet, signatures, constants, and pre-built robot models directly
in the tool description so the agent never wastes turns researching or trial-and-erroring.
"""

import json
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import mcp.server.stdio

import sys
DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from runner import (
    run_code,
    ROBOT_ALIASES,
    SNAPSHOT_PATH,
    is_coppelia_running
)

server = MCPServer("coppeliasim")

TOOL_DESCRIPTION = """Execute Python code directly inside CoppeliaSim simulator.
Auto-launches simulator if closed, runs physics/scene code, auto-captures camera snapshot to /tmp/coppelia_snapshot.png, and returns execution result in ONE single call.

INJECTED OBJECTS IN CODE:
- `sim`: CoppeliaSim ZeroMQ API module.
- `load_robot(alias, position=[x,y,z], orientation=[a,b,g])`: Loads robot model.
  Valid aliases: ['pioneer', 'youbot', 'hexapod', 'ant_hexapod', 'omni', 'quadcopter', 'asti', 'panda', 'ur5', 'ur10', 'vacuum', 'epuck'].
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

3. Simulation & Motors:
   - Start simulation: `sim.startSimulation()`
   - Stop simulation: `sim.stopSimulation()`
   - Set motor velocity: `sim.setJointTargetVelocity(jointHandle, float_val)`
   - Read proximity sensor: `detected, dist, pt, obj, normal = sim.readProximitySensor(sensorHandle)`

EXAMPLE READY-TO-RUN CODE:
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


@server.tool(
    name="coppelia_step",
    description=TOOL_DESCRIPTION
)
async def coppelia_step(code: str = "", reset: bool = False, headless: bool = False) -> str:
    """Execute Python code against CoppeliaSim in a single round-trip.

    Args:
        code: Python script using sim.* and load_robot(). If empty, captures snapshot & returns status.
        reset: If True, resets/stops current simulation before executing code.
        headless: If True and simulator is not running, launches without GUI.
    """
    script = code.strip() if code.strip() else "pass"
    result = run_code(
        code=script,
        take_snapshot=True,
        reset=reset,
        auto_launch=True,
        headless=headless
    )

    payload = {
        "success": result["success"],
        "stdout": result["stdout"].strip(),
        "stderr": result["stderr"].strip(),
        "error": result["error"],
        "snapshot": result["snapshot_path"] if result["snapshot_path"] and Path(result["snapshot_path"]).exists() else None,
        "available_robots": list(ROBOT_ALIASES.keys()) if not result["success"] else None
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None and v != ""}
    return json.dumps(clean_payload, separators=(',', ':'))


if __name__ == "__main__":
    server.run(transport="stdio")
