"""Structured simulation: step N times or until a diagnostic fires, then sample state."""

from .json_log import log
from .runner import evaluate_scene_diagnostics, get_floor_info
from .scene_io import export_results
from .sim_connection import connect_sim

MAX_STEPS = 10_000


def validate_request(steps: int, sample_every: int, observe: list[str], sensors: list[str]) -> None:
    if not isinstance(steps, int) or not 1 <= steps <= MAX_STEPS:
        raise ValueError(f"steps must be an integer between 1 and {MAX_STEPS}")
    if not isinstance(sample_every, int) or sample_every < 1:
        raise ValueError("sample_every must be an integer of at least 1")
    if not all(isinstance(name, str) and name for name in observe + sensors):
        raise ValueError("observe and sensors must be lists of non-empty object paths")


def resolve_handles(sim, paths: list[str]) -> dict[str, int]:
    handles = {path: sim.getObject(path, {"noError": True}) for path in paths}
    missing = [path for path, handle in handles.items() if handle == -1]
    if missing:
        raise ValueError(f"Object not found: {missing}")
    return handles


def read_proximity(sim, handle: int) -> dict:
    detected, distance, *_ = sim.readProximitySensor(handle)
    return {"detected": bool(detected), "distance": round(distance, 6) if detected else None}


def take_sample(sim, step: int, handles: dict[str, int], observe: list[str], sensors: list[str]) -> dict:
    return {
        "step": step,
        "time": round(sim.getSimulationTime(), 6),
        "positions": {path: [round(v, 6) for v in sim.getObjectPosition(handles[path], -1)] for path in observe},
        "sensors": {path: read_proximity(sim, handles[path]) for path in sensors},
    }


def condition_met(sim, until: dict, floor: dict) -> bool:
    item = evaluate_scene_diagnostics(sim, [until], floor)[0]
    if item["status"] == "unavailable":
        raise ValueError(f"until diagnostic unavailable: {item.get('error')}")
    return item["status"] == "issue"


def ensure_running(sim) -> None:
    if sim.getSimulationState() == sim.simulation_stopped:
        sim.startSimulation()


def run_steps(sim, steps: int, observe: list[str], sensors: list[str], sample_every: int, until: dict | None) -> dict:
    handles = resolve_handles(sim, observe + sensors)
    floor = get_floor_info(sim) if until else None
    samples, stopped_by, step = [], "steps", 0
    sim.setStepping(True)
    try:
        ensure_running(sim)
        for step in range(1, steps + 1):
            sim.step()
            met = bool(until) and condition_met(sim, until, floor)
            if met or step % sample_every == 0 or step == steps:
                samples.append(take_sample(sim, step, handles, observe, sensors))
            if met:
                stopped_by = "condition"
                break
    finally:
        sim.setStepping(False)
    log("debug", "simulation.steps_done", stopped_by=stopped_by, steps_run=step, samples=len(samples))
    return {"stopped_by": stopped_by, "steps_run": step, "final_time": round(sim.getSimulationTime(), 6), "samples": samples}


def run_simulation(
    steps: int = 100,
    observe: list[str] | None = None,
    sensors: list[str] | None = None,
    sample_every: int = 1,
    until: dict | None = None,
    export_path: str | None = None,
    headless: bool = False,
    host: str = "localhost",
    port: int = 23000,
) -> dict:
    observe, sensors = observe or [], sensors or []
    try:
        validate_request(steps, sample_every, observe, sensors)
        log("info", "simulation.started", steps=steps, sample_every=sample_every, until=until)
        _client, sim = connect_sim(host, port, headless)
        result = run_steps(sim, steps, observe, sensors, sample_every, until)
        if export_path:
            result["export_path"] = export_results(export_path, result)
        log("success", "simulation.completed", stopped_by=result["stopped_by"], steps_run=result["steps_run"])
        return {"success": True, **result}
    except Exception as error:
        log("error", "simulation.failed", error=str(error))
        return {"success": False, "error": str(error)}
