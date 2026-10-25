#!/usr/bin/env python3
"""Root compatibility launcher for CoppeliaSim Benchmark Suite."""
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from scripts.benchmark import (
    BENCHMARK_SUITE,
    SNAPSHOT_PATH,
    main,
    query_scene_state,
    run_benchmark_case,
    run_code,
)

if __name__ == "__main__":
    main()
