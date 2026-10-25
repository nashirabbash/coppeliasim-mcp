"""Compare identical bounded experiments on caller-prepared engine scenes."""

from pathlib import Path

from .experiment_tools import run_experiments
from .json_log import log

MAX_ENGINES = 5


def compare_physics_engines(scenes, episodes, observe=None, sensors=None, sample_every=1, headless=False):
    if not isinstance(scenes, dict) or not 2 <= len(scenes) <= MAX_ENGINES:
        raise ValueError(f"scenes must map 2 to {MAX_ENGINES} engine names to scene paths")
    if any(not isinstance(name, str) or not name for name in scenes):
        raise ValueError("engine names must be non-empty strings")
    if len(set(scenes.values())) != len(scenes):
        raise ValueError("each engine must use a distinct scene file")
    missing = [path for path in scenes.values() if not isinstance(path, str) or not Path(path).is_file()]
    if missing:
        raise ValueError(f"Engine scene not found: {missing[0]}")

    comparisons = []
    log("info", "physics.benchmark_started", engines=list(scenes))
    for engine, scene in scenes.items():
        result = run_experiments(
            initial_scene=scene,
            episodes=episodes,
            observe=observe,
            sensors=sensors,
            sample_every=sample_every,
            headless=headless,
        )
        if not result.get("success"):
            return {"success": False, "engine": engine, "error": result.get("error", "engine benchmark failed"), "completed": comparisons}
        comparisons.append({
            "engine": engine,
            "scene": str(Path(scene).resolve()),
            "summary": result["summary"],
            "episodes": [
                {key: episode[key] for key in ("name", "success", "stopped_by", "steps_run", "simulation_time", "success_checks")}
                for episode in result["episodes"]
            ],
        })
    log("success", "physics.benchmark_completed", engine_count=len(comparisons), episode_count=len(episodes))
    return {"success": True, "scene_engines_are_caller_configured": True, "engine_labels_are_caller_supplied": True, "comparisons": comparisons}
