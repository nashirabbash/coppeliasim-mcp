#!/usr/bin/env python3
"""CoppeliaSim CLI Runner for omp agents.

Connects to CoppeliaSim via ZeroMQ Remote API, provides helper utilities
for loading robot models, executes Python scene manipulation scripts,
and automatically captures observer camera snapshots.
"""

import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import time
import socket


# Add CoppeliaSim bundled Python client to sys.path
COPPELIA_ROOT = Path(os.environ.get("COPPELIASIM_ROOT", "/home/myarchlinux/.local/opt/coppeliaSim"))
CLIENT_SRC = COPPELIA_ROOT / "programming" / "zmqRemoteApi" / "clients" / "python" / "src"
if CLIENT_SRC.exists() and str(CLIENT_SRC) not in sys.path:
    sys.path.insert(0, str(CLIENT_SRC))

try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
except ImportError as err:
    print(json.dumps({
        "success": False,
        "error": f"Failed to import coppeliasim_zmqremoteapi_client: {err}. Run setup_env.sh first."
    }))
SNAPSHOT_PATH = Path("/tmp/coppelia_snapshot.png")
TOPDOWN_SNAPSHOT_PATH = Path("/tmp/coppelia_topdown.png")
OBSERVER_CAM_NAME = "Agent_Observer_Cam"
TOPDOWN_CAM_NAME = "Agent_TopDown_Cam"

# Calibrated isometric camera (diagonal perspective view):
CALIBRATED_CAM_POS = [9.0, -9.0, 7.5]
CALIBRATED_CAM_ROT = [-2.1588, -0.6940, 2.7385]
CALIBRATED_FOV_DEG = 65.0

# Calibrated top-down camera (bird's-eye view looking straight down at simulation board):
TOPDOWN_CAM_POS = [0.0, 0.0, 15.0]
TOPDOWN_CAM_ROT = [3.14159265, 0.0, 0.0]
TOPDOWN_FOV_DEG = 70.0

from PIL import Image

# Standard pre-built model aliases mapped to relative paths under models/
ROBOT_ALIASES = {
    "pioneer": "robots/mobile/pioneer p3dx.ttm",
    "pioneer_p3dx": "robots/mobile/pioneer p3dx.ttm",
    "youbot": "robots/mobile/KUKA YouBot.ttm",
    "kuka_youbot": "robots/mobile/KUKA YouBot.ttm",
    "hexapod": "robots/mobile/hexapod.ttm",
    "ant_hexapod": "robots/mobile/ant hexapod.ttm",
    "omni": "robots/mobile/Omnidirectional Platform.ttm",
    "quadcopter": "robots/mobile/Quadcopter.ttm",
    "nao": "robots/mobile/NAO.ttm",
    "asti": "robots/mobile/Asti.ttm",
    "humanoid": "robots/mobile/Asti.ttm",
    "epuck": "robots/mobile/e-puck.ttm",
    "panda": "robots/non-mobile/FrankaEmikaPanda.ttm",
    "ur5": "robots/non-mobile/UR5.ttm",
    "ur10": "robots/non-mobile/UR10.ttm",
    "vacuum": "examples/vacuum robot.ttm"
}

def resolve_model_path(name: str) -> Path:
    """Resolve robot alias or path to an absolute .ttm model path."""
    name_clean = name.strip().lower()
    if name_clean in ROBOT_ALIASES:
        rel = ROBOT_ALIASES[name_clean]
        p = COPPELIA_ROOT / "models" / rel
        if p.exists():
            return p
    
    # Try direct relative path under models/
    candidate = COPPELIA_ROOT / "models" / name
    if candidate.exists():
        return candidate
    candidate_ttm = COPPELIA_ROOT / "models" / f"{name}.ttm"
    if candidate_ttm.exists():
        return candidate_ttm

    # Direct absolute path
    p = Path(name)
    if p.exists():
        return p
    
    raise FileNotFoundError(f"Robot model '{name}' not found. Available aliases: {list(ROBOT_ALIASES.keys())}")


