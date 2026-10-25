"""Validated joint-trajectory execution with collision and manipulation checks."""

import math

from json_log import log
from grasp_checks import acquire_grasp, check_hold, prepare_grasp, run_wrench_sweep


def _resolve(sim, path: str) -> int:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Object paths must be absolute CoppeliaSim paths")
    handle = sim.getObject(path, {"noError": True})
    if handle == -1:
        raise ValueError(f"Object not found: {path}")
    return handle


def _validate_trajectory(joints, trajectory, max_velocity, steps_per_waypoint, max_acceleration=None, max_jerk=None):
    if not isinstance(joints, list) or not joints or any(not isinstance(path, str) or not path.startswith("/") for path in joints):
        raise ValueError("joints must contain absolute object paths")
    if len(set(joints)) != len(joints):
        raise ValueError("joints must contain unique absolute object paths")
    if not isinstance(trajectory, list) or not trajectory:
        raise ValueError("trajectory must be a non-empty list of joint states")
    if any(not isinstance(state, list) or len(state) != len(joints) for state in trajectory):
        raise ValueError("each trajectory state must match the joint count")
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for state in trajectory for value in state):
        raise ValueError("trajectory values must be finite numbers")
    if not isinstance(max_velocity, list) or len(max_velocity) != len(joints) or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in max_velocity):
        raise ValueError("max_velocity must contain one finite positive limit per joint")
    if not isinstance(steps_per_waypoint, int) or steps_per_waypoint < 1:
        raise ValueError("steps_per_waypoint must be a positive integer")
    if max_acceleration is not None and (not isinstance(max_acceleration, list) or len(max_acceleration) != len(joints) or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in max_acceleration)):
        raise ValueError("max_acceleration must contain one finite positive limit per joint")
    if max_jerk is not None and (not isinstance(max_jerk, list) or len(max_jerk) != len(joints) or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in max_jerk)):
        raise ValueError("max_jerk must contain one finite positive limit per joint")


def smooth_ratio(step: int, total_steps: int) -> float:
    tau = step / total_steps
    return 35.0 * (tau ** 4) - 84.0 * (tau ** 5) + 70.0 * (tau ** 6) - 20.0 * (tau ** 7)


def compute_profile_extrema(delta: float, steps: int, timestep: float):
    if delta == 0:
        return 0.0, 0.0, 0.0
    pts = [delta * smooth_ratio(k, steps) for k in range(steps + 1)]
    vels = [(pts[k] - pts[k - 1]) / timestep for k in range(1, steps + 1)]
    vel_seq = [0.0] + vels + [0.0]
    accs = [(vel_seq[k] - vel_seq[k - 1]) / timestep for k in range(1, len(vel_seq))]
    acc_seq = [0.0] + accs + [0.0]
    jerks = [(acc_seq[k] - acc_seq[k - 1]) / timestep for k in range(1, len(acc_seq))]
    return max(abs(v) for v in vels), max(abs(a) for a in accs), max(abs(j) for j in jerks)

def _check_limits(sim, handles, positions):
    for handle, position in zip(handles, positions):
        cyclic, interval = sim.getJointInterval(handle)
        low, span = interval
        if not cyclic and not low <= position <= low + span:
            raise ValueError(f"Joint target {position} exceeds limits [{low}, {low + span}]")
        if cyclic and not low <= position <= low + span:
            raise ValueError(f"Cyclic joint target {position} exceeds configured interval [{low}, {low + span}]")

def _check_collisions(sim, collision_pairs):
    for first, second, paths in collision_pairs:
        if sim.checkCollision(first, second)[0]:
            log("error", "trajectory.collision_detected", objects=paths)
            sim.stopSimulation()
            raise RuntimeError(f"Collision detected between {paths[0]} and {paths[1]}")

def _measure_distance(sim, first, second, threshold, kind):
    measured, data, _ = sim.checkDistance(first, second)
    if not measured or not isinstance(data, (list, tuple)) or len(data) < 7:
        raise RuntimeError(f"{kind} distance measurement unavailable")
    distance = float(data[6])
    return {"distance": distance, "max_distance": threshold, "success": distance <= threshold}


def _prepare_actions(sim, actions, trajectory_length):
    if not isinstance(actions, list):
        raise ValueError("gripper_actions must be a list")
    prepared = []
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Each gripper action must be an object")
        waypoint = action.get("waypoint")
        if not isinstance(waypoint, int) or not 0 <= waypoint < trajectory_length:
            raise ValueError("gripper action waypoint is outside the trajectory")
        joint = action.get("joint")
        position = action.get("position")
        if not isinstance(position, (int, float)) or not math.isfinite(position):
            raise ValueError("gripper action position must be finite")
        settle_steps = action.get("settle_steps", 1)
        if not isinstance(settle_steps, int) or settle_steps < 1:
            raise ValueError("gripper action settle_steps must be a positive integer")
        joint_handle = _resolve(sim, joint)
        _check_limits(sim, [joint_handle], [position])
        checks = {}
        if "grasp" in action:
            checks["grasp"] = prepare_grasp(sim, action["grasp"], waypoint, trajectory_length, _resolve)
        if "place" in action:
            check = action["place"]
            if not isinstance(check, dict) or not isinstance(check.get("object"), str) or not isinstance(check.get("target"), str):
                raise ValueError("place check requires object and target paths")
            threshold = check.get("max_distance")
            if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold < 0:
                raise ValueError("place.max_distance must be finite and non-negative")
            checks["place"] = (_resolve(sim, check["object"]), _resolve(sim, check["target"]), float(threshold))
        prepared.append((waypoint, joint_handle, float(position), settle_steps, checks))
    return prepared


