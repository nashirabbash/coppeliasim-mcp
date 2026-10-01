#!/usr/bin/env python3
"""CoppeliaSim MCP Server.

Exposes CoppeliaSim robotics simulation capabilities as native MCP tools
over standard stdio JSON-RPC using MCP 2.x API.
"""

import json
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import mcp.server.stdio

# Import runner utilities
import sys
DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from runner import (
    run_code,
    launch_coppelia,
    is_coppelia_running,
    ROBOT_ALIASES,
    SNAPSHOT_PATH
)

server = MCPServer("coppeliasim")


@server.tool(
    name="launch_simulator",
    description="Launch CoppeliaSim robotics simulator if not already running."
)
async def launch_simulator(headless: bool = False) -> str:
    """Launch CoppeliaSim application."""
    if is_coppelia_running():
        return "CoppeliaSim is already running and connected on port 23000."
    success = launch_coppelia(headless=headless)
    if success:
        mode = "headless" if headless else "GUI"
        return f"CoppeliaSim launched successfully in {mode} mode on port 23000."
    return "Failed to launch CoppeliaSim or connect to port 23000."


@server.tool(
    name="execute_code",
    description="Execute Python code in CoppeliaSim using sim.* and injected helpers like load_robot()."
)
async def execute_code(python_code: str, reset_simulation: bool = False) -> str:
    """Execute Python code in CoppeliaSim."""
    result = run_code(
        code=python_code,
        take_snapshot=True,
        reset=reset_simulation,
        auto_launch=True,
        headless=False
    )
    return json.dumps(result, indent=2)


@server.tool(
    name="get_snapshot",
    description="Get file path and info of the latest camera snapshot image."
)
async def get_snapshot() -> str:
    """Get the latest snapshot path and status."""
    if not SNAPSHOT_PATH.exists():
        run_code("pass", take_snapshot=True, auto_launch=True)
    if SNAPSHOT_PATH.exists():
        return json.dumps({
            "snapshot_path": str(SNAPSHOT_PATH),
            "size_bytes": SNAPSHOT_PATH.stat().st_size
        })
    return json.dumps({"error": "Snapshot unavailable"})


@server.tool(
    name="list_available_robots",
    description="List valid robot model aliases for load_robot() (e.g. pioneer, youbot, hexapod, asti)."
)
async def list_available_robots() -> list[str]:
    """List valid robot model aliases."""
    return list(ROBOT_ALIASES.keys())


@server.tool(
    name="get_simulation_status",
    description="Check whether CoppeliaSim is running and get current simulation time and state."
)
async def get_simulation_status() -> str:
    """Check simulation state."""
    running = is_coppelia_running()
    if not running:
        return json.dumps({"running": False, "message": "CoppeliaSim not running"})

    result = run_code(
        code="print(json.dumps({'state': sim.getSimulationState(), 'time': sim.getSimulationTime()}))",
        take_snapshot=False
    )
    return result.get("stdout") or json.dumps({"running": True})


if __name__ == "__main__":
    server.run(transport="stdio")
