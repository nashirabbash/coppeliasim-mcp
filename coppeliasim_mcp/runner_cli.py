#!/usr/bin/env python3
"""CLI interface for CoppeliaSim runner."""

import argparse
import json
import sys
if __package__ in (None, ""):
    from pathlib import Path
    _repo_dir = Path(__file__).resolve().parent.parent
    if str(_repo_dir) not in sys.path:
        sys.path.insert(0, str(_repo_dir))
    __package__ = "coppeliasim_mcp"

from .runner import ROBOT_ALIASES, is_coppelia_running, launch_coppelia, run_code


def build_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser for runner."""
    parser = argparse.ArgumentParser(description="Execute Python scripts against CoppeliaSim")
    parser.add_argument("--code", type=str, help="Python code string to execute")
    parser.add_argument("--file", type=str, help="Path to Python script file to execute")
    parser.add_argument("--host", type=str, default="localhost", help="CoppeliaSim ZMQ host")
    parser.add_argument("--port", type=int, default=23000, help="CoppeliaSim ZMQ port")
    parser.add_argument("--timeout", type=float, default=30.0, help="Maximum user script execution time in seconds")
    parser.add_argument("--diagnostics", type=json.loads, help="JSON list of opt-in scene diagnostics")
    parser.add_argument("--no-snapshot", action="store_true", help="Disable auto-capture snapshot")
    parser.add_argument("--reset", action="store_true", help="Stop simulation before running")
    parser.add_argument("--list-robots", action="store_true", help="List available robot model aliases")

    parser.add_argument("--launch", action="store_true", help="Launch CoppeliaSim GUI if not already running")
    parser.add_argument("--launch-headless", action="store_true", help="Launch CoppeliaSim in headless mode if not running")
    parser.add_argument("--only-launch", action="store_true", help="Launch CoppeliaSim and exit")
    return parser


def main(argv: list[str] | None = None, args: list[str] | None = None) -> None:
    if argv is None and args is not None:
        argv = args

    parser = build_parser()
    parsed_args = parser.parse_args(argv)

    if parsed_args.list_robots:
        print(json.dumps({"robot_aliases": ROBOT_ALIASES}, indent=2))
        return

    if parsed_args.only_launch:
        if not is_coppelia_running(parsed_args.host, parsed_args.port):
            launch_coppelia(headless=parsed_args.launch_headless)
        print(json.dumps({"success": True, "message": "CoppeliaSim is running and ready."}))
        return

    code_to_run = ""
    if parsed_args.code:
        code_to_run = parsed_args.code
    elif parsed_args.file:
        with open(parsed_args.file, "r") as f:
            code_to_run = f.read()
    else:
        # Check stdin
        if not sys.stdin.isatty():
            code_to_run = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(1)

    result = run_code(
        code=code_to_run,
        host=parsed_args.host,
        port=parsed_args.port,
        take_snapshot=not parsed_args.no_snapshot,
        reset=parsed_args.reset,
        auto_launch=parsed_args.launch or parsed_args.launch_headless,
        headless=parsed_args.launch_headless,
        diagnostics=parsed_args.diagnostics,
        timeout=parsed_args.timeout,
    )

    print(json.dumps(result, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
