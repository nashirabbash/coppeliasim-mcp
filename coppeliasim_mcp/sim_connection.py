"""Connect to CoppeliaSim ZeroMQ remote API, auto-launching when requested."""

import os
from pathlib import Path
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
    RemoteAPIClient = None
    REMOTE_API_IMPORT_ERROR = err
else:
    REMOTE_API_IMPORT_ERROR = None


def is_coppelia_running(host: str = "localhost", port: int = 23000) -> bool:
    """Check that the ZeroMQ Remote API can serve a request."""
    if RemoteAPIClient is None:
        return False
    try:
        client = RemoteAPIClient(host=host, port=port)
        sim = client.require("sim")
        return sim.getInt32Param(sim.intparam_program_version) > 0
    except Exception:
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
    try:
        subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"CoppeliaSim launch script failed with status {error.returncode}: {detail}") from error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_coppelia_running():
            return True
        time.sleep(0.5)
    return False


def connect_sim(host: str = "localhost", port: int = 23000, headless: bool = False):
    """Return (client, sim); keep client alive while sim is in use."""
    if RemoteAPIClient is None:
        raise ImportError(f"Failed to import coppeliasim_zmqremoteapi_client: {REMOTE_API_IMPORT_ERROR}. Run setup_env.sh first.")
    if not is_coppelia_running(host, port):
        log("info", "simulator.launching", host=host, port=port, headless=headless)
        if not launch_coppelia(headless=headless):
            raise ConnectionError(f"Auto-launch failed. CoppeliaSim ZeroMQ API at {host}:{port} did not become ready.")
    client = RemoteAPIClient(host=host, port=port)
    log("success", "simulator.connected", host=host, port=port)
    return client, client.require("sim")


