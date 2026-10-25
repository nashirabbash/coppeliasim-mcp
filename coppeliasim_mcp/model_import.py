"""Import structured robot models and report their new scene roots."""

from math import isfinite
from pathlib import Path

from .json_log import log

MODEL_IMPORTERS = {".urdf": "urdf", ".sdf": "sdf", ".stl": "mesh", ".obj": "mesh", ".dae": "mesh"}


def _vector(values, name):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError(f"{name} must contain three finite numbers")
    result = [float(value) for value in values]
    if not all(isfinite(value) for value in result):
        raise ValueError(f"{name} must contain three finite numbers")
    return result


def _root_handles(sim):
    return set(sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 2))


def _describe_roots(sim, handles):
    models = []
    for handle in handles:
        objects = sim.getObjectsInTree(handle, sim.handle_all, 0)
        joints = sim.getObjectsInTree(handle, sim.sceneobject_joint, 0)
        models.append({"handle": handle, "name": sim.getObjectAlias(handle), "object_count": len(objects), "joint_count": len(joints)})
    return models


def import_model(sim, client, path, position=None, orientation=None, scale=1.0, package_root=None):
    source = Path(path).expanduser().resolve()
    importer = MODEL_IMPORTERS.get(source.suffix.lower())
    if not importer or not source.is_file():
        raise ValueError(f"Model file must exist and use one of: {', '.join(MODEL_IMPORTERS)}")
    if not isinstance(scale, (int, float)) or not isfinite(scale) or scale <= 0:
        raise ValueError("scale must be a finite positive number")
    pos = _vector(position, "position") if position is not None else None
    rot = _vector(orientation, "orientation") if orientation is not None else None
    roots_before = _root_handles(sim)
    log("info", "model.import_started", path=str(source), format=importer)
    if importer == "urdf":
        name = client.require("simURDF").importFile(str(source), 0, package_root)
    elif importer == "sdf":
        getattr(client.require("simSDF"), "import")(str(source), {})
        name = None
    else:
        handle = sim.importShape(0, str(source), 0, 0, scale)
        name = sim.getObjectAlias(handle)
    new_roots = sorted(_root_handles(sim) - roots_before)
    if not new_roots:
        raise RuntimeError("Import completed but created no new scene root objects")
    if pos is not None or rot is not None:
        for handle in new_roots:
            if pos is not None:
                sim.setObjectPosition(handle, -1, pos)
            if rot is not None:
                sim.setObjectOrientation(handle, -1, rot)
    models = _describe_roots(sim, new_roots)
    log("success", "model.import_completed", path=str(source), model_count=len(models), name=name)
    return {"success": True, "path": str(source), "format": importer, "imported_name": name, "models": models}


def ros2_status(client):
    try:
        client.require("simROS2")
    except Exception as error:
        log("error", "ros2.plugin_unavailable", error=str(error))
        return {"available": False, "error": str(error), "required": "Source a compatible ROS 2 environment before launching CoppeliaSim."}
    log("success", "ros2.plugin_available")
    return {"available": True}
