#!/usr/bin/env python3
"""CoppeliaSim CLI Runner for omp agents.

Executes Python scripts against the simulator's ZeroMQ Remote API
and automatically captures observer camera snapshots.
"""
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    _repo_dir = Path(__file__).resolve().parent.parent
    if str(_repo_dir) not in sys.path:
        sys.path.insert(0, str(_repo_dir))
    __package__ = "coppeliasim_mcp"

import io
import math
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import signal
import time
from .json_log import log

from .sim_connection import CLIENT_SRC, COPPELIA_ROOT
try:
    from .sim_connection import RemoteAPIClient
except ImportError:
    pass
from .observation_tools import (
    CALIBRATED_CAM_POS,
    CALIBRATED_CAM_ROT,
    CALIBRATED_FOV_DEG,
    OBSERVER_CAM_NAME,
    SNAPSHOT_PATH,
    TOPDOWN_CAM_NAME,
    TOPDOWN_CAM_POS,
    TOPDOWN_CAM_ROT,
    TOPDOWN_FOV_DEG,
    TOPDOWN_SNAPSHOT_PATH,
)
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
    from .scene_catalog import resolve_model_path as _resolve_model_path

    return _resolve_model_path(name)

def is_coppelia_running(host: str = "localhost", port: int = 23000) -> bool:
    """Check if CoppeliaSim ZeroMQ server is responsive."""
    from .sim_connection import is_coppelia_running as _is_coppelia_running

    return _is_coppelia_running(host, port)

def launch_coppelia(headless: bool = False, timeout: int = 25):
    """Launch CoppeliaSim application if not currently running."""
    from .sim_connection import launch_coppelia as _launch_coppelia

    return _launch_coppelia(headless=headless, timeout=timeout)


def ensure_camera(sim, name: str, pos: list, rot: list, fov_deg: float):
    """Ensure a calibrated vision sensor exists in the scene."""
    from .observation_tools import ensure_camera as _ensure_camera

    return _ensure_camera(sim, name, pos, rot, fov_deg)


def ensure_observer_camera(sim):
    """Ensure floating isometric perspective camera exists."""
    from .observation_tools import ensure_observer_camera as _ensure_observer_camera

    return _ensure_observer_camera(sim)


def ensure_topdown_camera(sim):
    """Ensure bird's-eye top-down camera exists directly above board looking down."""
    from .observation_tools import ensure_topdown_camera as _ensure_topdown_camera

    return _ensure_topdown_camera(sim)

def auto_frame_gui_camera(sim):
    """Auto-frame GUI DefaultCamera to Bird's-Eye Top-Down view directly above board.
    Positions GUI DefaultCamera looking straight down at the entire board without clipping.
    """
    from .observation_tools import auto_frame_gui_camera as _auto_frame_gui_camera

    return _auto_frame_gui_camera(sim)


def get_floor_info(sim) -> dict:
    """Detect default scene floor size, bounds, and position."""
    from .scene_inspection import get_floor_info as _get_floor_info

    return _get_floor_info(sim)


from .scene_inspection import (
    SCENE_OBJECT_TYPE_NAMES,
    SYSTEM_OBJECT_PREFIXES,
)


def get_scene_hierarchy(sim) -> list:
    """Return visible scene roots with recursively nested user objects."""
    from .scene_inspection import get_scene_hierarchy as _get_scene_hierarchy

    return _get_scene_hierarchy(sim)


def capture_snapshot(sim, output_path: Path = SNAPSHOT_PATH, cam_type: str = "isometric") -> str:
    """Capture RGB frame from specified camera and save cleanly to disk."""
    from .observation_tools import capture_snapshot as _capture_snapshot

    return _capture_snapshot(sim, output_path=output_path, cam_type=cam_type)


def capture_all_snapshots(sim):
    """Capture both isometric and top-down views."""
    from .observation_tools import capture_all_snapshots as _capture_all_snapshots

    return _capture_all_snapshots(sim)

def make_load_robot_fn(sim):
    """Factory creating the load_robot helper injected into agent code."""
    from .scene_catalog import make_load_robot_fn as _make_load_robot_fn

    return _make_load_robot_fn(sim)


def evaluate_scene_diagnostics(sim, checks: list[dict], floor: dict | None = None) -> list[dict]:
    """Evaluate caller-selected collision, distance, and floor checks."""
    from .scene_inspection import evaluate_scene_diagnostics as _evaluate_scene_diagnostics

    return _evaluate_scene_diagnostics(sim, checks, floor=floor)


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
    from .motion_tools import plan_joint_path, solve_ik

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


def main(*args, **kwargs):
    """Execute CoppeliaSim runner CLI."""
    from .runner_cli import main as _main

    return _main(*args, **kwargs)

if __name__ == "__main__":
    main()