def execute_trajectory(sim, joints, trajectory, collision_pairs=None, max_velocity=None, steps_per_waypoint=10, gripper_actions=None, max_acceleration=None, max_jerk=None):
    if not isinstance(collision_pairs, list) or not collision_pairs:
        raise ValueError("collision_pairs must contain at least one monitored object pair")
    if max_velocity is None:
        max_velocity = []
    if gripper_actions is None:
        gripper_actions = []
    _validate_trajectory(joints, trajectory, max_velocity, steps_per_waypoint, max_acceleration, max_jerk)
    joint_handles = [_resolve(sim, path) for path in joints]
    resolved_pairs = []
    for pair in collision_pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("collision_pairs must contain two-object path pairs")
        resolved_pairs.append((_resolve(sim, pair[0]), _resolve(sim, pair[1]), pair))
    prepared_actions = _prepare_actions(sim, gripper_actions, len(trajectory))
    timestep = sim.getSimulationTimeStep()
    if not math.isfinite(timestep) or timestep <= 0:
        raise ValueError("Simulator timestep must be finite and positive")
    current = [sim.getJointPosition(handle) for handle in joint_handles]
    _check_limits(sim, joint_handles, current)
    for state in trajectory:
        _check_limits(sim, joint_handles, state)
    is_smooth = max_acceleration is not None or max_jerk is not None
    for target in trajectory:
        for index, _ in enumerate(joint_handles):
            delta = target[index] - current[index]
            if is_smooth:
                vel, acc, jerk = compute_profile_extrema(delta, steps_per_waypoint, timestep)
                if vel > max_velocity[index]:
                    raise ValueError(f"Joint {joints[index]} requested velocity {vel} exceeds limit {max_velocity[index]}")
                if max_acceleration is not None and acc > max_acceleration[index]:
                    raise ValueError(f"Joint {joints[index]} requested acceleration {acc} exceeds limit {max_acceleration[index]}")
                if max_jerk is not None and jerk > max_jerk[index]:
                    raise ValueError(f"Joint {joints[index]} requested jerk {jerk} exceeds limit {max_jerk[index]}")
            else:
                velocity = abs(delta) / (steps_per_waypoint * timestep)
                if velocity > max_velocity[index]:
                    raise ValueError(f"Joint {joints[index]} requested velocity {velocity} exceeds limit {max_velocity[index]}")
        current = target
    current = [sim.getJointPosition(handle) for handle in joint_handles]
    completed_steps = 0
    action_results = []
    held_grasps = []
    was_stopped = sim.getSimulationState() == sim.simulation_stopped
    sim.setStepping(True)
    try:
        if was_stopped:
            sim.startSimulation()
        for waypoint, target in enumerate(trajectory):
            for step in range(1, steps_per_waypoint + 1):
                ratio = smooth_ratio(step, steps_per_waypoint) if is_smooth else (step / steps_per_waypoint)
                for index, handle in enumerate(joint_handles):
                    sim.setJointTargetPosition(handle, current[index] + (target[index] - current[index]) * ratio)
                sim.step()
                completed_steps += 1
                _check_collisions(sim, resolved_pairs)
                for held in held_grasps:
                    if held["start"] < waypoint <= held["end"]:
                        check_hold(sim, held, waypoint)
            current = target
            for held in held_grasps:
                if waypoint == held["end"]:
                    for _ in range(held["hold_steps"]):
                        sim.step()
                        completed_steps += 1
                        _check_collisions(sim, resolved_pairs)
                        for active in held_grasps:
                            if active["start"] < waypoint <= active["end"]:
                                check_hold(sim, active, waypoint)
                    completed_steps += run_wrench_sweep(
                        sim, held, waypoint, lambda: _check_collisions(sim, resolved_pairs))
                    check_hold(sim, held, waypoint, final=True)
            for action in (item for item in prepared_actions if item[0] == waypoint):
                _, handle, position, settle_steps, checks = action
                sim.setJointTargetPosition(handle, position)
                for _ in range(settle_steps):
                    sim.step()
                    completed_steps += 1
                    _check_collisions(sim, resolved_pairs)
                    for held in held_grasps:
                        if held["start"] <= waypoint < held["end"]:
                            check_hold(sim, held, waypoint)
                result = {"waypoint": waypoint, "gripper_position": position}
                for kind, check in checks.items():
                    if kind == "grasp":
                        held = acquire_grasp(sim, check, waypoint)
                        held_grasps.append(held)
                        result[kind] = held["result"]
                    else:
                        result[kind] = _measure_distance(sim, *check, kind)
                        if not result[kind]["success"]:
                            raise RuntimeError(f"Place check failed at waypoint {waypoint}: distance {result[kind]['distance']} exceeds {check[2]}")
                action_results.append(result)
        final = [sim.getJointPosition(handle) for handle in joint_handles]
        log("success", "trajectory.completed", waypoints=len(trajectory), steps=completed_steps, gripper_actions=len(action_results))
        return {"waypoints": len(trajectory), "steps_run": completed_steps, "final_positions": final, "gripper_results": action_results}
    except Exception as error:
        log("error", "trajectory.stopped", error=str(error), steps=completed_steps)
        sim.stopSimulation()
        raise
    finally:
        sim.setStepping(False)


def run_trajectory(headless=False, **parameters):
    from sim_connection import connect_sim

    try:
        _, sim = connect_sim(headless=headless)
        log("info", "trajectory.started", waypoints=len(parameters.get("trajectory", [])))
        return {"success": True, **execute_trajectory(sim, **parameters)}
    except Exception as error:
        log("error", "trajectory.failed", error=str(error))
        return {"success": False, "error": str(error)}


