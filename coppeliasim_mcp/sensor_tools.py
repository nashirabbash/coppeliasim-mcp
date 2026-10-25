"""Typed observations from CoppeliaSim sensor objects."""

import base64
import math

from .json_log import log

SENSOR_TYPES = {"proximity", "vision_rgb", "vision_depth", "force_torque", "point_cloud"}
SENSOR_OBJECT_TYPES = {
    "proximity": "sceneobject_proximitysensor",
    "vision_rgb": "sceneobject_visionsensor",
    "vision_depth": "sceneobject_visionsensor",
    "force_torque": "sceneobject_forcesensor",
    "point_cloud": "sceneobject_visionsensor",
}
MAX_POINT_CLOUD_POINTS = 100_000


def _resolve(sim, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Sensor paths must be absolute CoppeliaSim paths")
    handle = sim.getObject(path, {"noError": True})
    if handle == -1:
        raise ValueError(f"Object not found: {path}")
    return handle


def _point_cloud(sim, handle, max_points):
    sim.handleVisionSensor(handle)
    depth_bytes, resolution = sim.getVisionSensorDepth(handle, 1)
    width, height = resolution
    depths = sim.unpackFloatTable(depth_bytes)
    if len(depths) != width * height:
        raise ValueError("Vision sensor depth buffer size does not match its resolution")
    fov = sim.getObjectFloatParam(handle, sim.visionfloatparam_perspective_angle)
    if not math.isfinite(fov) or not 0 < fov < math.pi:
        raise ValueError("Vision sensor perspective angle must be between 0 and pi")
    points = []
    stride = max(1, math.ceil(math.sqrt(width * height / max_points)))
    scale = 2 * math.tan(fov / 2) / width
    while math.ceil(width / stride) * math.ceil(height / stride) > max_points:
        stride += 1
    for y in range(0, height, stride):
        for x in range(0, width, stride):
            depth = float(depths[y * width + x])
            if math.isfinite(depth) and depth > 0:
                points.append({
                    "pixel": [x, y],
                    "xyz_m": [round((x + 0.5 - width / 2) * depth * scale, 6),
                              round((height / 2 - y - 0.5) * depth * scale, 6),
                              round(depth, 6)]
                })
    return {"resolution": [width, height], "frame": "camera_optical_x_right_y_up_z_forward", "points": points, "pixel_stride": stride}


def read_one(sim, sensor):
    if not isinstance(sensor, dict):
        raise ValueError("Each sensor request must be an object with path and type")
    path, kind = sensor.get("path"), sensor.get("type")
    if kind not in SENSOR_TYPES:
        raise ValueError(f"Unsupported sensor type: {kind}")
    handle = _resolve(sim, path)
    expected_type = getattr(sim, SENSOR_OBJECT_TYPES[kind], None)
    if expected_type is None or sim.getObjectType(handle) != expected_type:
        raise ValueError(f"{kind} requires an object of type {SENSOR_OBJECT_TYPES[kind]}: {path}")
    if kind == "proximity":
        detected, distance, *_ = sim.readProximitySensor(handle)
        result = {"detected": bool(detected), "distance_m": round(distance, 6) if detected else None}
    elif kind == "force_torque":
        status, force, torque = sim.readForceSensor(handle)
        result = {"available": bool(status & 1), "force_n": force, "torque_nm": torque}
    elif kind == "vision_rgb":
        sim.handleVisionSensor(handle)
        image, resolution = sim.getVisionSensorImg(handle)
        result = {"resolution": resolution, "encoding": "rgb8_base64", "data": base64.b64encode(image).decode("ascii")}
    elif kind == "vision_depth":
        sim.handleVisionSensor(handle)
        depth_bytes, resolution = sim.getVisionSensorDepth(handle, 1)
        result = {"resolution": resolution, "encoding": "float32_meters", "values": sim.unpackFloatTable(depth_bytes)}
    else:
        maximum = sensor.get("max_points", 4096)
        if not isinstance(maximum, int) or not 1 <= maximum <= MAX_POINT_CLOUD_POINTS:
            raise ValueError(f"max_points must be an integer between 1 and {MAX_POINT_CLOUD_POINTS}")
        result = _point_cloud(sim, handle, maximum)
    return {"path": path, "type": kind, **result}


def read_sensors(sim, sensors):
    if not isinstance(sensors, list) or not sensors:
        raise ValueError("sensors must be a non-empty list")
    readings = [read_one(sim, sensor) for sensor in sensors]
    log("success", "sensors.read", count=len(readings), types=[item["type"] for item in readings])
    return {"success": True, "readings": readings}
