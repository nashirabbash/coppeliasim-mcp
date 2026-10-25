"""Save/load CoppeliaSim scenes and export simulation results as JSON."""

import json
import time
from pathlib import Path

from .json_log import log
from .sim_connection import connect_sim

SCENE_SUFFIX = ".ttt"
STOP_TIMEOUT_S = 5.0


def check_writable_path(path: str, suffix: str) -> Path:
    target = Path(path)
    if target.suffix != suffix:
        raise ValueError(f"Path must end with {suffix}: {path}")
    if not target.parent.is_dir():
        raise ValueError(f"Parent directory does not exist: {target.parent}")
    return target


def stop_simulation(sim) -> None:
    if sim.getSimulationState() == sim.simulation_stopped:
        return
    log("info", "simulation.stopping_before_scene_load")
    sim.stopSimulation()
    deadline = time.time() + STOP_TIMEOUT_S
    while sim.getSimulationState() != sim.simulation_stopped and time.time() < deadline:
        time.sleep(0.1)
    if sim.getSimulationState() != sim.simulation_stopped:
        raise TimeoutError("Simulation did not stop within timeout")


def save_scene(sim, path: str) -> dict:
    target = check_writable_path(path, SCENE_SUFFIX)
    sim.saveScene(str(target))
    log("success", "scene.saved", path=str(target))
    return {"action": "save", "path": str(target)}


def load_scene(sim, path: str) -> dict:
    source = Path(path)
    if source.suffix != SCENE_SUFFIX or not source.is_file():
        raise ValueError(f"Scene file not found: {path}")
    stop_simulation(sim)
    sim.loadScene(str(source))
    log("success", "scene.loaded", path=str(source))
    return {"action": "load", "path": str(source)}


def export_results(path: str, payload: dict) -> str:
    target = check_writable_path(path, ".json")
    target.write_text(json.dumps(payload, indent=2))
    log("success", "results.exported", path=str(target))
    return str(target)


def run_scene_action(action: str, path: str, headless: bool = False, host: str = "localhost", port: int = 23000) -> dict:
    try:
        if action not in ("save", "load"):
            raise ValueError(f"Unsupported scene action: {action}")
        _client, sim = connect_sim(host, port, headless)
        result = save_scene(sim, path) if action == "save" else load_scene(sim, path)
        return {"success": True, **result}
    except Exception as error:
        log("error", "scene.action_failed", action=action, path=path, error=str(error))
        return {"success": False, "error": str(error)}
