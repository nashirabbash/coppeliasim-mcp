"""MCP registrations for model import and ROS 2 readiness."""

import asyncio

from .floorplan_tools import import_floorplan
from .json_log import log
from .model_import import import_model, ros2_status
from .signal_tools import operate_signal
from .physics_benchmark import compare_physics_engines
from .physics_tools import configure_physics
from .sim_connection import connect_sim
from .ros2_tools import run_ros2


def _import(sim, client, path, position, orientation, scale, package_root):
    try:
        return import_model(sim, client, path, position, orientation, scale, package_root)
    except Exception as error:
        log("error", "model.import_failed", path=path, error=str(error))
        return {"success": False, "error": str(error)}


def _ros2_status(client):
    return ros2_status(client)


def register_p2_tools(server, json_result):
    @server.tool(name="coppelia_import_model", description="Import a URDF, SDF, STL, OBJ, or DAE file and report newly created roots and joint counts.")
    async def coppelia_import_model(path: str, position: list[float] | None = None, orientation: list[float] | None = None, scale: float = 1.0, package_root: str | None = None, headless: bool = False):
        client, sim = await asyncio.to_thread(connect_sim, headless=headless)
        return json_result(await asyncio.to_thread(_import, sim, client, path, position, orientation, scale, package_root))

    @server.tool(name="coppelia_ros2_status", description="Check whether the installed CoppeliaSim simROS2 plugin loads. This tool does not start ROS 2 or alter the scene.")
    async def coppelia_ros2_status(headless: bool = False):
        client, _sim = await asyncio.to_thread(connect_sim, headless=headless)
        return json_result(await asyncio.to_thread(_ros2_status, client))

    @server.tool(name="coppelia_ros2", description="Publish, echo, capture, or stream ROS 2 topics, call services, or send action goals through CoppeliaSim ROS 2 Humble runtime.")
    async def coppelia_ros2(
        operation: str,
        name: str,
        interface_type: str,
        payload: dict | None = None,
        timeout: float = 10.0,
        count: int | None = None,
        duration: float | None = None,
        rate: float | None = None,
        payloads: list[dict] | None = None,
        feedback_topic: str | None = None,
        feedback_type: str | None = None,
    ):
        try:
            result = await asyncio.to_thread(
                run_ros2,
                operation,
                name,
                interface_type,
                payload=payload,
                timeout=timeout,
                count=count,
                duration=duration,
                rate=rate,
                payloads=payloads,
                feedback_topic=feedback_topic,
                feedback_type=feedback_type,
            )
        except ValueError as error:
            result = {"success": False, "error": str(error)}
        return json_result(result)

    @server.tool(name="coppelia_signals", description="Read or write a named integer, float, or string CoppeliaSim signal. This is not a PLC network adapter.")
    async def coppelia_signals(operation: str, signal_type: str, name: str, value: int | float | str | None = None, headless: bool = False):
        _client, sim = await asyncio.to_thread(connect_sim, headless=headless)
        try:
            result = await asyncio.to_thread(operate_signal, sim, operation, signal_type, name, value)
        except (TypeError, ValueError) as error:
            log("error", "signals.operation_failed", operation=operation, signal_type=signal_type, name=name, error=str(error))
            result = {"success": False, "error": str(error)}
        return json_result(result)

    @server.tool(name="coppelia_import_floorplan", description="Create static cuboid segments from grayscale floor-plan pixels classified as walls, doors, and windows.")
    async def coppelia_import_floorplan(
        image_path: str,
        pixel_size: float,
        wall_height: float,
        door_height: float,
        window_height: float,
        wall_range: list[int],
        door_range: list[int],
        window_range: list[int],
        respondable: bool = True,
        headless: bool = False,
    ):
        _client, sim = await asyncio.to_thread(connect_sim, headless=headless)
        try:
            result = await asyncio.to_thread(
                import_floorplan, sim, image_path, pixel_size, wall_height, door_height,
                window_height, wall_range, door_range, window_range, respondable,
            )
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            log("error", "floorplan.import_failed", image_path=image_path, error=str(error))
            result = {"success": False, "error": str(error)}
        return json_result(result)

    @server.tool(name="coppelia_physics_engine", description="Inspect or set the scene physics engine property and dynamics step size. Changes require simulation stopped; engine_property is [index, version].")
    async def coppelia_physics_engine(engine_property: list[int] | None = None, dynamics_step_size: float | None = None, headless: bool = False):
        _client, sim = await asyncio.to_thread(connect_sim, headless=headless)
        try:
            result = await asyncio.to_thread(configure_physics, sim, engine_property, dynamics_step_size)
        except Exception as error:
            log("error", "physics.settings_failed", error=str(error))
            result = {"success": False, "error": str(error)}
        return json_result(result)

    @server.tool(name="coppelia_physics_benchmark", description="Run identical bounded episodes on 2–5 caller-prepared scenes and compare task outcomes; each scene retains its configured physics engine.")
    async def coppelia_physics_benchmark(scenes: dict[str, str], episodes: list[dict], observe: list[str] | None = None, sensors: list[str] | None = None, sample_every: int = 1, headless: bool = False):
        try:
            result = await asyncio.to_thread(
                compare_physics_engines,
                scenes,
                episodes,
                observe=observe,
                sensors=sensors,
                sample_every=sample_every,
                headless=headless,
            )
        except ValueError as error:
            result = {"success": False, "error": str(error)}
        return json_result(result)
