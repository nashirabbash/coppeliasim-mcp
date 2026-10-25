"""JSON event logger; writes to stderr so MCP stdout stays clean."""

import json
import sys
from datetime import datetime, timezone

LEVELS = ("debug", "info", "success", "error")


def log(level: str, event: str, **fields) -> None:
    if level not in LEVELS:
        raise ValueError(f"Unsupported log level: {level}")
    record = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "event": event, **fields}
    print(json.dumps(record, default=str), file=sys.stderr, flush=True)