def is_coppelia_running(host: str = "localhost", port: int = 23000) -> bool:
    """Check if CoppeliaSim ZeroMQ server is responsive."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def launch_coppelia(headless: bool = False, timeout: int = 25):
    """Launch CoppeliaSim application if not currently running."""
    if is_coppelia_running():
        return True

    cmd = ["/home/myarchlinux/Documents/CoppeliaTools/coppelia_launch.sh"]
    if headless:
        cmd.append("--headless")
    subprocess.run(cmd, check=True)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_coppelia_running():
            return True
        time.sleep(0.5)
    return False


def ensure_camera(sim, name: str, pos: list, rot: list, fov_deg: float):
    """Ensure a calibrated vision sensor exists in the scene."""
    cam_handle = sim.getObject(f"/{name}", {"noError": True})
    if cam_handle == -1:
        int_params = [1024, 768, 0, 0] # 1024x768 resolution
        # float_params[3] = 0.5 (sensor physical size in GUI, easily visible in scene hierarchy)
        float_params = [0.1, 100.0, fov_deg * 3.14159265 / 180.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        cam_handle = sim.createVisionSensor(3, int_params, float_params)
        sim.setObjectAlias(cam_handle, name)
        # Make it persistent / static
        sim.setObjectProperty(cam_handle, sim.objectproperty_selectable)
    sim.setObjectPosition(cam_handle, -1, pos)
    sim.setObjectOrientation(cam_handle, -1, rot)
    return cam_handle


def ensure_observer_camera(sim):
    """Ensure floating isometric perspective camera exists."""
    return ensure_camera(sim, OBSERVER_CAM_NAME, CALIBRATED_CAM_POS, CALIBRATED_CAM_ROT, CALIBRATED_FOV_DEG)


def ensure_topdown_camera(sim):
    """Ensure bird's-eye top-down camera exists directly above board looking down."""
    return ensure_camera(sim, TOPDOWN_CAM_NAME, TOPDOWN_CAM_POS, TOPDOWN_CAM_ROT, TOPDOWN_FOV_DEG)

def get_floor_info(sim) -> dict:
    """Detect default scene floor size, bounds, and position."""
    floor_candidates = ['/Floor', '/floor', '/Floor_5_25', '/resizableFloor']
    floor_handle = -1
    for cand in floor_candidates:
        h = sim.getObject(cand, {'noError': True})
        if h != -1:
            floor_handle = h
            break

    if floor_handle == -1:
        shapes = sim.getObjectsInTree(sim.handle_scene, sim.object_shape_type, 0)
        for s in shapes:
            alias = sim.getObjectAlias(s).lower()
            if "floor" in alias:
                floor_handle = s
                break

    if floor_handle != -1:
        try:
            bb_dims, _ = sim.getShapeBB(floor_handle)
            pos = sim.getObjectPosition(floor_handle, -1)
            sx, sy, sz = round(bb_dims[0], 2), round(bb_dims[1], 2), round(bb_dims[2], 2)
            px, py, pz = round(pos[0], 2), round(pos[1], 2), round(pos[2], 2)
            return {
                "handle": floor_handle,
                "name": sim.getObjectAlias(floor_handle),
                "size_x": sx,
                "size_y": sy,
                "size_z": sz,
                "pos": [px, py, pz],
                "bounds_x": [round(px - sx/2, 2), round(px + sx/2, 2)],
                "bounds_y": [round(py - sy/2, 2), round(py + sy/2, 2)],
                "surface_z": round(pz + sz/2, 2)
            }
        except Exception:
            pass

    return {"exists": False, "size_x": 0.0, "size_y": 0.0, "bounds_x": [0, 0], "bounds_y": [0, 0], "surface_z": 0.0}


SYSTEM_OBJECT_PREFIXES = (
    'XYZCamera', 'XView', 'YView', 'ZView', 'NXView', 'NYView', 'NZView',
    'DefaultLights', 'DefaultCamera', 'LightA', 'LightB', 'LightC', 'LightD',
    'Agent_'
)


def get_scene_hierarchy(sim) -> list:
    """Extract active user objects and models in scene to prevent duplicate creations."""
    try:
        root_objs = sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 1)
        scene_items = []
        for h in root_objs:
            alias = sim.getObjectAlias(h)
            if any(alias.startswith(p) for p in SYSTEM_OBJECT_PREFIXES):
                continue
            pos = [round(x, 2) for x in sim.getObjectPosition(h, -1)]
            try:
                is_model = (sim.getModelProperty(h) & sim.modelproperty_not_model) == 0
            except Exception:
                is_model = False
            scene_items.append({
                "name": alias,
                "handle": h,
                "is_model": is_model,
                "pos": pos
            })
        return scene_items
    except Exception:
        return []



def capture_snapshot(sim, output_path: Path = SNAPSHOT_PATH, cam_type: str = "isometric") -> str:
    """Capture RGB frame from specified camera and save cleanly to disk."""
    cam_handle = ensure_topdown_camera(sim) if cam_type == "topdown" else ensure_observer_camera(sim)
    sim.handleVisionSensor(cam_handle)
    img_bytes, resolution = sim.getVisionSensorImg(cam_handle)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sim.saveImage(img_bytes, resolution, 0, str(output_path), -1)
    return str(output_path)


def capture_all_snapshots(sim):
    """Capture both isometric and top-down views."""
    iso_path = capture_snapshot(sim, SNAPSHOT_PATH, "isometric")
    top_path = capture_snapshot(sim, TOPDOWN_SNAPSHOT_PATH, "topdown")
    return iso_path, top_path

