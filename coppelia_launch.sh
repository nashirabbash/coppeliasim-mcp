#!/usr/bin/env bash
# Launch the native executable; vendor wrappers may terminate unrelated instances.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${COPPELIASIM_ROOT:-$HOME/.local/opt/coppeliaSim}"
PYTHON="$DIR/.venv/bin/python"
export COPPELIASIM_ROOT="$ROOT"
export QT_QPA_PLATFORM=xcb
export DISPLAY="${DISPLAY:-:0}"
export LD_LIBRARY_PATH="$ROOT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Verify RPC rather than treating an open TCP socket as a ready simulator.
probe() {
    timeout 3 "$PYTHON" -c '
from runner import RemoteAPIClient
client = RemoteAPIClient()
sim = client.require("sim")
assert sim.getInt32Param(sim.intparam_program_version) > 0
' >/dev/null 2>&1
}

cd "$DIR"
if probe; then
    echo '{"level":"info","event":"simulator.already_ready","port":23000}'
    exit 0
fi
ROS2_MODE="${COPPELIASIM_ROS2_MODE:-auto}"
ROS2_IMAGE="${COPPELIASIM_ROS2_IMAGE:-coppeliasim-ros2:humble}"
case "$ROS2_MODE" in
    docker)
        exec "$DIR/coppelia_ros2_container.sh" start
        ;;
    auto)
        if docker image inspect "$ROS2_IMAGE" >/dev/null 2>&1; then
            exec "$DIR/coppelia_ros2_container.sh" start
        fi
        ;;
    native)
        ;;
    *)
        echo "{\"level\":\"error\",\"event\":\"simulator.invalid_ros2_mode\",\"mode\":\"$ROS2_MODE\"}" >&2
        exit 2
        ;;
esac

if [ -n "${COPPELIASIM_ROS2_SETUP:-}" ]; then
    if [ ! -r "$COPPELIASIM_ROS2_SETUP" ]; then
        echo "{\"level\":\"error\",\"event\":\"simulator.ros2_setup_missing\",\"path\":\"$COPPELIASIM_ROS2_SETUP\"}" >&2
        exit 1
    fi
    source "$COPPELIASIM_ROS2_SETUP"
fi

export LD_LIBRARY_PATH="$ROOT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

test -x "$ROOT/coppeliaSim"
"$PYTHON" -c 'import zmq, cbor2'
ARGS=(-xnone "-Gpython=$PYTHON" -GsimCmd.autoStart=false)
if [ "${1:-}" = "--headless" ]; then
    ARGS+=(-h)
fi

(
    cd "$ROOT"
    exec nohup setsid "$ROOT/coppeliaSim" "${ARGS[@]}"
) </dev/null >/tmp/coppelia_stdout.log 2>&1 &
PID=$!
echo "{\"level\":\"info\",\"event\":\"simulator.launching\",\"pid\":$PID}"
for ((attempt=0; attempt<25; attempt++)); do
    if probe; then
        echo '{"level":"success","event":"simulator.rpc_ready","port":23000}'
        exit 0
    fi
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.5
done
echo '{"level":"error","event":"simulator.launch_failed","log":"/tmp/coppelia_stdout.log"}' >&2
exit 1
