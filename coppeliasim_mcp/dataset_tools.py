"""Synchronized sensor and state dataset recording across stepped simulation."""

import json
from pathlib import Path

from .json_log import log
from .sensor_tools import MAX_POINT_CLOUD_POINTS, SENSOR_OBJECT_TYPES, SENSOR_TYPES, read_one

MAX_STEPS = 10_000

DEFAULT_MAX_SAMPLES = 1000
MAX_SAMPLE_LIMIT = 10_000


def validate_dataset_request(
    steps: int,
    sample_every: int,
    observe: list[str],
    sensors: list[dict],
    max_samples: int,
    export_path: str | None = None,
) -> None:
    if not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= MAX_STEPS:
        raise ValueError(f"steps must be an integer between 1 and {MAX_STEPS}")
    if not isinstance(sample_every, int) or isinstance(sample_every, bool) or sample_every < 1:
        raise ValueError("sample_every must be an integer of at least 1")
    if not isinstance(max_samples, int) or isinstance(max_samples, bool) or not 1 <= max_samples <= MAX_SAMPLE_LIMIT:
        raise ValueError(f"max_samples must be an integer between 1 and {MAX_SAMPLE_LIMIT}")


    if not isinstance(observe, list):
        raise ValueError("observe must be a list of object paths")
    for idx, path in enumerate(observe):
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"observe[{idx}] must be an absolute object path: {path}")

    if not isinstance(sensors, list):
        raise ValueError("sensors must be a list of sensor specifications")
    for idx, sensor in enumerate(sensors):
        if not isinstance(sensor, dict):
            raise ValueError(f"sensors[{idx}] must be an object with path and type")
        path = sensor.get("path")
        kind = sensor.get("type")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"sensors[{idx}].path must be an absolute path: {path}")
        if kind not in SENSOR_TYPES:
            raise ValueError(f"sensors[{idx}].type must be one of {sorted(SENSOR_TYPES)}: {kind}")
        if kind == "point_cloud" and "max_points" in sensor:
            mp = sensor["max_points"]
            if not isinstance(mp, int) or isinstance(mp, bool) or not 1 <= mp <= MAX_POINT_CLOUD_POINTS:
                raise ValueError(f"sensors[{idx}].max_points must be an integer between 1 and {MAX_POINT_CLOUD_POINTS}")
    if export_path is not None:
        target = Path(export_path)
        if target.suffix != ".json":
            raise ValueError(f"Path must end with .json: {export_path}")
        if not target.parent.is_dir():
            raise ValueError(f"Parent directory does not exist: {target.parent}")


def resolve_handles(sim, paths: list[str]) -> dict[str, int]:
    handles = {}
    for path in paths:
        handle = sim.getObject(path, {"noError": True})
        if handle == -1:
            raise ValueError(f"Object not found: {path}")
        handles[path] = handle
    return handles

def resolve_sensor_handles(sim, sensors: list[dict]) -> dict[str, int]:
    handles = {}
    for sensor in sensors:
        path = sensor["path"]
        kind = sensor["type"]
        handle = sim.getObject(path, {"noError": True})
        if handle == -1:
            raise ValueError(f"Sensor object not found: {path}")
        expected_type_attr = SENSOR_OBJECT_TYPES.get(kind)
        expected_type = getattr(sim, expected_type_attr, None) if expected_type_attr else None
        if expected_type is not None and hasattr(sim, "getObjectType"):
            actual_type = sim.getObjectType(handle)
            if actual_type != expected_type:
                raise ValueError(f"{kind} requires an object of type {expected_type_attr}: {path}")
        handles[path] = handle
    return handles


def get_scene_metadata(sim) -> dict:
    meta = {}
    for param_name in ("stringparam_scene_name", "stringparam_scene_path", "stringparam_scene_path_and_name"):
        param = getattr(sim, param_name, None)
        if param is not None and hasattr(sim, "getStringParam"):
            try:
                val = sim.getStringParam(param)
                if val:
                    key = param_name.replace("stringparam_", "")
                    meta[key] = val
            except Exception:
                pass
    if hasattr(sim, "getSimulationTimeStep"):
        try:
            meta["time_step"] = sim.getSimulationTimeStep()
        except Exception:
            pass
    return meta


