#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$DIR/.." && pwd)"
ROOT="${COPPELIASIM_ROOT:-$HOME/.local/opt/coppeliaSim}"
IMAGE="${COPPELIASIM_ROS2_IMAGE:-coppeliasim-ros2:humble}"
CONTAINER="coppeliasim-ros2-mcp"
PYTHON="${COPPELIASIM_PYTHON:-$REPO_DIR/.venv/bin/python}"

probe() {
    timeout 3 env PYTHONPATH="$REPO_DIR" "$PYTHON" -c '
from coppeliasim_mcp.sim_connection import RemoteAPIClient
client = RemoteAPIClient()
sim = client.require("sim")
assert sim.getInt32Param(sim.intparam_program_version) > 0
' >/dev/null 2>&1
}

ros_probe() {
    timeout 3 env PYTHONPATH="$REPO_DIR" "$PYTHON" -c '
from coppeliasim_mcp.sim_connection import RemoteAPIClient
client = RemoteAPIClient()
client.require("simROS2")
' >/dev/null 2>&1
}

case "${1:-start}" in
    build)
        docker build -t "$IMAGE" -f "$REPO_DIR/docker/ros2/Dockerfile" "$REPO_DIR/docker/ros2"
        ;;
    start)
        if ros_probe; then
            echo '{"level":"info","event":"simulator.ros2_already_ready","port":23000}'
            exit 0
        fi
        if probe; then
            echo '{"level":"error","event":"simulator.non_ros2_instance_running","action":"stop the current CoppeliaSim before starting the ROS 2 container"}' >&2
            exit 1
        fi
        if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
            echo "ROS 2 image not found; build it with $DIR/coppelia_ros2_container.sh build" >&2
            exit 1
        fi
        if docker ps -q --filter "name=^/${CONTAINER}$" | grep -q .; then
            :
        elif docker ps -aq --filter "name=^/${CONTAINER}$" | grep -q .; then
            echo "Container $CONTAINER exists but is stopped; run $DIR/coppelia_ros2_container.sh stop" >&2
            exit 1
        else
            docker run -d --label com.coppelia-tools.ros2=true --name "$CONTAINER" --network host --ipc host \
                --user "$(id -u):$(id -g)" --env HOME="$HOME" \
                --env ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
                --volume "$ROOT:/opt/coppeliaSim:ro" \
                --volume "$HOME:$HOME" --volume /tmp:/tmp \
                "$IMAGE" bash -lc 'source /opt/ros/humble/setup.bash && export QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH=/opt/coppeliaSim${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} && cd /opt/coppeliaSim && exec ./coppeliaSim -xnone -Gpython=/usr/bin/python3 -GsimCmd.autoStart=false -h' >/dev/null
        fi
        for ((attempt=0; attempt<60; attempt++)); do
            if ros_probe; then
                echo '{"level":"success","event":"simulator.ros2_rpc_ready","port":23000}'
                exit 0
            fi
            if ! docker ps -q --filter "name=^/${CONTAINER}$" | grep -q .; then
                break
            fi
            sleep 0.5
        done
        docker logs "$CONTAINER" >&2 || true
        echo '{"level":"error","event":"simulator.ros2_launch_failed"}' >&2
        exit 1
        ;;
    stop)
        if [ "$(docker inspect -f '{{index .Config.Labels "com.coppelia-tools.ros2"}}' "$CONTAINER" 2>/dev/null || true)" != true ]; then
            echo "Refusing to stop a container not created by CoppeliaTools" >&2
            exit 1
        fi
        docker rm -f "$CONTAINER" >/dev/null
        ;;
    logs)
        docker logs "$CONTAINER"
        ;;
    *)
        echo "Usage: $0 {build|start|stop|logs}" >&2
        exit 2
        ;;
esac
