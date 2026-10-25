"""Connect to CoppeliaSim ZeroMQ remote API, auto-launching when requested."""

from json_log import log
from runner import RemoteAPIClient, is_coppelia_running, launch_coppelia


def connect_sim(host: str = "localhost", port: int = 23000, headless: bool = False):
    """Return (client, sim); keep client alive while sim is in use."""
    if not is_coppelia_running(host, port):
        log("info", "simulator.launching", host=host, port=port, headless=headless)
        if not launch_coppelia(headless=headless):
            raise ConnectionError(f"Auto-launch failed. CoppeliaSim port {port} did not become ready.")
    client = RemoteAPIClient(host=host, port=port)
    log("success", "simulator.connected", host=host, port=port)
    return client, client.require("sim")
