"""Summarize a robot subtree for safe motion-tool setup."""

from json_log import log

JOINT_TYPES = (("joint_revolute", "revolute"), ("joint_prismatic", "prismatic"), ("joint_spherical", "spherical"))
SENSOR_TYPES = (
    ("sceneobject_visionsensor", "vision"),
    ("sceneobject_forcesensor", "force_torque"),
    ("sceneobject_proximitysensor", "proximity"),
    ("sceneobject_pointcloud", "point_cloud"),
)


def inspect_mechanism(sim, root_path):
    if not isinstance(root_path, str) or not root_path.startswith("/"):
        raise ValueError("root_path must be an absolute CoppeliaSim object path")
    root = sim.getObject(root_path, {"noError": True})
    if root == -1:
        raise ValueError(f"Object not found: {root_path}")

    handles = sim.getObjectsInTree(root, sim.handle_all, 0)
    parents = {handle: sim.getObjectParent(handle) for handle in handles}
    joint_types = {
        getattr(sim, name): description
        for name, description in JOINT_TYPES
        if hasattr(sim, name)
    }
    sensor_types = {
        getattr(sim, name): description
        for name, description in SENSOR_TYPES
        if hasattr(sim, name)
    }
    joints, sensors = [], []
    for handle in handles:
        object_type = sim.getObjectType(handle)
        path = sim.getObjectAlias(handle, 1)
        if object_type == sim.sceneobject_joint:
            joint_type = sim.getJointType(handle)
            spherical = joint_type == getattr(sim, "joint_spherical", None)
            if spherical:
                joint_details = {
                    "cyclic": None,
                    "limits": None,
                    "position": None,
                    "target_position": None,
                    "unit": "quaternion",
                    "orientation_quaternion": sim.getObjectQuaternion(handle, -1),
                }
            else:
                cyclic, interval = sim.getJointInterval(handle)
                try:
                    target = sim.getJointTargetPosition(handle)
                except Exception:
                    target = None
                joint_details = {
                    "cyclic": bool(cyclic),
                    "limits": [interval[0], interval[0] + interval[1]],
                    "position": sim.getJointPosition(handle),
                    "target_position": target,
                    "unit": "rad" if joint_type == getattr(sim, "joint_revolute", None) else "m",
                }
            joints.append({
                "path": path,
                "type": joint_types.get(joint_type, f"unknown:{joint_type}"),
                **joint_details,
            })
        elif object_type in sensor_types:
            sensors.append({"path": path, "type": sensor_types[object_type]})

    child_handles = set(parents.values())
    leaves = sorted(
        sim.getObjectAlias(handle, 1)
        for handle in handles
        if handle not in child_handles and handle != root and sim.getObjectType(handle) in (sim.sceneobject_shape, sim.sceneobject_dummy)
    )
    result = {
        "success": True,
        "root": {"path": sim.getObjectAlias(root, 1), "position": sim.getObjectPosition(root, -1)},
        "base_candidate": sim.getObjectAlias(root, 1),
        "end_effector_candidates": leaves,
        "joints": sorted(joints, key=lambda item: item["path"]),
        "sensors": sorted(sensors, key=lambda item: item["path"]),
    }
    log("success", "mechanism.inspected", root=result["root"]["path"], joints=len(joints), sensors=len(sensors), end_effector_candidates=len(leaves))
    return result
