"""Focused tests for synchronized sensor/state dataset recording."""

import json
import tempfile
import unittest
from pathlib import Path

from dataset_tools import (
    DEFAULT_MAX_SAMPLES,
    MAX_SAMPLE_LIMIT,
    record_dataset,
    validate_dataset_request,
)


class DatasetFakeSim:
    handle_all = -1
    sceneobject_joint = 1
    sceneobject_shape = 2
    sceneobject_dummy = 3
    sceneobject_visionsensor = 4
    sceneobject_forcesensor = 5
    sceneobject_proximitysensor = 6
    sceneobject_pointcloud = 7
    visionfloatparam_perspective_angle = 20
    stringparam_scene_name = 101
    stringparam_scene_path = 102
    simulation_stopped = 0

    def __init__(self):
        self.simulation_state = self.simulation_stopped
        self.time = 0.0
        self.dt = 0.05
        self.stepping = False
        self.start_calls = 0
        self.step_calls = 0
        self.object_positions = {
            "/Robot": [0.0, 0.0, 0.0],
            "/Robot/J1": [0.0, 0.0, 0.5],
            "/Robot/Camera": [0.1, 0.0, 0.8],
            "/Robot/Proximity": [0.2, 0.0, 0.3],
            "/Robot/Force": [0.0, 0.0, 0.1],
        }
        self.joint_positions = {2: 0.0}
        self.handles = {
            "/Robot": 1,
            "/Robot/J1": 2,
            "/Robot/Camera": 3,
            "/Robot/Proximity": 4,
            "/Robot/Force": 5,
        }
        self.types = {
            1: self.sceneobject_shape,
            2: self.sceneobject_joint,
            3: self.sceneobject_visionsensor,
            4: self.sceneobject_proximitysensor,
            5: self.sceneobject_forcesensor,
        }

    def getObject(self, path, _options=None):
        return self.handles.get(path, -1)

    def getObjectType(self, handle):
        return self.types.get(handle, self.sceneobject_shape)

    def getObjectPosition(self, handle, _relative):
        for path, h in self.handles.items():
            if h == handle:
                return list(self.object_positions[path])
        return [0.0, 0.0, 0.0]

    def getObjectQuaternion(self, handle, _relative):
        return [0.0, 0.0, 0.0, 1.0]

    def getJointPosition(self, handle):
        return self.joint_positions.get(handle, 0.0)

    def getSimulationState(self):
        return self.simulation_state

    def startSimulation(self):
        self.simulation_state = 1
        self.start_calls += 1

    def stopSimulation(self, _wait=True):
        self.simulation_state = self.simulation_stopped

    def setStepping(self, enabled):
        self.stepping = enabled

    def step(self):
        self.step_calls += 1
        self.time += self.dt
        self.object_positions["/Robot"][0] = round(self.object_positions["/Robot"][0] + 0.1, 6)
        if 2 in self.joint_positions:
            self.joint_positions[2] = round(self.joint_positions[2] + 0.05, 6)

    def getSimulationTime(self):
        return self.time

    def getSimulationTimeStep(self):
        return self.dt

    def getStringParam(self, param):
        if param == self.stringparam_scene_name:
            return "test_scene.ttt"
        if param == self.stringparam_scene_path:
            return "/tmp"
        return ""

    def handleVisionSensor(self, _handle):
        return None

    def getVisionSensorImg(self, _handle):
        return b"\x01\x02\x03" * 4, [2, 2]

    def getVisionSensorDepth(self, _handle, _options):
        return b"depth", [2, 2]

    def unpackFloatTable(self, _buffer):
        return [1.0, 1.5, 2.0, 2.5]

    def getObjectFloatParam(self, _handle, _parameter):
        return 1.04719755

    def readProximitySensor(self, _handle):
        dist = round(0.5 - self.step_calls * 0.01, 6)
        return True, dist, None, None, None

    def readForceSensor(self, _handle):
        return 1, [0.0, 0.0, round(9.81 + self.step_calls, 2)], [0.0, 0.0, 0.1]


