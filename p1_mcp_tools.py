"""MCP registrations for P1 observation and experiment workflows."""

import asyncio

from dataset_tools import record_dataset
from experiment_tools import run_experiments
from json_log import log
from mechanism_tools import inspect_mechanism
from sensor_tools import read_sensors
from sim_connection import connect_sim


def run_sensor_reading(sim, sensors):
    try:
        return read_sensors(sim, sensors)
    except Exception as error:
        log("error", "sensors.read_failed", error=str(error))
        return {"success": False, "error": str(error)}


def run_mechanism_inspection(sim, root_path):
    try:
        return inspect_mechanism(sim, root_path)
    except Exception as error:
        log("error", "mechanism.inspection_failed", error=str(error))
        return {"success": False, "error": str(error)}


def register_p1_tools(server, json_result):
    @server.tool(name="coppelia_sensors", description="Read selected proximity, vision RGB, metric depth, force/torque, or sampled vision point-cloud data from typed sensor paths.")
    async def coppelia_sensors(sensors: list[dict]):
        _client, sim = await asyncio.to_thread(connect_sim)
        result = await asyncio.to_thread(run_sensor_reading, sim, sensors)
        return json_result(result)

    @server.tool(name="coppelia_record_dataset", description="Record bounded, per-step synchronized simulation state and typed sensor samples to JSON.")
    async def coppelia_record_dataset(steps: int = 100, sensors: list[dict] | None = None, observe: list[str] | None = None, sample_every: int = 1, until: dict | None = None, export_path: str | None = None, max_samples: int = 1000, stop_on_finish: bool = False, headless: bool = False):
        result = await asyncio.to_thread(
            record_dataset,
            steps=steps,
            sensors=sensors,
            observe=observe,
            sample_every=sample_every,
            until=until,
            export_path=export_path,
            max_samples=max_samples,
            stop_on_finish=stop_on_finish,
            headless=headless,
        )
        return json_result(result)

    @server.tool(name="coppelia_mechanism", description="Inspect a robot subtree and report joint types, limits, current/target positions, sensors, base candidate, and end-effector candidates.")
    async def coppelia_mechanism(root_path: str):
        _client, sim = await asyncio.to_thread(connect_sim)
        result = await asyncio.to_thread(run_mechanism_inspection, sim, root_path)
        return json_result(result)

    @server.tool(name="coppelia_experiments", description="Run up to 20 simulation episodes in an explicit scene with per-episode scene reload, joint positions, diagnostics, and success conditions; combined steps are capped at 10000.")
    async def coppelia_experiments(initial_scene: str, episodes: list[dict], observe: list[str] | None = None, sensors: list[str] | None = None, sample_every: int = 1, headless: bool = False):
        result = await asyncio.to_thread(run_experiments, initial_scene=initial_scene, episodes=episodes, observe=observe, sensors=sensors, sample_every=sample_every, headless=headless)
        return json_result(result)
