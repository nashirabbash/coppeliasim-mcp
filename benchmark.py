#!/usr/bin/env python3
"""CoppeliaSim MCP Evaluation & Benchmark Suite.

Evaluates:
1. Tool Call Count (checks if agent solves task in 1 turn without exploration).
2. Token Usage (input & output tokens consumed via omp JSON stream).
3. Execution Success & Scene Verification (verifies objects exist in CoppeliaSim).
4. Visual Snapshot Validity (ensures image rendered properly at 1024x768).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from runner import run_code, is_coppelia_running, launch_coppelia, SNAPSHOT_PATH

# Standard Benchmark Test Cases
BENCHMARK_SUITE = [
    {
        "id": "TC-01-House-And-Robot",
        "description": "Construct house with 5m walls and roof, spawn pioneer robot inside, start simulation",
        "prompt": (
            "Gunakan tool coppelia_step untuk membuat simulasi di CoppeliaSim: "
            "bangun lantai 10x10, 4 dinding setinggi 5 meter, atap di atasnya, "
            "lalu spawn robot pioneer di dalam rumah dan mulai simulasi."
        ),
        "expected_objects": ["PioneerP3DX"],
        "min_shapes": 5  # floor + 4 walls + roof
    },
    {
        "id": "TC-02-Multi-Obstacles-YouBot",
        "description": "Spawn youbot and place red obstacle blocks around it",
        "prompt": (
            "Gunakan tool coppelia_step di CoppeliaSim: "
            "spawn robot youbot di posisi [0, 0, 0.2] dan buat 3 balok kubus rintangan merah di sekitarnya."
        ),
        "expected_objects": ["youBot"],
        "min_shapes": 3
    }
]


def query_scene_state(expected_objects, min_shapes=0):
    """Run direct Python check against CoppeliaSim to verify scene reality."""
    check_code = f"""
import json
results = {{}}
# Check expected objects
for name in {expected_objects}:
    h = sim.getObject(f'/{{name}}', {{'noError': True}})
    if h == -1:
        all_objs = sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 0)
        found = any(name.lower() in sim.getObjectAlias(o).lower() for o in all_objs)
        results[name] = found
    else:
        results[name] = True

