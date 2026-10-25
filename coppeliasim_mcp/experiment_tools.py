"""Run bounded batches of simulation episodes and compare outcomes."""

import math
from pathlib import Path
import time

from .json_log import log
from .runner import get_floor_info
from .sim_connection import connect_sim
from .sim_run import MAX_STEPS, condition_met, resolve_handles, take_sample

MAX_EPISODES = 20
STOP_TIMEOUT_S = 5.0


def _is_finite_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_experiments(initial_scene, episodes, observe, sensors, sample_every):
    if not isinstance(initial_scene, str) or not initial_scene.startswith("/") or not initial_scene.endswith(".ttt"):
        raise ValueError("initial_scene must be an absolute .ttt path")
    if not Path(initial_scene).is_file():
        raise ValueError(f"Scene file not found: {initial_scene}")
    if not isinstance(episodes, list) or not 1 <= len(episodes) <= MAX_EPISODES:
        raise ValueError(f"episodes must contain between 1 and {MAX_EPISODES} entries")
    if not isinstance(sample_every, int) or isinstance(sample_every, bool) or sample_every < 1:
        raise ValueError("sample_every must be an integer of at least 1")
    if any(not isinstance(p, str) or not p.startswith("/") for p in observe):
        raise ValueError("observe must contain absolute object paths")
    if any(not isinstance(p, str) or not p.startswith("/") for p in sensors):
        raise ValueError("sensors must contain absolute object paths")

    total_steps = 0
    for index, episode in enumerate(episodes):
        if not isinstance(episode, dict):
            raise ValueError(f"episodes[{index}] must be an object")
        name = episode.get("name", f"episode-{index + 1}")
        if not isinstance(name, str) or not name:
            raise ValueError(f"episodes[{index}].name must be a non-empty string")
        steps = episode.get("steps", 100)
        if not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= MAX_STEPS:
            raise ValueError(f"episodes[{index}].steps must be an integer between 1 and {MAX_STEPS}")
        total_steps += steps
        positions = episode.get("joint_positions", {})
        if not isinstance(positions, dict) or any(not isinstance(p, str) or not p.startswith("/") for p in positions):
            raise ValueError(f"episodes[{index}].joint_positions must map absolute joint paths to positions")
        if any(not _is_finite_num(v) for v in positions.values()):
            raise ValueError(f"episodes[{index}].joint_positions values must be finite numbers")
        conditions = episode.get("success_conditions")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError(f"episodes[{index}].success_conditions must contain at least one assertion")
        for c_idx, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                raise ValueError(f"episodes[{index}].success_conditions[{c_idx}] must be an object")
            kind = condition.get("kind")
            if kind == "object_position":
                obj, pos, tol = condition.get("object"), condition.get("position"), condition.get("tolerance")
                if not isinstance(obj, str) or not obj.startswith("/"):
                    raise ValueError("object_position requires an absolute object path")
                if not isinstance(pos, list) or len(pos) != 3 or any(not _is_finite_num(v) for v in pos):
                    raise ValueError("object_position.position must contain three finite numbers")
                if not _is_finite_num(tol) or tol < 0:
                    raise ValueError("object_position.tolerance must be finite and non-negative")
            elif kind == "proximity":
                sensor, detected = condition.get("sensor"), condition.get("detected")
                if not isinstance(sensor, str) or not sensor.startswith("/"):
                    raise ValueError("proximity requires an absolute sensor path")
                if not isinstance(detected, bool):
                    raise ValueError("proximity requires detected boolean")
            else:
                raise ValueError(f"episodes[{index}].success_conditions[{c_idx}].kind is unsupported")
        if "until" in episode:
            until = episode["until"]
            kind = until.get("kind") if isinstance(until, dict) else None
            if kind == "floor_bounds":
                objs = [until.get("object")]
            elif kind in ("collision", "distance"):
                objs = until.get("objects")
            else:
                raise ValueError(f"episodes[{index}].until must be a supported diagnostic")
            expected = 1 if kind == "floor_bounds" else 2
            if not isinstance(objs, list) or len(objs) != expected or any(not isinstance(p, str) or not p.startswith("/") for p in objs):
                raise ValueError(f"episodes[{index}].until requires {expected} absolute object path(s)")
            if kind == "distance":
                thresh = until.get("threshold")
                if not _is_finite_num(thresh) or thresh < 0:
                    raise ValueError(f"episodes[{index}].until.threshold must be finite and non-negative")
    if total_steps > MAX_STEPS:
        raise ValueError(f"combined episode steps must not exceed {MAX_STEPS}")


def _stop_and_wait(sim):
    if sim.getSimulationState() == sim.simulation_stopped:
        return
    sim.stopSimulation()
    deadline = time.monotonic() + STOP_TIMEOUT_S
    while sim.getSimulationState() != sim.simulation_stopped and time.monotonic() < deadline:
        time.sleep(0.05)
    if sim.getSimulationState() != sim.simulation_stopped:
        raise TimeoutError("Simulation did not stop within timeout")


def _prepare_success_conditions(sim, conditions):
    prepared = []
    for condition in conditions:
        if condition["kind"] == "object_position":
            handle = sim.getObject(condition["object"], {"noError": True})
            if handle == -1:
                raise ValueError(f"Object not found: {condition['object']}")
            prepared.append((condition, handle))
        elif condition["kind"] == "proximity":
            handle = sim.getObject(condition["sensor"], {"noError": True})
            if handle == -1:
                raise ValueError(f"Sensor not found: {condition['sensor']}")
            if sim.getObjectType(handle) != sim.sceneobject_proximitysensor:
                raise ValueError(f"Sensor is not a proximity sensor: {condition['sensor']}")
            prepared.append((condition, handle))
    return prepared


