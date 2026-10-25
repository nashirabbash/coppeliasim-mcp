#!/usr/bin/env python3
"""CoppeliaSim CLI Runner for omp agents.

Executes Python scripts against the simulator's ZeroMQ Remote API
and automatically captures observer camera snapshots.
"""

import math

import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import time
import signal
import socket
from json_log import log

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
TOPDOWN_CAM_POS = [0.0, 0.0, 20.0]
TOPDOWN_CAM_ROT = [3.14159, 0.0, 0.0]
TOPDOWN_FOV_DEG = 90.0

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

    cmd = [str(Path(__file__).resolve().with_name("coppelia_launch.sh"))]
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

def auto_frame_gui_camera(sim):
    """Auto-frame GUI DefaultCamera to Bird's-Eye Top-Down view directly above board.
    Positions GUI DefaultCamera looking straight down at the entire board without clipping.
    """
    try:
        gui_cam = sim.getObject('/DefaultCamera', {'noError': True})
        if gui_cam == -1:
            return

        # Calculate extent of scene to adjust height if scene is large
        shapes = sim.getObjectsInTree(sim.handle_scene, sim.object_shape_type, 0)
        max_r = 5.0
        for s in shapes:
            if s == 13: # skip default floor
                continue
            pos = sim.getObjectPosition(s, -1)
            r = (pos[0]**2 + pos[1]**2)**0.5
            if r > max_r:
                max_r = r

        # Set height dynamically based on scene radius (minimum 15m)
        cam_z = max(max_r * 2.2, 15.0)
        sim.setObjectPosition(gui_cam, -1, [0.0, 0.0, cam_z])
        # Exact top-down rotation: pointing straight down (-Z)
        sim.setObjectOrientation(gui_cam, -1, [3.14159265, 0.0, 0.0])
    except Exception:
        pass


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

SCENE_OBJECT_TYPE_NAMES = (
    ("sceneobject_shape", "shape"),
    ("sceneobject_joint", "joint"),
    ("sceneobject_graph", "graph"),
    ("sceneobject_camera", "camera"),
    ("sceneobject_light", "light"),
    ("sceneobject_dummy", "dummy"),
    ("sceneobject_proximitysensor", "proximity sensor"),
    ("sceneobject_octree", "octree"),
    ("sceneobject_pointcloud", "point cloud"),
    ("sceneobject_visionsensor", "vision sensor"),
    ("sceneobject_forcesensor", "force sensor"),
    ("sceneobject_script", "script"),
)


def get_scene_hierarchy(sim) -> list:
    """Return visible scene roots with recursively nested user objects."""
    handles = sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 0)
    children_by_parent = {}
    for handle in handles:
        parent = sim.getObjectParent(handle)
        children_by_parent.setdefault(parent, []).append(handle)

    object_type_names = {
        getattr(sim, constant): name
        for constant, name in SCENE_OBJECT_TYPE_NAMES
        if hasattr(sim, constant)
    }
    object_count = 0

    def build_node(handle):
        nonlocal object_count
        alias = sim.getObjectAlias(handle)
        if any(alias.startswith(prefix) for prefix in SYSTEM_OBJECT_PREFIXES):
            return None
        object_type = sim.getObjectType(handle)
        try:
            is_model = (sim.getModelProperty(handle) & sim.modelproperty_not_model) == 0
        except Exception:
            is_model = False
        node = {
            "name": alias,
            "path": sim.getObjectAlias(handle, 1),
            "handle": handle,
            "type": object_type_names.get(object_type, f"unknown:{object_type}"),
            "is_model": is_model,
            "pos": [round(value, 2) for value in sim.getObjectPosition(handle, -1)],
            "children": []
        }
        node["children"] = sorted(
            (child for child_handle in children_by_parent.get(handle, [])
             if (child := build_node(child_handle)) is not None),
            key=lambda child: child["path"]
        )
        object_count += 1
        return node

    roots = [
        node for handle in children_by_parent.get(-1, [])
        if (node := build_node(handle)) is not None
    ]
    roots.sort(key=lambda node: node["path"])
    log("info", "simulator.scene_hierarchy_read", object_count=object_count, root_count=len(roots))
    return roots



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


