"""Typed inverse-kinematics and joint-space path-planning operations."""

import math

from json_log import log


def _resolve(sim, path: str) -> int:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Object paths must be absolute CoppeliaSim paths")
    handle = sim.getObject(path, {"noError": True})
    if handle == -1:
        raise ValueError(f"Object not found: {path}")
    return handle


def solve_ik(
    sim,
    sim_ik,
    base: str,
    tip: str,
    target: str,
    constraints: str = "pose",
    method: str = "damped_least_squares",
    damping: float = 0.02,
    iterations: int = 20,
) -> dict:
    if sim_ik is None:
        raise RuntimeError("simIK is unavailable in the active simulator")
    if constraints not in ("pose", "position", "orientation"):
        raise ValueError("constraints must be pose, position, or orientation")
    if method not in ("damped_least_squares", "pseudo_inverse"):
        raise ValueError("method must be damped_least_squares or pseudo_inverse")
    if not math.isfinite(damping) or damping < 0 or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("damping must be finite and non-negative; iterations must be positive")

    handles = [_resolve(sim, path) for path in (base, tip, target)]
    environment = sim_ik.createEnvironment()
    try:
        group = sim_ik.createGroup(environment)
        element, _, _ = sim_ik.addElementFromScene(
            environment, group, *handles, getattr(sim_ik, f"constraint_{constraints}")
        )
        solver_method = getattr(sim_ik, f"method_{method}")
        sim_ik.setGroupCalculation(environment, group, solver_method, damping, iterations)
        result, flags, _ = sim_ik.handleGroup(environment, group, {"syncWorlds": True})
        return {"solved": result == sim_ik.result_success, "flags": int(flags), "element": int(element)}
    finally:
        sim_ik.eraseEnvironment(environment)


def plan_joint_path(
    sim,
    sim_ompl,
    joints: list[str],
    goal: list[float],
    collision_pairs: list[list[str]],
    algorithm: str = "RRTConnect",
    max_time: float = 4.0,
    simplify_time: float = 0.5,
    path_states: int = 100,
) -> dict:
    if sim_ompl is None:
        raise RuntimeError("simOMPL is unavailable in the active simulator")
    if not joints or len(joints) != len(goal):
        raise ValueError("joints and goal must be non-empty lists of equal length")
    if any(not math.isfinite(value) for value in goal):
        raise ValueError("goal values must be finite")
    if not math.isfinite(max_time) or max_time <= 0 or not math.isfinite(simplify_time) or simplify_time < 0:
        raise ValueError("max_time must be positive and simplify_time non-negative")
    if not isinstance(path_states, int) or path_states < 2:
        raise ValueError("path_states must be an integer of at least 2")
    if not isinstance(collision_pairs, list) or any(not isinstance(pair, list) or len(pair) != 2 for pair in collision_pairs):
        raise ValueError("collision_pairs must contain two-object path pairs")

    joint_handles = [_resolve(sim, path) for path in joints]
    collision_handles = [_resolve(sim, path) for pair in collision_pairs for path in pair]
    state_spaces = []
    task = sim_ompl.createTask("mcp_joint_plan")
    try:
        for index, handle in enumerate(joint_handles):
            cyclic, interval = sim.getJointInterval(handle)
            low, span = interval
            if cyclic:
                low, span = -math.pi, 2 * math.pi
            state_spaces.append(sim_ompl.createStateSpace(
                f"joint_{index}", sim_ompl.StateSpaceType.joint_position,
                handle, [low], [low + span], index + 1 if index < 3 else 0
            ))
        sim_ompl.setStateSpace(task, state_spaces)
        sim_ompl.setAlgorithm(task, getattr(sim_ompl.Algorithm, algorithm))
        if collision_handles:
            sim_ompl.setCollisionPairs(task, collision_handles)
        start = [sim.getJointPosition(handle) for handle in joint_handles]
        sim_ompl.setStartState(task, start)
        sim_ompl.setGoalState(task, goal)
        sim_ompl.setup(task)
        solved = sim_ompl.solve(task, max_time)
        path = []
        if solved:
            if simplify_time:
                sim_ompl.simplifyPath(task, simplify_time)
            sim_ompl.interpolatePath(task, path_states)
            flat_path = sim_ompl.getPath(task)
            dimension = len(joint_handles)
            path = [flat_path[offset:offset + dimension] for offset in range(0, len(flat_path), dimension)]
        return {"solved": bool(solved), "start": start, "goal": goal, "path": path}
    finally:
        sim_ompl.destroyTask(task)
        for state_space in state_spaces:
            sim_ompl.destroyStateSpace(state_space)


def runtime_health(host: str, port: int) -> dict:
    from runner import RemoteAPIClient, is_coppelia_running

    reachable = is_coppelia_running(host, port)
    result = {"connected": False, "host": host, "port": port, "simIK": False, "simOMPL": False}
    if not reachable:
        result["error"] = "CoppeliaSim ZeroMQ API is not reachable"
        return result
    try:
        client = RemoteAPIClient(host=host, port=port)
        sim = client.require("sim")
        result["connected"] = True
        result["program_version"] = sim.getInt32Param(sim.intparam_program_version)
        for module in ("simIK", "simOMPL"):
            try:
                client.require(module)
                result[module] = True
            except Exception:
                result[module] = False
        log("success", "simulator.health_checked", host=host, port=port, capabilities=result)
    except Exception as error:
        result["error"] = str(error)
        log("error", "simulator.health_check_failed", host=host, port=port, error=str(error))
    return result

def run_motion(operation: str, headless: bool = False, **parameters) -> dict:
    from sim_connection import connect_sim

    try:
        client, sim = connect_sim(headless=headless)
        if operation == "ik":
            result = solve_ik(sim, client.require("simIK"), **parameters)
        elif operation == "plan":
            result = plan_joint_path(sim, client.require("simOMPL"), **parameters)
        else:
            raise ValueError("operation must be ik or plan")
        log("success", "simulator.motion_completed", operation=operation)
        return {"success": True, "operation": operation, **result}
    except Exception as error:
        log("error", "simulator.motion_failed", operation=operation, error=str(error))
        return {"success": False, "operation": operation, "error": str(error)}
