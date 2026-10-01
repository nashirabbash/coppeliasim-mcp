#!/usr/bin/env bash
# coppelia_launch.sh: Launch or verify running CoppeliaSim instance

HEADLESS=false
if [ "${1:-}" = "--headless" ]; then
    HEADLESS=true
fi

# Check if port 23000 is open and answering
if ss -tln | grep -q ":23000 "; then
    echo "CoppeliaSim ZeroMQ API is already active on port 23000."
    exit 0
fi

COPPELIA_BIN="/home/myarchlinux/.local/bin/coppeliaSim"
if [ ! -x "$COPPELIA_BIN" ]; then
    COPPELIA_BIN="/home/myarchlinux/.local/opt/coppeliaSim/coppeliaSim.sh"
fi

export DISPLAY="${DISPLAY:-:0}"

if [ "$HEADLESS" = true ]; then
    echo "Launching CoppeliaSim in headless mode..."
    # -h runs emulated headless; pass -Gws_remote_api=false if needed or keep default
    nohup "$COPPELIA_BIN" -h </dev/null >/tmp/coppelia_stdout.log 2>&1 &
else
    echo "Launching CoppeliaSim with GUI..."
    nohup "$COPPELIA_BIN" </dev/null >/tmp/coppelia_stdout.log 2>&1 &
fi

COPPELIA_PID=$!
echo "CoppeliaSim launched with PID $COPPELIA_PID. Waiting for ZeroMQ port 23000..."

for i in {1..50}; do
    if ss -tln | grep -q ":23000 "; then
        # Give remote api a short moment to initialize rpc loop
        sleep 1.0
        echo "CoppeliaSim ZeroMQ API is ready on port 23000."
        exit 0
    fi
    sleep 0.5
done

echo "Error: CoppeliaSim port 23000 failed to open."
cat /tmp/coppelia_stdout.log | tail -n 20
exit 1