def take_dataset_sample(sim, step: int, observe_handles: dict[str, int], sensors: list[dict]) -> dict:
    sim_time = round(sim.getSimulationTime(), 6)
    positions = {}
    orientations = {}
    joints = {}
    for path, handle in observe_handles.items():
        try:
            positions[path] = [round(v, 6) for v in sim.getObjectPosition(handle, -1)]
        except Exception:
            pass
        if hasattr(sim, "getObjectQuaternion"):
            try:
                orientations[path] = [round(v, 6) for v in sim.getObjectQuaternion(handle, -1)]
            except Exception:
                pass
        if hasattr(sim, "sceneobject_joint") and hasattr(sim, "getObjectType") and hasattr(sim, "getJointPosition"):
            try:
                if sim.getObjectType(handle) == sim.sceneobject_joint:
                    joints[path] = round(sim.getJointPosition(handle), 6)
            except Exception:
                pass

    state = {"positions": positions}
    if orientations:
        state["orientations"] = orientations
    if joints:
        state["joints"] = joints

    sensor_readings = [read_one(sim, sensor) for sensor in sensors]

    return {
        "step": step,
        "timestamp": sim_time,
        "time": sim_time,
        "state": state,
        "sensors": sensor_readings,
    }


def record_dataset(
    sim=None,
    steps: int = 100,
    sensors: list[dict] | None = None,
    observe: list[str] | None = None,
    sample_every: int = 1,
    until: dict | None = None,
    export_path: str | None = None,
    max_samples: int | None = DEFAULT_MAX_SAMPLES,
    stop_on_finish: bool = False,
    headless: bool = False,
    host: str = "localhost",
    port: int = 23000,
) -> dict:
    if isinstance(sim, int):
        steps = sim
        sim = None
    sensors = sensors or []
    observe = observe or []
    if max_samples is None:
        max_samples = DEFAULT_MAX_SAMPLES

    try:
        validate_dataset_request(steps, sample_every, observe, sensors, max_samples, export_path)
        if sim is None:
            from .sim_connection import connect_sim
            _client, sim = connect_sim(host, port, headless)

        observe_handles = resolve_handles(sim, observe)
        resolve_sensor_handles(sim, sensors)

        log("info", "dataset.recording_started", steps=steps, sample_every=sample_every, sensors=len(sensors), observe=len(observe))

        if until:
            from .sim_run import condition_met
            from .runner import get_floor_info
            floor = get_floor_info(sim)
        else:
            condition_met = floor = None
        scene_meta = get_scene_metadata(sim)
        time_step = sim.getSimulationTimeStep() if hasattr(sim, "getSimulationTimeStep") else None

        samples = []
        stopped_by = "steps"
        step = 0

        was_stopped = sim.getSimulationState() == sim.simulation_stopped
        sim.setStepping(True)
        try:
            if was_stopped:
                sim.startSimulation()

            for step in range(1, steps + 1):
                sim.step()
                met = bool(until) and condition_met(sim, until, floor)

                if met or step % sample_every == 0 or step == steps:
                    samples.append(take_dataset_sample(sim, step, observe_handles, sensors))
                    if len(samples) >= max_samples:
                        stopped_by = "max_samples" if not met else "condition"
                        break

                if met:
                    stopped_by = "condition"
                    break
        finally:
            sim.setStepping(False)
            if stop_on_finish and sim.getSimulationState() != sim.simulation_stopped:
                try:
                    sim.stopSimulation()
                except Exception:
                    pass

        result = {
            "success": True,
            "metadata": {
                "scene": scene_meta,
                "simulation_time_step": time_step,
                "steps_requested": steps,
                "sample_every": sample_every,
                "max_samples": max_samples,
            },
            "summary": {
                "steps_run": step,
                "sample_count": len(samples),
                "stopped_by": stopped_by,
                "final_time": round(sim.getSimulationTime(), 6),
            },
            "samples": samples,
        }

        if export_path:
            target = Path(export_path)
            target.write_text(json.dumps(result, indent=2))
            result["export_path"] = str(target)
            log("success", "results.exported", path=str(target))

        log("success", "dataset.recording_completed", steps_run=step, samples=len(samples), stopped_by=stopped_by)
        return result

    except Exception as error:
        log("error", "dataset.recording_failed", error=str(error))
        return {"success": False, "error": str(error)}
