import math
import unittest

from coppeliasim_mcp.trajectory_tools import execute_trajectory
from coppeliasim_mcp.grasp_checks import measure_contact


def grasp_config():
    return {
        "object": "/part", "gripper": "/gripper", "min_normal_force": 1.0,
        "hold_until_waypoint": 1, "min_lift": 0.1, "max_slip": 0.01, "max_rotation_rad": 0.1,
        "wrench_sweep": {"force_n": 0.2, "torque_nm": 0.02, "steps_per_direction": 2},
    }


class FakeSim:
    simulation_stopped = 0
    handle_all = -1
    sceneobject_shape = 2
    def __init__(self, collision=False, lose_contact=False):
        self.handles = {"/joint": 1, "/gripper": 2, "/part": 3, "/tip": 4, "/target": 5, "/robot": 6, "/wall": 7}
        self.positions = {1: 0.0, 2: 0.0}
        self.targets, self.stepping, self.stopped = {}, False, True
        self.collision, self.lose_contact, self.steps = collision, lose_contact, 0
        self.applied_wrenches = []
    def getObjectQuaternion(self, _handle, _relative):
        return [0.0, 0.0, 0.0, 1.0]
    def addForceAndTorque(self, handle, force, torque):
        self.applied_wrenches.append((handle, force, torque))
    def getObject(self, path, _options):
        return self.handles.get(path, -1)
    def getObjectsInTree(self, _root, _kind, _options):
        return [2]
    def getObjectType(self, _handle):
        return self.sceneobject_shape
    def getObjectPosition(self, _handle, relative):
        return [0.0, 0.0, 0.0 if relative != -1 else self.positions[1]]
    def getJointInterval(self, _handle):
        return False, [-1.0, 2.0]
    def getSimulationTimeStep(self):
        return 0.1
    def getJointPosition(self, handle):
        return self.positions.get(handle, 0.0)
    def getSimulationState(self):
        return self.simulation_stopped if self.stopped else 1
    def setStepping(self, enabled):
        self.stepping = enabled
    def startSimulation(self):
        self.stopped = False
    def stopSimulation(self, _wait=False):
        self.stopped = True
    def setJointTargetPosition(self, handle, position):
        self.targets[handle] = position
    def step(self):
        self.positions.update(self.targets)
        self.steps += 1
    def checkCollision(self, _first, _second):
        return self.collision, None
    def checkDistance(self, _first, _second):
        return True, [0, 0, 0, 0, 0, 0, 0.01], None
    def getContactInfo(self, _pass, _shape, index):
        if index or self.lose_contact and self.steps >= 4:
            return [], [], [], []
        return [2, 3], [0, 0, 0], [0, 0, 2], [0, 0, 1]

