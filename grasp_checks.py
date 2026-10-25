"""Dynamic contact, relative slip, and post-lift checks in simulation units."""

import math

from json_log import log


def measure_contact(sim, object_handle, gripper_handles, minimum):
    strongest = 0.0
    count = 0
    for shape in gripper_handles:
        for index in range(10000):
            objects, _point, force, normal = sim.getContactInfo(sim.handle_all, shape, index)
            if not objects:
                break
            if object_handle in objects:
                value = abs(sum(component * axis for component, axis in zip(force, normal)))
                if not math.isfinite(value):
                    raise RuntimeError("Non-finite dynamic contact force")
                strongest = max(strongest, value)
                count += 1
        else:
            raise RuntimeError("Contact enumeration exceeded 10000 entries per gripper shape")
    return {"normal_force": strongest, "min_normal_force": minimum, "contact_count": count,
            "success": count > 0 and strongest >= minimum}


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


def prepare_grasp(sim, check, waypoint, length, resolve):
    if not isinstance(check, dict):
        raise ValueError("grasp must be an object")
    for key in ("min_normal_force", "min_lift", "max_slip", "max_rotation_rad"):
        _positive(check.get(key), f"grasp.{key}")
    end = check.get("hold_until_waypoint")
    if isinstance(end, bool) or not isinstance(end, int) or not waypoint < end < length:
        raise ValueError("grasp.hold_until_waypoint must be after grasp and inside the trajectory")
    hold_steps = check.get("hold_steps", 10)
    if isinstance(hold_steps, bool) or not isinstance(hold_steps, int) or not 1 <= hold_steps <= 1000:
        raise ValueError("grasp.hold_steps must be an integer between 1 and 1000")
    sweep = check.get("wrench_sweep")
    if not isinstance(sweep, dict):
        raise ValueError("grasp.wrench_sweep must specify bounded force and torque tests")
    force = _positive(sweep.get("force_n"), "grasp.wrench_sweep.force_n")
    torque = _positive(sweep.get("torque_nm"), "grasp.wrench_sweep.torque_nm")
    sweep_steps = sweep.get("steps_per_direction", 2)
    if isinstance(sweep_steps, bool) or not isinstance(sweep_steps, int) or not 1 <= sweep_steps <= 1000:
        raise ValueError("grasp.wrench_sweep.steps_per_direction must be an integer between 1 and 1000")
    obj = resolve(sim, check.get("object"))
    root = resolve(sim, check.get("gripper"))
    if sim.getObjectType(obj) != sim.sceneobject_shape:
        raise ValueError("grasp.object must identify the dynamic shape being held")
    shapes = sim.getObjectsInTree(root, sim.sceneobject_shape, 0)
    if not shapes or obj in shapes:
        raise ValueError("gripper must contain shapes and must not contain grasp.object")
    return {"object": obj, "root": root, "shapes": shapes, "minimum": float(check["min_normal_force"]),
            "min_lift": float(check["min_lift"]), "max_slip": float(check["max_slip"]),
            "max_rotation_rad": float(check["max_rotation_rad"]), "wrench_sweep": {
                "force_n": force, "torque_nm": torque, "steps_per_direction": sweep_steps},
            "end": end, "hold_steps": hold_steps}


def _rotation_delta(first, second):
    if len(first) != 4 or len(second) != 4:
        raise RuntimeError("Object quaternion must contain four components")
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if not math.isfinite(first_norm) or not math.isfinite(second_norm) or first_norm == 0 or second_norm == 0:
        raise RuntimeError("Object quaternion must be finite and nonzero")
    dot = abs(sum(a * b for a, b in zip(first, second)) / (first_norm * second_norm))
    return 2 * math.acos(min(1.0, dot))