def _evaluate_success_conditions(sim, conditions):
    results = []
    for condition, handle in conditions:
        if condition["kind"] == "object_position":
            actual = sim.getObjectPosition(handle, -1)
            error = math.sqrt(sum((actual[i] - condition["position"][i]) ** 2 for i in range(3)))
            results.append({
                "kind": "object_position",
                "object": condition["object"],
                "position": [round(v, 6) for v in actual],
                "error": round(error, 6),
                "tolerance": condition["tolerance"],
                "success": error <= condition["tolerance"],
            })
        elif condition["kind"] == "proximity":
            detected, distance, *_ = sim.readProximitySensor(handle)
            is_detected = bool(detected)
            results.append({
                "kind": "proximity",
                "sensor": condition["sensor"],
                "detected": is_detected,
                "distance": round(distance, 6) if is_detected and distance is not None else None,
                "expected_detected": condition["detected"],
                "success": is_detected is condition["detected"],
            })
    return results


def _reset_episode(sim, scene_path, name):
    _stop_and_wait(sim)
    sim.loadScene(str(scene_path))
    _stop_and_wait(sim)
    log("debug", "experiments.episode_reset", name=name, scene=scene_path)


def run_experiments(initial_scene, episodes, observe=None, sensors=None, sample_every=1, headless=False, host="localhost", port=23000):
    observe, sensors = observe or [], sensors or []
    sim = None
    try:
        validate_experiments(initial_scene, episodes, observe, sensors, sample_every)
        log("info", "experiments.started", episodes=len(episodes), scene=initial_scene)
        _client, sim = connect_sim(host, port, headless)
        results = []
        for index, episode in enumerate(episodes):
            name = episode.get("name", f"episode-{index + 1}")
            _reset_episode(sim, initial_scene, name)

            joint_actions = []
            for path, position in episode.get("joint_positions", {}).items():
                handle = sim.getObject(path, {"noError": True})
                if handle == -1 or sim.getObjectType(handle) != sim.sceneobject_joint:
                    raise ValueError(f"Joint not found: {path}")
                if sim.getJointType(handle) == sim.joint_spherical:
                    raise ValueError(f"Spherical joint positions are not supported: {path}")
                _cyclic, interval = sim.getJointInterval(handle)
                low, span = interval
                if not low <= position <= low + span:
                    raise ValueError(f"Joint position {position} exceeds limits [{low}, {low + span}]")
                joint_actions.append((handle, position))

            for handle, position in joint_actions:
                sim.setJointPosition(handle, position)
                sim.setJointTargetPosition(handle, position)

            initial_joint_positions = {
                path: sim.getJointPosition(handle)
                for path, (handle, _position) in zip(episode.get("joint_positions", {}), joint_actions)
            }
            handles = resolve_handles(sim, observe + sensors)
            for s_path in sensors:
                if sim.getObjectType(handles[s_path]) != sim.sceneobject_proximitysensor:
                    raise ValueError(f"Sensor is not a proximity sensor: {s_path}")

            prepared_conditions = _prepare_success_conditions(sim, episode.get("success_conditions", []))
            until = episode.get("until")
            floor = get_floor_info(sim) if until else None

            sim.setStepping(True)
            samples = []
            stopped_by = "steps"
            step = 0
            try:
                if sim.getSimulationState() == sim.simulation_stopped:
                    sim.startSimulation()
                start_time = sim.getSimulationTime()
                initial_sample = take_sample(sim, 0, handles, observe, sensors)
                samples.append(initial_sample)
                steps = episode.get("steps", 100)
                for step in range(1, steps + 1):
                    sim.step()
                    met = bool(until) and condition_met(sim, until, floor)
                    if met or step % sample_every == 0 or step == steps:
                        samples.append(take_sample(sim, step, handles, observe, sensors))
                    if met:
                        stopped_by = "condition"
                        break
                final_time = sim.getSimulationTime()
                checks = _evaluate_success_conditions(sim, prepared_conditions)
            finally:
                _stop_and_wait(sim)
                sim.setStepping(False)

            success = (stopped_by == "steps") and all(check["success"] for check in checks)
            elapsed = round(final_time - start_time, 6)
            initial_state = {
                "step": 0,
                "time": round(start_time, 6),
                "joint_positions": initial_joint_positions,
                "positions": initial_sample["positions"],
                "sensors": initial_sample["sensors"],
            }
            results.append({
                "name": name,
                "success": success,
                "stopped_by": stopped_by,
                "steps_run": step,
                "simulation_time": elapsed,
                "elapsed_simulation_time": elapsed,
                "initial_state": initial_state,
                "success_checks": checks,
                "samples": samples,
            })
            log("info", "experiments.episode_completed", name=name, success=success, steps=step, stopped_by=stopped_by)

        summary = {
            "episode_count": len(results),
            "successful_episodes": sum(item["success"] for item in results),
            "failed_episodes": sum(not item["success"] for item in results),
            "total_steps": sum(item["steps_run"] for item in results),
        }
        log("success", "experiments.completed", **summary)
        return {"success": True, "reset_method": "scene_reload", "summary": summary, "episodes": results}
    except Exception as error:
        log("error", "experiments.failed", error=str(error))
        return {"success": False, "error": str(error)}
    finally:
        if sim is not None:
            try:
                _stop_and_wait(sim)
            except Exception as error:
                log("error", "experiments.stop_failed", error=str(error))
            try:
                sim.setStepping(False)
            except Exception as error:
                log("error", "experiments.stepping_release_failed", error=str(error))
