#!/usr/bin/env python3
"""CoppeliaSim Unified Minimal MCP Server.

Provides a single high-efficiency tool (`coppelia_step`) to minimize
round-trip tool calling and drastically save token budget.
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


@server.tool(
    name="coppelia_step",
    description=(
        "Unified CoppeliaSim executor. Auto-launches simulator if closed, runs Python code "
        "with 'sim' and 'load_robot(alias, [x,y,z])' injected, captures camera snapshot, "
        "and returns execution result + simulation state in ONE call."
    )
)
async def coppelia_step(code: str = "", reset: bool = False, headless: bool = False) -> str:
    """Execute Python code against CoppeliaSim in a single round-trip.

    Args:
        code: Python script manipulating scene (objects, joints, simulation). If empty, returns status & snapshot.
        reset: If True, resets/stops current simulation before executing code.
        headless: If True and simulator is not running, launches without GUI.
    """
    # 1. Run code (with auto-launch and auto-snapshot enabled by default)
    script = code.strip() if code.strip() else "pass"
    result = run_code(
        code=script,
        take_snapshot=True,
        reset=reset,
        auto_launch=True,
        headless=headless
    )

    # 2. Pack compact summary in one response
    payload = {
        "success": result["success"],
        "stdout": result["stdout"].strip(),
        "stderr": result["stderr"].strip(),
        "error": result["error"],
        "snapshot": result["snapshot_path"] if result["snapshot_path"] and Path(result["snapshot_path"]).exists() else None,
        "available_robots": list(ROBOT_ALIASES.keys()) if not result["success"] else None
    }

    # Clean nulls to save tokens
    clean_payload = {k: v for k, v in payload.items() if v is not None and v != ""}
    return json.dumps(clean_payload, separators=(',', ':'))


if __name__ == "__main__":
    server.run(transport="stdio")
