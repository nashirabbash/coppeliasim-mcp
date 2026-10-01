# CoppeliaSim MCP Server 🤖🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-1.0%20%2F%202.0-blue)](https://modelcontextprotocol.io)

High-efficiency, token-optimized **Model Context Protocol (MCP)** server providing direct integration between AI agents (**Claude Desktop**, **omp**, **Cursor**, **Windsurf**, **Zed**) and the **CoppeliaSim** robotics simulator.

---

## ✨ Features

- **⚡ Token-Optimized (`coppelia_step`)**: Single unified tool call replacing fragmented multi-round trips. Auto-launches, runs code, extracts floor & hierarchy, and captures multimodal snapshots in **one request**.
- **👁️ Dual-Camera Visual Eyes**:
  - **`topdown_snapshot`** (`/tmp/coppelia_topdown.png`): Bird's-eye view above the simulation board to verify 2D placement, room boundaries, and navigation.
  - **`snapshot`** (`/tmp/coppelia_snapshot.png`): Elevated isometric 3D perspective to verify object heights, wall alignment, and robot upright stability.
- **📐 Auto Floor & Scene Hierarchy Awareness**: Returns exact floor bounding box (`size_x`, `size_y`, `surface_z`) and existing scene objects (`scene_objects`) on every turn to prevent duplicate models.
- **🤖 Built-in Robot Catalog**: Injected `load_robot(alias, [x, y, z])` supporting pre-tested models:
  - Mobile: `'pioneer'`, `'youbot'`, `'hexapod'`, `'ant_hexapod'`, `'omni'`, `'quadcopter'`, `'asti'`, `'epuck'`, `'vacuum'`
  - Manipulators: `'panda'`, `'ur5'`, `'ur10'`
- **🛡️ Self-Documenting Zero-Discovery**: Complete API cheat-sheet and constants embedded in tool schema so agents do not waste tokens guessing functions.

---

## 📋 Prerequisites

1. **CoppeliaSim** (v4.3+ recommended, Linux / macOS / Windows) with ZeroMQ Remote API enabled (default port `23000`).
2. **Python >= 3.10**.

---

## 🚀 Installation & Setup

Clone the repository and install dependencies in an isolated virtual environment:

```bash
git clone https://github.com/nashirabbash/coppeliasim-mcp.git
cd coppeliasim-mcp

# Setup environment
chmod +x setup_env.sh
./setup_env.sh
```

---

## 🔌 Configuration Across Agent Harnesses

### 1. `omp` Harness
Add to `~/.omp/agent/mcp.json`:
```json
{
  "mcpServers": {
    "coppeliasim": {
      "type": "stdio",
      "command": "/path/to/coppeliasim-mcp/.venv/bin/python",
      "args": [
        "/path/to/coppeliasim-mcp/coppelia_mcp.py"
      ],
      "enabled": true
    }
  }
}
```

### 2. Claude Desktop
Add to `~/.config/Claude/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "coppeliasim": {
      "command": "/path/to/coppeliasim-mcp/.venv/bin/python",
      "args": [
        "/path/to/coppeliasim-mcp/coppelia_mcp.py"
      ]
    }
  }
}
```

### 3. Cursor / Windsurf / Zed
Add to your workspace `.cursor/mcp.json` or global settings:
```json
{
  "mcpServers": {
    "coppeliasim": {
      "command": "/path/to/coppeliasim-mcp/.venv/bin/python",
      "args": [
        "/path/to/coppeliasim-mcp/coppelia_mcp.py"
      ]
    }
  }
}
```

---

## 🛠️ Tool Schema: `coppelia_step`

The agent interacts via a single function:

```python
coppelia_step(
    code: str = "",         # Python code manipulating scene (sim.* and load_robot)
    reset: bool = False,    # If True, stops simulation before execution
    headless: bool = False  # If True, launches simulator without GUI
)
```

### Injected Environment
Inside the `code` string, the script directly accesses:
- `sim`: CoppeliaSim ZeroMQ API module.
- `load_robot(alias, position=[x, y, z])`: Loads pre-built robot model.
- `get_floor_info()`: Current floor boundaries and elevation.
- `get_scene_hierarchy()`: Currently active scene shapes and models.
- `capture_snapshot()`: Captures camera frame.

### Response Payload
```json
{
  "success": true,
  "stdout": "...",
  "floor": {
    "size_x": 5.0,
    "size_y": 5.0,
    "bounds_x": [-2.5, 2.5],
    "bounds_y": [-2.5, 2.5],
    "surface_z": 0.0
  },
  "scene_objects": [
    {"name": "PioneerP3DX", "handle": 25, "is_model": true, "pos": [0.0, 0.0, 0.3]}
  ],
  "snapshot": "/tmp/coppelia_snapshot.png",
  "topdown_snapshot": "/tmp/coppelia_topdown.png",
  "eye_evaluation_directive": "EVALUATE YOUR EYES: Read /tmp/coppelia_topdown.png and /tmp/coppelia_snapshot.png before replying."
}
```

---

## 📊 Benchmark & Evaluation

Run the automated evaluation benchmark:
```bash
./run_benchmark.sh
```
Measures token consumption, tool invocation count, physical scene reality, and visual validity.

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