class TestDatasetTools(unittest.TestCase):
    def test_invalid_inputs_rejected_without_simulator_mutation(self):
        invalid_cases = [
            {"steps": -1},
            {"steps": 0},
            {"steps": 10001},
            {"steps": True},
            {"sample_every": 0},
            {"sample_every": -2},
            {"max_samples": 0},
            {"max_samples": -5},
            {"max_samples": 20000},
            {"observe": ["invalid_rel_path"]},
            {"observe": "not_a_list"},
            {"sensors": ["not_a_dict"]},
            {"sensors": [{"path": "/Robot/Camera", "type": "unsupported_type"}]},
            {"sensors": [{"path": "relative/path", "type": "proximity"}]},
            {"export_path": "/tmp/test_export.txt"},
            {"export_path": "/nonexistent_folder/dataset.json"},
        ]

        for case in invalid_cases:
            with self.subTest(case=case):
                sim = DatasetFakeSim()
                result = record_dataset(sim, **case)
                self.assertFalse(result["success"])
                self.assertIn("error", result)
                self.assertEqual(sim.start_calls, 0)
                self.assertEqual(sim.step_calls, 0)
                self.assertEqual(sim.time, 0.0)
                self.assertFalse(sim.stepping)

    def test_missing_objects_or_sensors_rejected_before_mutation(self):
        sim = DatasetFakeSim()
        result = record_dataset(sim, steps=5, observe=["/Nonexistent/Object"])
        self.assertFalse(result["success"])
        self.assertIn("Object not found", result["error"])
        self.assertEqual(sim.start_calls, 0)
        self.assertEqual(sim.step_calls, 0)
        self.assertFalse(sim.stepping)

        sim = DatasetFakeSim()
        result = record_dataset(sim, steps=5, sensors=[{"path": "/Nonexistent/Sensor", "type": "proximity"}])
        self.assertFalse(result["success"])
        self.assertIn("Sensor object not found", result["error"])
        self.assertEqual(sim.start_calls, 0)
        self.assertEqual(sim.step_calls, 0)
        self.assertFalse(sim.stepping)

        sim = DatasetFakeSim()
        result = record_dataset(sim, steps=5, sensors=[{"path": "/Robot", "type": "proximity"}])
        self.assertFalse(result["success"])
        self.assertIn("requires an object of type", result["error"])
        self.assertEqual(sim.start_calls, 0)
        self.assertEqual(sim.step_calls, 0)
        self.assertFalse(sim.stepping)

    def test_sync_sample_alignment_and_sensor_payloads(self):
        sim = DatasetFakeSim()
        sensors = [
            {"path": "/Robot/Proximity", "type": "proximity"},
            {"path": "/Robot/Force", "type": "force_torque"},
            {"path": "/Robot/Camera", "type": "vision_rgb"},
            {"path": "/Robot/Camera", "type": "vision_depth"},
            {"path": "/Robot/Camera", "type": "point_cloud", "max_points": 4},
        ]
        observe = ["/Robot", "/Robot/J1"]

        result = record_dataset(sim, steps=3, sample_every=1, observe=observe, sensors=sensors)
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["steps_run"], 3)
        self.assertEqual(result["summary"]["sample_count"], 3)
        self.assertEqual(result["summary"]["stopped_by"], "steps")
        self.assertEqual(result["summary"]["final_time"], 0.15)
        self.assertFalse(sim.stepping)

        # Verify metadata
        self.assertEqual(result["metadata"]["scene"].get("scene_name"), "test_scene.ttt")
        self.assertEqual(result["metadata"]["simulation_time_step"], 0.05)

        # Verify lockstep synchronization across steps
        for step_idx, sample in enumerate(result["samples"], start=1):
            expected_time = round(step_idx * 0.05, 6)
            self.assertEqual(sample["step"], step_idx)
            self.assertEqual(sample["timestamp"], expected_time)
            self.assertEqual(sample["time"], expected_time)

            # Robot state aligned to step
            expected_robot_x = round(step_idx * 0.1, 6)
            self.assertEqual(sample["state"]["positions"]["/Robot"][0], expected_robot_x)
            expected_joint_pos = round(step_idx * 0.05, 6)
            self.assertEqual(sample["state"]["joints"]["/Robot/J1"], expected_joint_pos)

            # Sensors aligned to step
            sensor_map = {f"{s['path']}:{s['type']}": s for s in sample["sensors"]}
            self.assertIn("/Robot/Proximity:proximity", sensor_map)
            self.assertIn("/Robot/Force:force_torque", sensor_map)
            self.assertIn("/Robot/Camera:vision_rgb", sensor_map)
            self.assertIn("/Robot/Camera:vision_depth", sensor_map)
            self.assertIn("/Robot/Camera:point_cloud", sensor_map)

            expected_prox_dist = round(0.5 - step_idx * 0.01, 6)
            self.assertEqual(sensor_map["/Robot/Proximity:proximity"]["distance_m"], expected_prox_dist)
            self.assertEqual(sensor_map["/Robot/Force:force_torque"]["force_n"][2], round(9.81 + step_idx, 2))
            self.assertEqual(sensor_map["/Robot/Camera:vision_rgb"]["encoding"], "rgb8_base64")
            self.assertEqual(sensor_map["/Robot/Camera:vision_depth"]["encoding"], "float32_meters")
            self.assertEqual(len(sensor_map["/Robot/Camera:point_cloud"]["points"]), 4)

    def test_stepping_mode_restored_on_simulation_exception(self):
        sim = DatasetFakeSim()

        def faulty_step():
            raise RuntimeError("Simulation stepped error")

        sim.step = faulty_step

        result = record_dataset(sim, steps=5, observe=["/Robot"])
        self.assertFalse(result["success"])
        self.assertIn("Simulation stepped error", result["error"])
        self.assertFalse(sim.stepping)

    def test_json_export(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            export_path = temp_file.name

        try:
            sim = DatasetFakeSim()
            result = record_dataset(
                sim,
                steps=2,
                sample_every=1,
                observe=["/Robot"],
                sensors=[{"path": "/Robot/Proximity", "type": "proximity"}],
                export_path=export_path,
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["export_path"], export_path)

            exported_data = json.loads(Path(export_path).read_text())
            self.assertTrue(exported_data["success"])
            self.assertEqual(exported_data["summary"]["sample_count"], 2)
            self.assertEqual(exported_data["samples"][0]["sensors"][0]["path"], "/Robot/Proximity")
        finally:
            Path(export_path).unlink(missing_ok=True)

    def test_sample_every_and_early_stop_on_max_samples(self):
        sim = DatasetFakeSim()
        # steps=6, sample_every=2 -> step 2, 4, 6
        result = record_dataset(sim, steps=6, sample_every=2, observe=["/Robot"])
        self.assertTrue(result["success"])
        sampled_steps = [s["step"] for s in result["samples"]]
        self.assertEqual(sampled_steps, [2, 4, 6])

        # max_samples stops early when reached
        sim = DatasetFakeSim()
        result = record_dataset(sim, steps=10, sample_every=2, max_samples=3, observe=["/Robot"])
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["stopped_by"], "max_samples")
        self.assertEqual(len(result["samples"]), 3)
        self.assertEqual([s["step"] for s in result["samples"]], [2, 4, 6])


if __name__ == "__main__":
    unittest.main()
