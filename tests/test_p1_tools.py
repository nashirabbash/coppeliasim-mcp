import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coppeliasim_mcp.experiment_tools import run_experiments, validate_experiments
from coppeliasim_mcp.mechanism_tools import inspect_mechanism
from coppeliasim_mcp.sensor_tools import read_one


class FakeSim:
    handle_all = -1
    sceneobject_joint = 1
    sceneobject_shape = 2
    sceneobject_dummy = 3
    sceneobject_visionsensor = 4
    sceneobject_forcesensor = 5
    sceneobject_proximitysensor = 6
    sceneobject_pointcloud = 7
    joint_revolute = 10
    joint_prismatic = 11
    joint_spherical = 12
    visionfloatparam_perspective_angle = 20
    simulation_stopped = 0

    def __init__(self):
        self.simulation_state = self.simulation_stopped
        self.resets = 0
        self.scene_loads = []
        self.handle_epoch = 0
        self.time = 0.0
        self.stepping = False
        self.joint_applied_while_stopped = None
        self.joint_applied_while_running = False
        self.collision_detected = False
        self.initial_positions = {"/Robot": [0.0, 0.0, 0.0], "/Robot/Tip": [0.0, 0.0, 0.0], "/Other": [1.0, 1.0, 1.0]}
        self.object_positions = {k: list(v) for k, v in self.initial_positions.items()}
        self.joint_positions = {}
        self.joint_targets = {}

    def loadScene(self, path):
        if self.simulation_state != self.simulation_stopped:
            raise RuntimeError("loadScene requires simulation to be stopped")
        self.scene_loads.append(path)
        self.handle_epoch += 10
        self.object_positions = {k: list(v) for k, v in self.initial_positions.items()}
        self.time = 0.0
        self.simulation_state = self.simulation_stopped

    def getObject(self, path, _options=None):
        base_handles = {"/Robot": 1, "/Robot/J1": 2, "/Robot/Tip": 3, "/Robot/Camera": 4, "/Robot/Proximity": 5, "/Other": 6}
        if path not in base_handles:
            return -1
        return base_handles[path] + self.handle_epoch

    def getObjectType(self, handle):
        base = handle - self.handle_epoch if (handle - self.handle_epoch) in {1, 2, 3, 4, 5, 6} else handle
        types = {1: self.sceneobject_shape, 2: self.sceneobject_joint, 3: self.sceneobject_dummy, 4: self.sceneobject_visionsensor, 5: self.sceneobject_proximitysensor, 6: self.sceneobject_shape}
        return types.get(base, self.sceneobject_shape)

    def getObjectsInTree(self, _root, _kind, _options=None):
        return [1 + self.handle_epoch, 2 + self.handle_epoch, 3 + self.handle_epoch, 4 + self.handle_epoch, 5 + self.handle_epoch]

    def getObjectParent(self, handle):
        return 1 + self.handle_epoch if (handle - self.handle_epoch) > 1 else -1

    def getObjectAlias(self, handle, _options=0):
        base = handle - self.handle_epoch if (handle - self.handle_epoch) in {1, 2, 3, 4, 5, 6} else handle
        aliases = {1: "/Robot", 2: "/Robot/J1", 3: "/Robot/Tip", 4: "/Robot/Camera", 5: "/Robot/Proximity", 6: "/Other"}
        return aliases.get(base, f"/Obj{handle}")

    def getObjectPosition(self, handle, _relative):
        alias = self.getObjectAlias(handle)
        return list(self.object_positions.get(alias, [0.0, 0.0, 0.0]))

    def getJointType(self, _handle):
        return self.joint_revolute

    def getJointInterval(self, _handle):
        return False, [-1.0, 2.0]

    def getJointTargetPosition(self, handle):
        return self.joint_targets.get(handle, 0.25)

    def getObjectQuaternion(self, _handle, _relative):
        return [0.0, 0.0, 0.0, 1.0]

    def getJointPosition(self, handle):
        return self.joint_positions.get(handle, 0.2)

    def setJointPosition(self, handle, position):
        if self.simulation_state == self.simulation_stopped:
            self.joint_applied_while_stopped = True
        else:
            self.joint_applied_while_running = True
        self.joint_positions[handle] = position

    def setJointTargetPosition(self, handle, position):
        self.joint_targets[handle] = position

    def getSimulationState(self):
        return self.simulation_state

    def stopSimulation(self, _wait=True):
        self.simulation_state = self.simulation_stopped

    def startSimulation(self):
        self.simulation_state = 1
        self.resets += 1

    def setStepping(self, enabled):
        self.stepping = enabled

    def step(self):
        self.time += 0.05
        self.object_positions["/Robot"][0] += 0.1

    def handleVisionSensor(self, _handle):
        return None

    def getVisionSensorDepth(self, _handle, _options):
        return b"depth", [2, 2]

    def unpackFloatTable(self, _buffer):
        return [1.0, 2.0, 3.0, 4.0]

    def getObjectFloatParam(self, _handle, _parameter):
        return 1.5707963267948966

    def getSimulationTime(self):
        return self.time

    def readProximitySensor(self, _handle):
        return True, 0.125, None, None, None

    def checkCollision(self, _handle1, _handle2):
        return [self.collision_detected]


