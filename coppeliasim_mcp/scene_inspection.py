import math

from .json_log import log


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