def evaluate_scene_diagnostics(sim, checks: list[dict], floor: dict | None = None) -> list[dict]:
    """Evaluate caller-selected collision, distance, and floor checks."""
    floor = floor or get_floor_info(sim)
    results = []
    for check in checks:
        kind = check.get("kind") if isinstance(check, dict) else None
        objects = check.get("objects", [check.get("object")]) if isinstance(check, dict) else []
        item = {"kind": kind, "objects": objects, "status": "unavailable"}
        try:
            if not isinstance(check, dict):
                raise ValueError("Each diagnostic must be an object")
            if kind not in ("collision", "distance", "floor_bounds"):
                raise ValueError(f"Unsupported diagnostic kind: {kind}")
            required = 1 if kind == "floor_bounds" else 2
            if not isinstance(objects, list) or len(objects) != required or any(not isinstance(name, str) or not name for name in objects):
                raise ValueError(f"{kind} requires {required} object name(s)")
            handles = [sim.getObject(name, {"noError": True}) for name in objects]
            if any(handle == -1 for handle in handles):
                raise ValueError(f"Object not found: {objects}")
            if kind == "collision":
                collided = sim.checkCollision(*handles)[0]
                item.update(status="issue" if collided else "clear", collision=bool(collided))
            elif kind == "distance":
                threshold = check["threshold"]
                if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold < 0:
                    raise ValueError("distance threshold must be a finite non-negative number")
                result, distance_data, _ = sim.checkDistance(*handles)
                if not result or not isinstance(distance_data, (tuple, list)) or len(distance_data) < 7:
                    raise ValueError("Distance API did not return a measurement")
                distance = float(distance_data[6])
                closest_points = [distance_data[:3], distance_data[3:6]]
                item.update(
                    status="issue" if distance <= threshold else "clear",
                    distance=distance,
                    threshold=threshold,
                    closest_points=closest_points
                )
            else:
                if not floor.get("exists", True):
                    raise ValueError("Floor not found")
                matrix = sim.getObjectMatrix(handles[0], -1)
                bounds = {
                    axis: (
                        sim.getObjectFloatParam(handles[0], getattr(sim, f"objfloatparam_objbbox_min_{axis}")),
                        sim.getObjectFloatParam(handles[0], getattr(sim, f"objfloatparam_objbbox_max_{axis}"))
                    )
                    for axis in "xyz"
                }
                corners = [
                    [
                        matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
                        matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7]
                    ]
                    for x in bounds["x"]
                    for y in bounds["y"]
                    for z in bounds["z"]
                ]
                x_bounds, y_bounds = floor["bounds_x"], floor["bounds_y"]
                inside = all(x_bounds[0] <= point[0] <= x_bounds[1] and y_bounds[0] <= point[1] <= y_bounds[1] for point in corners)
                item.update(status="clear" if inside else "issue", bounds_x=x_bounds, bounds_y=y_bounds)
        except Exception as error:
            item["error"] = str(error)
        results.append(item)
    return results


def _raise_execution_timeout(_signum, _frame):
    raise TimeoutError("coppelia_step execution timed out")


def run_code(code: str, host: str = "localhost", port: int = 23000, take_snapshot: bool = True, reset: bool = False, auto_launch: bool = False, headless: bool = False, diagnostics: list[dict] | None = None, timeout: float = 30.0):
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")
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
        try:
            simIK = client.require("simIK")
        except Exception:
            simIK = None
        try:
            simOMPL = client.require("simOMPL")
        except Exception:
            simOMPL = None
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
    from motion_tools import plan_joint_path, solve_ik

    env = {
        "client": client,
        "sim": sim,
        "simIK": simIK,
        "simOMPL": simOMPL,
        "solve_ik": lambda **kwargs: solve_ik(sim, simIK, **kwargs),
        "plan_joint_path": lambda **kwargs: plan_joint_path(sim, simOMPL, **kwargs),
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
    log("info", "simulator.script_started", timeout=timeout)
    timer_started = time.monotonic()
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    old_handler = signal.signal(signal.SIGALRM, _raise_execution_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                exec(code, env)
                exec_success = True
            except Exception as e:
                exec_error = str(e)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, max(0.001, old_timer[0] - (time.monotonic() - timer_started)), old_timer[1])
        if exec_error and "timed out" in exec_error:
            log("error", "simulator.script_timed_out", timeout=timeout)

    if exec_success:
        auto_frame_gui_camera(sim)

    snapshot_file = None
    topdown_file = None
    if take_snapshot and exec_success:
        try:
            snapshot_file, topdown_file = capture_all_snapshots(sim)
        except Exception as snap_err:
            stderr_buf.write(f"\n[Warning: Snapshot capture failed: {snap_err}]")

    floor_data = None
    try:
        floor_data = get_floor_info(sim)
    except Exception:
        pass
    scene_hierarchy = []
    scene_hierarchy_error = None
    try:
        scene_hierarchy = get_scene_hierarchy(sim)
    except Exception as error:
        scene_hierarchy_error = str(error)
        log("error", "simulator.scene_hierarchy_failed", error=scene_hierarchy_error)

    log("success" if exec_success else "error", "simulator.script_finished", success=exec_success)
    return {
        "success": exec_success,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "error": exec_error,
        "snapshot_path": snapshot_file,
        "topdown_path": topdown_file,
        "diagnostics": evaluate_scene_diagnostics(sim, diagnostics, floor_data) if diagnostics and exec_success else [],
        "floor": floor_data,
        "scene_objects": scene_hierarchy,
        "scene_hierarchy_error": scene_hierarchy_error
    }


def main():
    parser = argparse.ArgumentParser(description="Execute Python scripts against CoppeliaSim")
    parser.add_argument("--code", type=str, help="Python code string to execute")
    parser.add_argument("--file", type=str, help="Path to Python script file to execute")
    parser.add_argument("--host", type=str, default="localhost", help="CoppeliaSim ZMQ host")
    parser.add_argument("--port", type=int, default=23000, help="CoppeliaSim ZMQ port")
    parser.add_argument("--timeout", type=float, default=30.0, help="Maximum user script execution time in seconds")
    parser.add_argument("--diagnostics", type=json.loads, help="JSON list of opt-in scene diagnostics")
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
        headless=args.launch_headless,
        diagnostics=args.diagnostics,
        timeout=args.timeout
    )

    print(json.dumps(result, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
