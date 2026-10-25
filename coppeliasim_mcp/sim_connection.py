"""Connect to CoppeliaSim ZeroMQ remote API, auto-launching when requested."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from .json_log import log
from .resources import resource_path

# Add CoppeliaSim bundled Python client to sys.path
COPPELIA_ROOT = Path(os.environ.get("COPPELIASIM_ROOT", "/home/myarchlinux/.local/opt/coppeliaSim"))
CLIENT_SRC = COPPELIA_ROOT / "programming" / "zmqRemoteApi" / "clients" / "python" / "src"
if CLIENT_SRC.exists() and str(CLIENT_SRC) not in sys.path:
    sys.path.insert(0, str(CLIENT_SRC))

try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
except ImportError as err:
    print(json.dumps({
        "success": False,
        "error": f"Failed to import coppeliasim_zmqremoteapi_client: {err}. Run setup_env.sh first."
    }))


def is_coppelia_running(host: str = "localhost", port: int = 23000) -> bool:
    """Check if CoppeliaSim ZeroMQ server is responsive."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def launch_coppelia(headless: bool = False, timeout: int = 25):
    """Launch CoppeliaSim GUI by default, or headless when explicitly requested."""
    if is_coppelia_running():
        return True

    cmd = ["bash", str(resource_path("scripts", "coppelia_launch.sh"))]
    if headless:
        cmd.append("--headless")
    env = os.environ.copy()
    env["COPPELIASIM_PYTHON"] = sys.executable
    subprocess.run(cmd, check=True, env=env)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_coppelia_running():
            return True
        time.sleep(0.5)
    return False


def connect_sim(host: str = "localhost", port: int = 23000, headless: bool = False):
    """Return (client, sim); keep client alive while sim is in use."""
    if not is_coppelia_running(host, port):
        log("info", "simulator.launching", host=host, port=port, headless=headless)
        if not launch_coppelia(headless=headless):
            raise ConnectionError(f"Auto-launch failed. CoppeliaSim port {port} did not become ready.")
    client = RemoteAPIClient(host=host, port=port)
    log("success", "simulator.connected", host=host, port=port)
    return client, client.require("sim")
