from pathlib import Path

SNAPSHOT_PATH = Path("/tmp/coppelia_snapshot.png")
TOPDOWN_SNAPSHOT_PATH = Path("/tmp/coppelia_topdown.png")

# Calibrated isometric camera (diagonal perspective view):
OBSERVER_CAM_NAME = "Agent_Observer_Cam"
CALIBRATED_CAM_POS = [9.0, -9.0, 7.5]
CALIBRATED_CAM_ROT = [-2.1588, -0.6940, 2.7385]
CALIBRATED_FOV_DEG = 65.0

# Calibrated top-down camera (bird's-eye view looking straight down at simulation board):
TOPDOWN_CAM_NAME = "Agent_TopDown_Cam"
TOPDOWN_CAM_POS = [0.0, 0.0, 20.0]
TOPDOWN_CAM_ROT = [3.14159, 0.0, 0.0]
TOPDOWN_FOV_DEG = 90.0


def ensure_camera(sim, name: str, pos: list, rot: list, fov_deg: float):
    """Ensure a calibrated vision sensor exists in the scene."""
    cam_handle = sim.getObject(f"/{name}", {"noError": True})
    if cam_handle == -1:
        int_params = [1024, 768, 0, 0]  # 1024x768 resolution
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
    return ensure_camera(
        sim,
        OBSERVER_CAM_NAME,
        CALIBRATED_CAM_POS,
        CALIBRATED_CAM_ROT,
        CALIBRATED_FOV_DEG,
    )


def ensure_topdown_camera(sim):
    """Ensure bird's-eye top-down camera exists directly above board looking down."""
    return ensure_camera(
        sim,
        TOPDOWN_CAM_NAME,
        TOPDOWN_CAM_POS,
        TOPDOWN_CAM_ROT,
        TOPDOWN_FOV_DEG,
    )


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
