#!/usr/bin/env python3
"""Root compatibility launcher for CoppeliaSim MCP Server."""
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
if str(DIR) not in sys.path:
    sys.path.insert(0, str(DIR))

from coppeliasim_mcp.coppelia_mcp import *

if __name__ == "__main__":
    main()