def make_load_robot_fn(sim):
    """Factory creating the load_robot helper injected into agent code."""
    def load_robot(name: str, position: list = None, orientation: list = None):
        model_path = resolve_model_path(name)
        handle = sim.loadModel(str(model_path))
        if position is not None:
            sim.setObjectPosition(handle, -1, position)
        if orientation is not None:
            sim.setObjectOrientation(handle, -1, orientation)
        return handle
    return load_robot


def run_code(code: str, host: str = "localhost", port: int = 23000, take_snapshot: bool = True, reset: bool = False, auto_launch: bool = False, headless: bool = False):
    """Execute code against CoppeliaSim and return structured result."""
    if auto_launch and not is_coppelia_running(host, port):
        launched = launch_coppelia(headless=headless)
        if not launched:
            return {
                "success": False,
                "error": f"Auto-launch failed. CoppeliaSim port {port} did not become ready.",
                "stdout": "",
                "stderr": ""
            }

    try:
        client = RemoteAPIClient(host=host, port=port)
        sim = client.require("sim")
    except Exception as err:
        return {
            "success": False,
            "error": f"Failed to connect to CoppeliaSim at {host}:{port}. Is CoppeliaSim running? Details: {err}",
            "stdout": "",
            "stderr": ""
        }

    if reset:
        try:
            sim.stopSimulation()
        except Exception:
            pass

    # Always ensure both cameras exist in scene hierarchy on connection
    try:
        ensure_topdown_camera(sim)
        ensure_observer_camera(sim)
    except Exception:
        pass

    load_robot_fn = make_load_robot_fn(sim)

    # Injected environment
    env = {
        "client": client,
        "sim": sim,
        "load_robot": load_robot_fn,
        "capture_snapshot": lambda: capture_snapshot(sim, SNAPSHOT_PATH, "isometric"),
        "capture_topdown": lambda: capture_snapshot(sim, TOPDOWN_SNAPSHOT_PATH, "topdown"),
        "ROBOT_ALIASES": list(ROBOT_ALIASES.keys()),
        "get_floor_info": lambda: get_floor_info(sim),
        "get_scene_hierarchy": lambda: get_scene_hierarchy(sim),


    }


    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exec_success = False
    exec_error = None

    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        try:
            exec(code, env)
            exec_success = True
        except Exception as e:
            exec_error = str(e)

    snapshot_file = None
    topdown_file = None
    if take_snapshot and exec_success:
        try:
            snapshot_file, topdown_file = capture_all_snapshots(sim)
        except Exception as snap_err:
            stderr_buf.write(f"\n[Warning: Snapshot capture failed: {snap_err}]")

    floor_data = None
    scene_hierarchy = []
    try:
        floor_data = get_floor_info(sim)
        scene_hierarchy = get_scene_hierarchy(sim)
    except Exception:
        pass

    return {
        "success": exec_success,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "error": exec_error,
        "snapshot_path": snapshot_file,
        "topdown_path": topdown_file,
        "floor": floor_data,
        "scene_objects": scene_hierarchy
    }


def main():
    parser = argparse.ArgumentParser(description="Execute Python scripts against CoppeliaSim")
    parser.add_argument("--code", type=str, help="Python code string to execute")
    parser.add_argument("--file", type=str, help="Path to Python script file to execute")
    parser.add_argument("--host", type=str, default="localhost", help="CoppeliaSim ZMQ host")
    parser.add_argument("--port", type=int, default=23000, help="CoppeliaSim ZMQ port")
    parser.add_argument("--no-snapshot", action="store_true", help="Disable auto-capture snapshot")
    parser.add_argument("--reset", action="store_true", help="Stop simulation before running")
    parser.add_argument("--list-robots", action="store_true", help="List available robot model aliases")

    parser.add_argument("--launch", action="store_true", help="Launch CoppeliaSim GUI if not already running")
    parser.add_argument("--launch-headless", action="store_true", help="Launch CoppeliaSim in headless mode if not running")
    parser.add_argument("--only-launch", action="store_true", help="Launch CoppeliaSim and exit")

    args = parser.parse_args()

    if args.list_robots:
        print(json.dumps({"robot_aliases": ROBOT_ALIASES}, indent=2))
        return

    if args.only_launch:
        if not is_coppelia_running(args.host, args.port):
            launch_coppelia(headless=args.launch_headless)
        print(json.dumps({"success": True, "message": "CoppeliaSim is running and ready."}))
        return

    code_to_run = ""
    if args.code:
        code_to_run = args.code
    elif args.file:
        with open(args.file, "r") as f:
            code_to_run = f.read()
    else:
        # Check stdin
        if not sys.stdin.isatty():
            code_to_run = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(1)

    result = run_code(
        code=code_to_run,
        host=args.host,
        port=args.port,
        take_snapshot=not args.no_snapshot,
        reset=args.reset,
        auto_launch=args.launch or args.launch_headless,
        headless=args.launch_headless
    )

    print(json.dumps(result, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
