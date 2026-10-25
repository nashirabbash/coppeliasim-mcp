"""MCP registrations for model import and ROS 2 readiness."""

import asyncio

from json_log import log
from model_import import import_model, ros2_status
from sim_connection import connect_sim
from ros2_tools import run_ros2


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
