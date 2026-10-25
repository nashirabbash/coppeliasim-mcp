#!/usr/bin/env python3
"""Root compatibility launcher for CoppeliaSim runner."""
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from coppeliasim_mcp import runner as _runner_mod
from coppeliasim_mcp.runner import (
    CALIBRATED_CAM_POS,
    CALIBRATED_CAM_ROT,
    CALIBRATED_FOV_DEG,
    CLIENT_SRC,
    COPPELIA_ROOT,
    OBSERVER_CAM_NAME,
    ROBOT_ALIASES,
    SCENE_OBJECT_TYPE_NAMES,
    SNAPSHOT_PATH,
    SYSTEM_OBJECT_PREFIXES,
    TOPDOWN_CAM_NAME,
    TOPDOWN_CAM_POS,
    TOPDOWN_CAM_ROT,
    TOPDOWN_FOV_DEG,
    TOPDOWN_SNAPSHOT_PATH,
    auto_frame_gui_camera,
    capture_all_snapshots,
    capture_snapshot,
    ensure_camera,
    ensure_observer_camera,
    ensure_topdown_camera,
    evaluate_scene_diagnostics,
    get_floor_info,
    get_scene_hierarchy,
    is_coppelia_running,
    launch_coppelia,
    main,
    make_load_robot_fn,
    resolve_model_path,
    run_code,
)

try:
    from coppeliasim_mcp.runner import RemoteAPIClient
except ImportError:
    pass

if __name__ == "__main__":
    main()