def acquire_grasp(sim, check, waypoint):
    result = measure_contact(sim, check["object"], check["shapes"], check["minimum"])
    if not result["success"]:
        raise RuntimeError(f"Grasp contact check failed at waypoint {waypoint}")
    held = {**check, "start": waypoint,
            "relative": sim.getObjectPosition(check["object"], check["root"]),
            "orientation": sim.getObjectQuaternion(check["object"], check["root"]),
            "initial_z": sim.getObjectPosition(check["object"], -1)[2], "result": result,
            "max_observed_slip": 0.0, "max_observed_rotation": 0.0}
    result.update({"hold_until_waypoint": check["end"], "hold_verified": False,
                   "max_slip": check["max_slip"], "max_rotation_rad": check["max_rotation_rad"],
                   "min_lift": check["min_lift"], "hold_steps": check["hold_steps"]})
    log("info", "trajectory.grasp_acquired", waypoint=waypoint, **result)
    return held


def check_hold(sim, held, waypoint, final=False):
    result = measure_contact(sim, held["object"], held["shapes"], held["minimum"])
    relative = sim.getObjectPosition(held["object"], held["root"])
    slip = math.dist(relative, held["relative"])
    rotation = _rotation_delta(held["orientation"], sim.getObjectQuaternion(held["object"], held["root"]))
    lift = sim.getObjectPosition(held["object"], -1)[2] - held["initial_z"]
    if not result["success"] or not math.isfinite(slip) or slip > held["max_slip"]:
        raise RuntimeError(f"Grasp contact lost or slip exceeded at waypoint {waypoint}: slip={slip}")
    if not math.isfinite(rotation) or rotation > held["max_rotation_rad"]:
        raise RuntimeError(f"Grasp rotational slip exceeded at waypoint {waypoint}: rotation={rotation}")
    held["max_observed_slip"] = max(held["max_observed_slip"], slip)
    held["max_observed_rotation"] = max(held["max_observed_rotation"], rotation)
    if final:
        if not math.isfinite(lift) or lift < held["min_lift"]:
            raise RuntimeError(f"Grasp lift check failed at waypoint {waypoint}: lift={lift}")
        held["result"].update({"hold_verified": True, "lift": lift, "slip": slip,
                               "rotation_slip_rad": rotation,
                               "max_observed_slip": held["max_observed_slip"],
                               "max_observed_rotation_slip_rad": held["max_observed_rotation"],
                               "final_normal_force": result["normal_force"]})
        log("success", "trajectory.grasp_hold_verified", waypoint=waypoint, lift=lift,
            slip=slip, rotation_slip_rad=rotation)
    return {"normal_force": result["normal_force"], "slip": slip, "rotation_slip_rad": rotation}


def run_wrench_sweep(sim, held, waypoint, check_collisions):
    sweep = held["wrench_sweep"]
    checks = []
    for kind, amplitude in (("force", sweep["force_n"]), ("torque", sweep["torque_nm"])):
        for axis in range(3):
            for sign in (-1, 1):
                vector = [0.0, 0.0, 0.0]
                vector[axis] = sign * amplitude
                force, torque = (vector, [0.0, 0.0, 0.0]) if kind == "force" else ([0.0, 0.0, 0.0], vector)
                maximum = {"slip": 0.0, "rotation_slip_rad": 0.0}
                for _ in range(sweep["steps_per_direction"]):
                    sim.addForceAndTorque(held["object"], force, torque)
                    sim.step()
                    check_collisions()
                    observed = check_hold(sim, held, waypoint)
                    for key in maximum:
                        maximum[key] = max(maximum[key], observed[key])
                checks.append({"kind": kind, "axis": axis, "sign": sign, **maximum})
    result = {"method": "six-axis force and torque perturbation sweep",
              "force_n": sweep["force_n"], "torque_nm": sweep["torque_nm"],
              "steps_per_direction": sweep["steps_per_direction"],
              "direction_count": len(checks), "directions": checks,
              "passed": True, "analytic_force_closure_proven": False}
    held["result"]["wrench_resistance_test"] = result
    log("success", "trajectory.grasp_wrench_sweep_passed",
        force_n=sweep["force_n"], torque_nm=sweep["torque_nm"], direction_count=len(checks))
    return len(checks) * sweep["steps_per_direction"]