class TrajectoryTests(unittest.TestCase):
    def test_executes_path_and_verifies_dynamic_grasp_contact_through_lift(self):
        sim = FakeSim()
        result = execute_trajectory(
            sim,
            ["/joint"],
            [[0.2], [0.4]],
            collision_pairs=[["/robot", "/wall"]],
            max_velocity=[1.0],
            steps_per_waypoint=2,
            gripper_actions=[
                {"waypoint": 0, "joint": "/gripper", "position": 0.5, "grasp": grasp_config()},
                {"waypoint": 1, "joint": "/gripper", "position": 0.0, "place": {"object": "/part", "target": "/target", "max_distance": 0.05}},
            ],
        )
        self.assertEqual(result["steps_run"], 40)
        self.assertEqual(result["final_positions"], [0.4])
        self.assertEqual(result["gripper_results"][0]["grasp"]["normal_force"], 2.0)
        self.assertTrue(result["gripper_results"][0]["grasp"]["hold_verified"])
        sweep = result["gripper_results"][0]["grasp"]["wrench_resistance_test"]
        self.assertEqual(sweep["direction_count"], 12)
        self.assertTrue(sweep["passed"])
        self.assertFalse(sweep["analytic_force_closure_proven"])
        self.assertEqual(len(sim.applied_wrenches), 24)

        self.assertTrue(result["gripper_results"][1]["place"]["success"])
        self.assertFalse(sim.stepping)

    def test_fails_when_contact_is_lost_during_lift(self):
        sim = FakeSim(lose_contact=True)
        with self.assertRaisesRegex(RuntimeError, "Grasp contact lost"):
            execute_trajectory(
                sim,
                ["/joint"],
                [[0.2], [0.4]],
                collision_pairs=[["/robot", "/wall"]],
                max_velocity=[1.0],
                steps_per_waypoint=2,
                gripper_actions=[
                    {"waypoint": 0, "joint": "/gripper", "position": 0.5, "grasp": grasp_config()},
                ],
            )
        self.assertFalse(sim.stepping)
        self.assertTrue(sim.stopped)

    def test_contact_without_lift_is_not_a_successful_grasp(self):
        sim = FakeSim()
        with self.assertRaisesRegex(RuntimeError, "Grasp lift check failed"):
            execute_trajectory(
                sim, ["/joint"], [[0.0], [0.0]],
                collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], steps_per_waypoint=2,
                gripper_actions=[{"waypoint": 0, "joint": "/gripper", "position": 0.5,
                                  "grasp": {**grasp_config()}}],
            )
        self.assertTrue(sim.stopped)

    def test_post_lift_dwell_rejects_contact_loss_and_relative_slip(self):
        class UnstableSim(FakeSim):
            def getContactInfo(self, dynamic_pass, shape, index):
                if failure == "contact" and self.steps >= 6:
                    return [], [], [], []
                return super().getContactInfo(dynamic_pass, shape, index)

            def getObjectQuaternion(self, handle, relative):
                if failure == "rotation" and self.steps >= 6:
                    return [0.0, 0.0, 0.2, math.sqrt(0.96)]
                return super().getObjectQuaternion(handle, relative)

            def getObjectPosition(self, handle, relative):
                if failure == "slip" and self.steps >= 6 and relative != -1:
                    return [0.02, 0, 0]
                return super().getObjectPosition(handle, relative)


        for failure in ("contact", "slip"):
            with self.subTest(failure=failure):
                sim = UnstableSim()
                with self.assertRaisesRegex(RuntimeError, "Grasp contact lost or slip exceeded"):
                    execute_trajectory(
                        sim, ["/joint"], [[0.2], [0.4]],
                        collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], steps_per_waypoint=2,
                        gripper_actions=[{"waypoint": 0, "joint": "/gripper", "position": 0.5,
                                          "grasp": grasp_config()}],
                    )
                self.assertTrue(sim.stopped)
    def test_post_lift_rotation_is_rejected(self):
        class RotatingSim(FakeSim):
            def getObjectQuaternion(self, handle, relative):
                if self.steps >= 6:
                    return [0.0, 0.0, 0.2, math.sqrt(0.96)]
                return super().getObjectQuaternion(handle, relative)

        with self.assertRaisesRegex(RuntimeError, "Grasp rotational slip exceeded"):
            execute_trajectory(
                RotatingSim(), ["/joint"], [[0.2], [0.4]],
                collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], steps_per_waypoint=2,
                gripper_actions=[{"waypoint": 0, "joint": "/gripper", "position": 0.5,
                                  "grasp": grasp_config()}],
            )


    def test_tangential_force_or_missing_contact_does_not_prove_grasp(self):
        class TangentialSim(FakeSim):
            def getContactInfo(self, _pass, _shape, index):
                if index:
                    return [], [], [], []
                return [2, 3], [0, 0, 0], [10, 0, 0], [0, 0, 1]

        sim = TangentialSim()
        self.assertFalse(measure_contact(sim, 3, [2], 0.1)["success"])
        self.assertFalse(measure_contact(sim, 99, [2], 0.1)["success"])

    def test_rejects_velocity_before_advancing_simulation(self):
        sim = FakeSim()
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[0.5], steps_per_waypoint=2)
        self.assertEqual(sim.steps, 0)
        self.assertTrue(sim.stopped)

    def test_collision_stops_simulation(self):
        sim = FakeSim(collision=True)
        with self.assertRaisesRegex(RuntimeError, "Collision detected"):
            execute_trajectory(sim, ["/joint"], [[0.1]], collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0])
        self.assertTrue(sim.stopped)
        self.assertFalse(sim.stepping)

    def test_smooth_trajectory_rejects_invalid_inputs(self):
        sim = FakeSim()
        for bad in ("fast", 1.0, [-1.0], [0.0], [float("nan")], [float("inf")], [1.0, 2.0]):
            with self.subTest(bad_acc=bad):
                with self.assertRaisesRegex(ValueError, "max_acceleration must contain one finite positive limit per joint"):
                    execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], max_acceleration=bad)
            with self.subTest(bad_jerk=bad):
                with self.assertRaisesRegex(ValueError, "max_jerk must contain one finite positive limit per joint"):
                    execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], max_jerk=bad)
        self.assertEqual(sim.steps, 0)
        self.assertTrue(sim.stopped)

    def test_smooth_trajectory_rejects_velocity_envelope(self):
        sim = FakeSim()
        with self.assertRaisesRegex(ValueError, "requested velocity .* exceeds limit"):
            execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[0.4], max_acceleration=[5.0], max_jerk=[20.0], steps_per_waypoint=10)
        self.assertEqual(sim.steps, 0)
        self.assertTrue(sim.stopped)

    def test_smooth_trajectory_rejects_acceleration_envelope(self):
        sim = FakeSim()
        with self.assertRaisesRegex(ValueError, "requested acceleration .* exceeds limit"):
            execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], max_acceleration=[1.0], max_jerk=[20.0], steps_per_waypoint=10)
        self.assertEqual(sim.steps, 0)
        self.assertTrue(sim.stopped)

    def test_smooth_trajectory_rejects_jerk_envelope(self):
        sim = FakeSim()
        with self.assertRaisesRegex(ValueError, "requested jerk .* exceeds limit"):
            execute_trajectory(sim, ["/joint"], [[0.2]], collision_pairs=[["/robot", "/wall"]], max_velocity=[1.0], max_acceleration=[5.0], max_jerk=[5.0], steps_per_waypoint=10)
        self.assertEqual(sim.steps, 0)
        self.assertTrue(sim.stopped)

    def test_smooth_trajectory_executes_within_kinematic_bounds(self):
        class TrackingSim(FakeSim):
            def __init__(self):
                super().__init__()
                self.commanded_positions = [0.0]
            def step(self):
                super().step()
                self.commanded_positions.append(self.positions[1])
        sim = TrackingSim()
        res = execute_trajectory(
            sim,
            ["/joint"],
            [[0.2]],
            collision_pairs=[["/robot", "/wall"]],
            max_velocity=[1.0],
            max_acceleration=[2.0],
            max_jerk=[15.0],
            steps_per_waypoint=10,
        )
        self.assertEqual(res["steps_run"], 10)
        self.assertEqual(res["final_positions"], [0.2])
        self.assertFalse(sim.stepping)

        pts = sim.commanded_positions
        dt = sim.getSimulationTimeStep()
        vels = [(pts[k] - pts[k - 1]) / dt for k in range(1, len(pts))]
        accs = [(vels[k] - vels[k - 1]) / dt for k in range(1, len(vels))]
        jerks = [(accs[k] - accs[k - 1]) / dt for k in range(1, len(accs))]

        self.assertTrue(all(abs(v) <= 1.0 for v in vels))
        self.assertTrue(all(abs(a) <= 2.0 for a in accs))
        self.assertTrue(all(abs(j) <= 15.0 for j in jerks))

    def test_smooth_trajectory_collision_stops_and_cleans_up(self):
        sim = FakeSim(collision=True)
        with self.assertRaisesRegex(RuntimeError, "Collision detected"):
            execute_trajectory(
                sim,
                ["/joint"],
                [[0.2]],
                collision_pairs=[["/robot", "/wall"]],
                max_velocity=[1.0],
                max_acceleration=[2.0],
                max_jerk=[15.0],
                steps_per_waypoint=10,
            )
        self.assertTrue(sim.stopped)
        self.assertFalse(sim.stepping)

    def test_smooth_trajectory_with_gripper_actions(self):
        sim = FakeSim()
        result = execute_trajectory(
            sim,
            ["/joint"],
            [[0.2], [0.4]],
            collision_pairs=[["/robot", "/wall"]],
            max_velocity=[1.0],
            max_acceleration=[5.0],
            max_jerk=[30.0],
            steps_per_waypoint=10,
            gripper_actions=[
                {"waypoint": 0, "joint": "/gripper", "position": 0.5, "grasp": grasp_config()},
                {"waypoint": 1, "joint": "/gripper", "position": 0.0, "place": {"object": "/part", "target": "/target", "max_distance": 0.05}},
            ],
        )
        self.assertEqual(result["steps_run"], 56)
        self.assertEqual(result["final_positions"], [0.4])
        self.assertTrue(result["gripper_results"][0]["grasp"]["hold_verified"])
        self.assertTrue(result["gripper_results"][1]["place"]["success"])
        self.assertFalse(sim.stepping)


if __name__ == "__main__":
    unittest.main()