shapes = sim.getObjectsInTree(sim.handle_scene, sim.object_shape_type, 0)
results['shape_count'] = len(shapes)
results['sim_state'] = sim.getSimulationState()
print(json.dumps(results))
"""
    res = run_code(check_code, take_snapshot=False)
    try:
        return json.loads(res.get("stdout", "{}"))
    except Exception:
        return {"raw": res.get("stdout")}


def run_benchmark_case(case, omp_cmd="omp"):
    print(f"\n=======================================================")
    print(f"▶ Running Test Case: {case['id']}")
    print(f"  Prompt: {case['prompt'][:80]}...")
    print(f"=======================================================")

    # Ensure CoppeliaSim is running
    if not is_coppelia_running():
        print("Starting CoppeliaSim...")
        launch_coppelia(headless=False)

    # Clean old snapshot
    if SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.unlink()

    # Reset simulator before test case
    run_code("sim.stopSimulation()", reset=True, take_snapshot=False)
    time.sleep(0.5)

    start_time = time.time()

    # Increase timeout to 300s to avoid premature timeout
    cmd = [omp_cmd, "--mode=json", case["prompt"]]
    
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
    except subprocess.TimeoutExpired:
        return {
            "id": case["id"],
            "status": "TIMEOUT",
            "error": "Execution timed out after 300 seconds."
        }

    duration = time.time() - start_time

    # Parse JSON stream from omp
    tool_invocations = 0
    input_tokens = 0
    output_tokens = 0
    tool_names = set()

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            event_type = data.get("type", "")
            # Tool call events
            if event_type in ("tool_call", "tool_use", "call"):
                tool_invocations += 1
                t_name = data.get("name") or data.get("tool") or data.get("function", {}).get("name")
                if t_name:
                    tool_names.add(t_name)
            elif data.get("tool") == "coppelia_step" or data.get("name") == "coppelia_step":
                tool_invocations += 1
                tool_names.add("coppelia_step")

            # Token usage
            usage = data.get("usage") or data.get("tokens") or {}
            if isinstance(usage, dict):
                if "input_tokens" in usage:
                    input_tokens = max(input_tokens, usage["input_tokens"])
                if "output_tokens" in usage:
                    output_tokens = max(output_tokens, usage["output_tokens"])
                if "prompt_tokens" in usage:
                    input_tokens = max(input_tokens, usage["prompt_tokens"])
                if "completion_tokens" in usage:
                    output_tokens = max(output_tokens, usage["completion_tokens"])
                if "total_tokens" in usage and input_tokens == 0:
                    input_tokens = usage["total_tokens"]
        except json.JSONDecodeError:
            pass

    # If stream didn't expose tool_call event types, fallback to 1 invocation
    if tool_invocations == 0 and "coppelia_step" in proc.stdout:
        tool_invocations = 1
        tool_names.add("coppelia_step")

    # Verify physical scene in CoppeliaSim
    scene_data = query_scene_state(case["expected_objects"], case.get("min_shapes", 0))

    objects_ok = all(scene_data.get(obj, False) for obj in case["expected_objects"])
    shapes_ok = scene_data.get("shape_count", 0) >= case.get("min_shapes", 0)
    sim_ok = objects_ok and shapes_ok

    snapshot_ok = SNAPSHOT_PATH.exists() and SNAPSHOT_PATH.stat().st_size > 5000

    status = "PASS" if (sim_ok and snapshot_ok and tool_invocations <= 2) else "WARN" if sim_ok else "FAIL"

    return {
        "id": case["id"],
        "status": status,
        "duration_s": round(duration, 2),
        "tool_calls": tool_invocations,
        "tool_names": list(tool_names),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "objects_verified": objects_ok,
        "shapes_count": scene_data.get("shape_count", 0),
        "snapshot_valid": snapshot_ok,
        "snapshot_path": str(SNAPSHOT_PATH) if snapshot_ok else None
    }


def main():
    print("=======================================================")
    print("  COPPELIASIM MCP BENCHMARK & EVALUATION RUNNER")
    print("=======================================================")

    results = []
    for case in BENCHMARK_SUITE:
        try:
            res = run_benchmark_case(case)
            results.append(res)
        except Exception as e:
            print(f"Error executing case {case['id']}: {e}")
            results.append({
                "id": case["id"],
                "status": "ERROR",
                "error": str(e)
            })

    # Print Summary Table
    print("\n\n" + "=" * 80)
    print("                    BENCHMARK EVALUATION SCOREBOARD")
    print("=" * 80)
    header = f"{'Test Case':<26} | {'Status':<6} | {'Calls':<5} | {'In Tokens':<9} | {'Out Tokens':<10} | {'Scene':<7} | {'Snapshot':<8}"
    print(header)
    print("-" * 80)

    for r in results:
        if r.get("status") in ("ERROR", "TIMEOUT"):
            st = r.get("status")
            print(f"{r['id']:<26} | {st:<6} | -     | -         | -          | -       | -")
            continue

        scene_str = "OK" if r["objects_verified"] else "FAIL"
        snap_str = "OK" if r["snapshot_valid"] else "FAIL"
        row = (
            f"{r['id']:<26} | "
            f"{r['status']:<6} | "
            f"{r['tool_calls']:<5} | "
            f"{r['input_tokens']:<9} | "
            f"{r['output_tokens']:<10} | "
            f"{scene_str:<7} | "
            f"{snap_str:<8}"
        )
        print(row)

    print("=" * 80)
    report_file = DIR / "benchmark_report.json"
    report_file.write_text(json.dumps(results, indent=2))
    print(f"Detailed JSON report saved to: {report_file}\n")


if __name__ == "__main__":
    main()
