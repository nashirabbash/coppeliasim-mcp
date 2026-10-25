"""Read and write typed CoppeliaSim signals."""

from math import isfinite
from .json_log import log


SIGNAL_TYPES = {
    "integer": ("getInt32Signal", "setInt32Signal"),
    "float": ("getFloatSignal", "setFloatSignal"),
    "string": ("getStringSignal", "setStringSignal"),
}


def operate_signal(sim, operation, signal_type, name, value=None):
    if operation not in ("get", "set"):
        raise ValueError("operation must be 'get' or 'set'")
    if signal_type not in SIGNAL_TYPES:
        raise ValueError("signal_type must be 'integer', 'float', or 'string'")
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")

    getter, setter = SIGNAL_TYPES[signal_type]
    if operation == "get":
        result = getattr(sim, getter)(name)
        log("info", "signals.read", name=name, signal_type=signal_type, found=result is not None)
        return {"success": True, "operation": operation, "name": name, "signal_type": signal_type, "value": result, "found": result is not None}

    if signal_type == "integer" and (
        not isinstance(value, int) or isinstance(value, bool) or not -(2**31) <= value < 2**31
    ):
        raise ValueError("integer signal value must fit a signed 32-bit integer")
    if signal_type == "float" and (
        not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value)
    ):
        raise ValueError("float signal value must be finite")
    if signal_type == "string" and not isinstance(value, str):
        raise ValueError("string signal value must be a string")
    getattr(sim, setter)(name, value)
    log("success", "signals.written", name=name, signal_type=signal_type)
    return {"success": True, "operation": operation, "name": name, "signal_type": signal_type, "value": value}