class TestP1Tools(unittest.TestCase):
    def setUp(self):
        self.temp_scene = tempfile.NamedTemporaryFile(suffix=".ttt", delete=False)
        self.scene_path = self.temp_scene.name
        self.temp_scene.close()

    def tearDown(self):
        Path(self.scene_path).unlink(missing_ok=True)

    def test_proximity_sensor_returns_typed_distance(self):
        result = read_one(FakeSim(), {"path": "/Robot/Proximity", "type": "proximity"})
        self.assertEqual(result["distance_m"], 0.125)
        self.assertTrue(result["detected"])

    def test_mechanism_inspection_reports_control_ready_joint_and_candidates(self):
        result = inspect_mechanism(FakeSim(), "/Robot")
        self.assertEqual(result["base_candidate"], "/Robot")
        self.assertEqual(result["joints"][0]["type"], "revolute")
        self.assertEqual(result["joints"][0]["limits"], [-1.0, 1.0])
        self.assertEqual(result["end_effector_candidates"], ["/Robot/Tip"])
        self.assertEqual(result["sensors"][0]["type"], "vision")

    def test_mechanism_handles_spherical_joints_without_scalar_limits(self):
        class SphericalSim(FakeSim):
            def getJointType(self, _handle):
                return self.joint_spherical

            def getJointInterval(self, _handle):
                raise AssertionError("spherical joints have no scalar interval")

        result = inspect_mechanism(SphericalSim(), "/Robot")
        self.assertEqual(result["joints"][0]["unit"], "quaternion")
        self.assertIsNone(result["joints"][0]["limits"])
        self.assertEqual(result["joints"][0]["orientation_quaternion"], [0.0, 0.0, 0.0, 1.0])

    def test_point_cloud_is_metric_and_respects_point_cap(self):
        result = read_one(FakeSim(), {"path": "/Robot/Camera", "type": "point_cloud", "max_points": 2})
        self.assertLessEqual(len(result["points"]), 2)
        self.assertEqual(result["points"][0]["xyz_m"][2], 1.0)

    def test_experiment_budget_rejects_batch_before_simulation(self):
        with self.assertRaisesRegex(ValueError, "combined episode steps"):
            validate_experiments(
                self.scene_path,
                [
                    {"steps": 6000, "success_conditions": [{"kind": "proximity", "sensor": "/Robot/Proximity", "detected": True}]},
                    {"steps": 5000, "success_conditions": [{"kind": "proximity", "sensor": "/Robot/Proximity", "detected": True}]},
                ],
                [],
                [],
                1,
            )

    def test_experiment_invalid_input_rejected_before_scene_mutation(self):
        sim = FakeSim()
        with patch("coppeliasim_mcp.experiment_tools.connect_sim", return_value=(object(), sim)):
            result = run_experiments(
                self.scene_path,
                [{"name": "invalid", "steps": 10, "joint_positions": {"/Robot/J1": True}, "success_conditions": [{"kind": "proximity", "sensor": "/Robot/Proximity", "detected": True}]}],
            )
        self.assertFalse(result["success"])
        self.assertEqual(len(sim.scene_loads), 0)

    def test_experiment_reload_resets_leaked_state_and_applies_joint_pre_start(self):
        sim = FakeSim()
        with patch("coppeliasim_mcp.experiment_tools.connect_sim", return_value=(object(), sim)):
            result = run_experiments(
                self.scene_path,
                [
                    {
                        "name": "ep1",
                        "steps": 3,
                        "joint_positions": {"/Robot/J1": 0.5},
                        "success_conditions": [{"kind": "object_position", "object": "/Robot", "position": [0.3, 0.0, 0.0], "tolerance": 0.01}],
                    },
                    {
                        "name": "ep2",
                        "steps": 2,
                        "joint_positions": {"/Robot/J1": -0.2},
                        "success_conditions": [{"kind": "object_position", "object": "/Robot", "position": [0.2, 0.0, 0.0], "tolerance": 0.01}],
                    },
                ],
                observe=["/Robot"],
            )
        self.assertTrue(result["success"])
        self.assertEqual(len(sim.scene_loads), 2)
        self.assertEqual(sim.resets, 2)
        self.assertTrue(sim.joint_applied_while_stopped)
        self.assertFalse(sim.joint_applied_while_running)
        self.assertEqual(result["summary"]["successful_episodes"], 2)
        self.assertEqual(result["episodes"][1]["initial_state"]["positions"]["/Robot"], [0.0, 0.0, 0.0])

    def test_experiment_task_assertion_failure_marks_episode_false_on_full_steps(self):
        sim = FakeSim()
        with patch("coppeliasim_mcp.experiment_tools.connect_sim", return_value=(object(), sim)):
            result = run_experiments(
                self.scene_path,
                [
                    {
                        "name": "failed-target",
                        "steps": 3,
                        "success_conditions": [{"kind": "object_position", "object": "/Robot", "position": [10.0, 10.0, 10.0], "tolerance": 0.01}],
                    }
                ],
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["episodes"][0]["stopped_by"], "steps")
        self.assertFalse(result["episodes"][0]["success"])
        self.assertFalse(result["episodes"][0]["success_checks"][0]["success"])
        self.assertEqual(result["summary"]["successful_episodes"], 0)
        self.assertEqual(result["summary"]["failed_episodes"], 1)

    def test_experiment_sensor_check_validates_proximity_sensor_type(self):
        sim = FakeSim()
        with patch("coppeliasim_mcp.experiment_tools.connect_sim", return_value=(object(), sim)):
            result = run_experiments(
                self.scene_path,
                [
                    {
                        "name": "bad-sensor",
                        "steps": 3,
                        "success_conditions": [{"kind": "proximity", "sensor": "/Robot/Camera", "detected": True}],
                    }
                ],
            )
        self.assertFalse(result["success"])
        self.assertIn("Sensor is not a proximity sensor", result["error"])

    def test_experiment_diagnostic_stop_marks_episode_failure(self):
        sim = FakeSim()
        sim.collision_detected = True
        with patch("coppeliasim_mcp.experiment_tools.connect_sim", return_value=(object(), sim)), patch(
            "coppeliasim_mcp.experiment_tools.get_floor_info", return_value={"bounds_x": [-5, 5], "bounds_y": [-5, 5]}
        ):
            result = run_experiments(
                self.scene_path,
                [
                    {
                        "name": "collision-episode",
                        "steps": 5,
                        "until": {"kind": "collision", "objects": ["/Robot", "/Robot/Tip"]},
                        "success_conditions": [{"kind": "proximity", "sensor": "/Robot/Proximity", "detected": True}],
                    }
                ],
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["episodes"][0]["stopped_by"], "condition")
        self.assertFalse(result["episodes"][0]["success"])

    def test_experiments_require_an_explicit_task_assertion(self):
        for conditions in (None, []):
            with self.subTest(conditions=conditions), self.assertRaises(ValueError):
                validate_experiments(
                    self.scene_path, [{"steps": 2, "success_conditions": conditions}], [], [], 1
                )


if __name__ == "__main__":
    unittest.main()
