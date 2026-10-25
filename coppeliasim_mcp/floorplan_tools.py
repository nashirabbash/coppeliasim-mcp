"""Build static scene geometry from grayscale floor-plan pixels."""

from math import isfinite
from pathlib import Path

from .json_log import log

MAX_PIXELS = 1_000_000


def _validate_range(value, name):
    if not isinstance(value, list) or len(value) != 2 or any(not isinstance(v, int) or isinstance(v, bool) for v in value):
        raise ValueError(f"{name} must be a two-integer [minimum, maximum] range")
    low, high = value
    if not 0 <= low <= high <= 255:
        raise ValueError(f"{name} values must be between 0 and 255")
    return low, high


def import_floorplan(sim, image_path, pixel_size, wall_height, door_height, window_height, wall_range, door_range, window_range, respondable=True):
    source = Path(image_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Floor-plan image not found: {source}")
    values = (pixel_size, wall_height, door_height, window_height)
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v) or v <= 0 for v in values):
        raise ValueError("pixel_size and geometry heights must be finite positive numbers")
    if not isinstance(respondable, bool):
        raise ValueError("respondable must be a boolean")
    classes = [
        ("wall", _validate_range(wall_range, "wall_range"), float(wall_height)),
        ("door", _validate_range(door_range, "door_range"), float(door_height)),
        ("window", _validate_range(window_range, "window_range"), float(window_height)),
    ]
    for index, (_, (low, high), _) in enumerate(classes):
        if any(max(low, other_low) <= min(high, other_high) for _, (other_low, other_high), _ in classes[index + 1:]):
            raise ValueError("wall_range, door_range, and window_range must not overlap")

    from PIL import Image
    with Image.open(source) as image:
        width, height = image.size
        if width * height > MAX_PIXELS:
            raise ValueError(f"Floor-plan image must contain at most {MAX_PIXELS} pixels")
        grayscale = image.convert("L")
        pixels = grayscale.load()
        runs = []
        for y in range(height):
            x = 0
            while x < width:
                kind = next((item for item in classes if item[1][0] <= pixels[x, y] <= item[1][1]), None)
                if kind is None:
                    x += 1
                    continue
                end = x + 1
                while end < width and kind[1][0] <= pixels[end, y] <= kind[1][1]:
                    end += 1
                runs.append((kind[0], x, y, end - x, kind[2]))
                x = end

    if len(runs) > 10000:
        raise ValueError("Floor-plan image creates too many geometry segments (maximum 10000)")
    created = []
    try:
        for kind, x, y, run_width, segment_height in runs:
            handle = sim.createPrimitiveShape(sim.primitiveshape_cuboid, [run_width * pixel_size, pixel_size, segment_height], 0)
            created.append({"handle": handle, "kind": kind})
            sim.setObjectPosition(handle, -1, [(x + run_width / 2) * pixel_size, (height - y - 0.5) * pixel_size, segment_height / 2])
            sim.setObjectInt32Param(handle, sim.shapeintparam_static, 1)
            if respondable:
                sim.setObjectInt32Param(handle, sim.shapeintparam_respondable, 1)
    except Exception:
        for item in created:
            sim.removeObject(item["handle"])
        raise

    counts = {kind: sum(item["kind"] == kind for item in created) for kind, _, _ in classes}
    log("success", "floorplan.import_completed", path=str(source), width=width, height=height, segment_count=len(created))
    return {"success": True, "path": str(source), "image_size": [width, height], "pixel_size": float(pixel_size), "segment_count": len(created), "segments_by_kind": counts, "respondable": bool(respondable)}
