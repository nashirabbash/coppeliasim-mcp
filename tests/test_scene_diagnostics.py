import unittest
from unittest.mock import MagicMock, patch

from coppeliasim_mcp import runner, scene_inspection


class FakeDiagnosticsSim:
    def __init__(
        self,
        objects=None,
        collisions=None,
        distances=None,
        matrices=None,
        bbox_params=None,
        shapes=None,
        aliases=None,
        bbs=None,
        positions=None,
    ):
        self.objects = dict(objects or {})
        self.collisions = dict(collisions or {})
        self.distances = dict(distances or {})
        self.matrices = dict(matrices or {})
        self.bbox_params = dict(bbox_params or {})
        self.shapes = list(shapes or [])
        self.aliases = dict(aliases or {})
        self.bbs = dict(bbs or {})
        self.positions = dict(positions or {})
        self.handle_scene = 1
        self.object_shape_type = 2
        self.objfloatparam_objbbox_min_x = 101
        self.objfloatparam_objbbox_max_x = 102
        self.objfloatparam_objbbox_min_y = 103
        self.objfloatparam_objbbox_max_y = 104
        self.objfloatparam_objbbox_min_z = 105
        self.objfloatparam_objbbox_max_z = 106

    def getObject(self, name, options=None):
        return self.objects.get(name, -1)

    def checkCollision(self, handle1, handle2):
        return self.collisions.get((handle1, handle2), (0,))

    def checkDistance(self, handle1, handle2):
        return self.distances.get((handle1, handle2), (0, [], []))

    def getObjectMatrix(self, handle, rel_to):
        return self.matrices.get(handle, [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0])

    def getObjectFloatParam(self, handle, param_id):
        return self.bbox_params.get(handle, {}).get(param_id, 0.0)

    def getObjectsInTree(self, root, obj_type, options):
        if root == self.handle_scene and obj_type == self.object_shape_type:
            return self.shapes
        return []

    def getObjectAlias(self, handle):
        return self.aliases.get(handle, f"object_{handle}")

    def getShapeBB(self, handle):
        if handle in self.bbs:
            return self.bbs[handle]
        raise RuntimeError(f"No BB for {handle}")

    def getObjectPosition(self, handle, rel_to):
        if handle in self.positions:
            return self.positions[handle]
        raise RuntimeError(f"No position for {handle}")


class TestEvaluateSceneDiagnostics(unittest.TestCase):
    def setUp(self):
        self.sim = FakeDiagnosticsSim(
            objects={"robot": 1, "table": 2, "box": 3, "/Floor": 10},
            collisions={(1, 2): (0,), (1, 3): (1,)},
            distances={
                (1, 2): (1, [0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.5], None),
                (1, 3): (1, [0.0, 0.0, 0.0, 0.2, 0.0, 0.0, 0.2], None),
            },
            matrices={
                1: [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                3: [1.0, 0.0, 0.0, 10.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            },
            bbox_params={
                1: {101: -1.0, 102: 1.0, 103: -1.0, 104: 1.0, 105: 0.0, 106: 1.0},
                3: {101: -1.0, 102: 1.0, 103: -1.0, 104: 1.0, 105: 0.0, 106: 1.0},
            },
            bbs={10: ([4.0, 4.0, 0.2], None)},
            positions={10: [0.0, 0.0, 0.0]},
            aliases={10: "Floor"},
        )
        self.floor = {"exists": True, "bounds_x": [-2.0, 2.0], "bounds_y": [-2.0, 2.0]}

    def test_collision_clear_and_issue_statuses(self):
        checks = [
            {"kind": "collision", "objects": ["robot", "table"]},
            {"kind": "collision", "objects": ["robot", "box"]},
        ]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
        self.assertEqual(len(res), 2)
        self.assertEqual(
            res[0],
            {"kind": "collision", "objects": ["robot", "table"], "status": "clear", "collision": False},
        )
        self.assertEqual(
            res[1],
            {"kind": "collision", "objects": ["robot", "box"], "status": "issue", "collision": True},
        )

    def test_distance_threshold_equality_and_comparison(self):
        checks = [
            {"kind": "distance", "objects": ["robot", "table"], "threshold": 0.5},
            {"kind": "distance", "objects": ["robot", "table"], "threshold": 0.4},
            {"kind": "distance", "objects": ["robot", "table"], "threshold": 0.6},
        ]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
        self.assertEqual(res[0]["status"], "issue")
        self.assertEqual(res[0]["distance"], 0.5)
        self.assertEqual(res[0]["threshold"], 0.5)
        self.assertEqual(res[0]["closest_points"], [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])

        self.assertEqual(res[1]["status"], "clear")
        self.assertEqual(res[1]["distance"], 0.5)
        self.assertEqual(res[1]["threshold"], 0.4)

        self.assertEqual(res[2]["status"], "issue")
        self.assertEqual(res[2]["distance"], 0.5)
        self.assertEqual(res[2]["threshold"], 0.6)

    def test_distance_threshold_validation_errors(self):
        invalid_thresholds = [-0.001, float("nan"), float("inf"), float("-inf"), "0.5", None]
        for t in invalid_thresholds:
            checks = [{"kind": "distance", "objects": ["robot", "table"], "threshold": t}]
            res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
            self.assertEqual(res[0]["status"], "unavailable")
            self.assertEqual(res[0]["error"], "distance threshold must be a finite non-negative number")

        checks = [{"kind": "distance", "objects": ["robot", "table"]}]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertIn("threshold", res[0]["error"])

    def test_distance_api_failures(self):
        sim = FakeDiagnosticsSim(
            objects={"robot": 1, "table": 2},
            distances={(1, 2): (0, [0.0] * 7, None)},
        )
        res = scene_inspection.evaluate_scene_diagnostics(sim, [{"kind": "distance", "objects": ["robot", "table"], "threshold": 1.0}], floor=self.floor)
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Distance API did not return a measurement")

        sim.distances[(1, 2)] = (1, [0.0] * 6, None)
        res = scene_inspection.evaluate_scene_diagnostics(sim, [{"kind": "distance", "objects": ["robot", "table"], "threshold": 1.0}], floor=self.floor)
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Distance API did not return a measurement")

        sim.distances[(1, 2)] = (1, "not-a-list", None)
        res = scene_inspection.evaluate_scene_diagnostics(sim, [{"kind": "distance", "objects": ["robot", "table"], "threshold": 1.0}], floor=self.floor)
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Distance API did not return a measurement")

    def test_floor_bounds_inside_and_outside(self):
        checks = [
            {"kind": "floor_bounds", "objects": ["robot"]},
            {"kind": "floor_bounds", "object": "box"},
        ]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
        self.assertEqual(
            res[0],
            {"kind": "floor_bounds", "objects": ["robot"], "status": "clear", "bounds_x": [-2.0, 2.0], "bounds_y": [-2.0, 2.0]},
        )
        self.assertEqual(
            res[1],
            {"kind": "floor_bounds", "objects": ["box"], "status": "issue", "bounds_x": [-2.0, 2.0], "bounds_y": [-2.0, 2.0]},
        )

    def test_floor_bounds_missing_floor_and_default_lookup(self):
        checks = [{"kind": "floor_bounds", "objects": ["robot"]}]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor={"exists": False})
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Floor not found")

        res_default = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=None)
        self.assertEqual(res_default[0]["status"], "clear")
        self.assertEqual(res_default[0]["bounds_x"], [-2.0, 2.0])
        self.assertEqual(res_default[0]["bounds_y"], [-2.0, 2.0])

        sim_no_floor = FakeDiagnosticsSim(
            objects={"robot": 1},
            matrices={1: [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]},
            bbox_params={1: {101: -1.0, 102: 1.0, 103: -1.0, 104: 1.0, 105: 0.0, 106: 1.0}},
        )
        res_no_floor = scene_inspection.evaluate_scene_diagnostics(sim_no_floor, checks, floor=None)
        self.assertEqual(res_no_floor[0]["status"], "unavailable")
        self.assertEqual(res_no_floor[0]["error"], "Floor not found")

    def test_malformed_checks_and_missing_objects(self):
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, ["not-a-dict", 123], floor=self.floor)
        self.assertEqual(res[0], {"kind": None, "objects": [], "status": "unavailable", "error": "Each diagnostic must be an object"})
        self.assertEqual(res[1], {"kind": None, "objects": [], "status": "unavailable", "error": "Each diagnostic must be an object"})

        res = scene_inspection.evaluate_scene_diagnostics(self.sim, [{"kind": "velocity", "objects": ["robot"]}], floor=self.floor)
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Unsupported diagnostic kind: velocity")

        cases = [
            ({"kind": "collision", "objects": ["robot"]}, "collision requires 2 object name(s)"),
            ({"kind": "collision", "objects": ["robot", "table", "box"]}, "collision requires 2 object name(s)"),
            ({"kind": "collision", "objects": "robot"}, "collision requires 2 object name(s)"),
            ({"kind": "collision", "objects": ["", "table"]}, "collision requires 2 object name(s)"),
            ({"kind": "collision", "objects": [123, "table"]}, "collision requires 2 object name(s)"),
            ({"kind": "floor_bounds", "objects": ["robot", "table"]}, "floor_bounds requires 1 object name(s)"),
            ({"kind": "floor_bounds", "objects": []}, "floor_bounds requires 1 object name(s)"),
        ]
        for check, expected_err in cases:
            res = scene_inspection.evaluate_scene_diagnostics(self.sim, [check], floor=self.floor)
            self.assertEqual(res[0]["status"], "unavailable")
            self.assertEqual(res[0]["error"], expected_err)

        res = scene_inspection.evaluate_scene_diagnostics(
            self.sim,
            [{"kind": "collision", "objects": ["robot", "nonexistent"]}],
            floor=self.floor,
        )
        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Object not found: ['robot', 'nonexistent']")

    def test_per_check_exception_isolation(self):
        mixed_checks = [
            "invalid_non_dict",
            {"kind": "collision", "objects": ["robot", "table"]},
            {"kind": "distance", "objects": ["robot", "table"]},
            {"kind": "distance", "objects": ["robot", "table"], "threshold": 0.5},
            {"kind": "collision", "objects": ["robot", "missing_obj"]},
            {"kind": "floor_bounds", "objects": ["robot"]},
        ]
        res = scene_inspection.evaluate_scene_diagnostics(self.sim, mixed_checks, floor=self.floor)
        self.assertEqual(len(res), 6)

        self.assertEqual(res[0]["status"], "unavailable")
        self.assertEqual(res[0]["error"], "Each diagnostic must be an object")

        self.assertEqual(res[1]["status"], "clear")
        self.assertNotIn("error", res[1])

        self.assertEqual(res[2]["status"], "unavailable")
        self.assertIn("threshold", res[2]["error"])

        self.assertEqual(res[3]["status"], "issue")
        self.assertNotIn("error", res[3])

        self.assertEqual(res[4]["status"], "unavailable")
        self.assertEqual(res[4]["error"], "Object not found: ['robot', 'missing_obj']")

        self.assertEqual(res[5]["status"], "clear")
        self.assertNotIn("error", res[5])

    def test_legacy_runner_evaluate_scene_diagnostics_delegates(self):
        sim = MagicMock()
        checks = [{"kind": "collision", "objects": ["a", "b"]}]
        floor = {"exists": True, "bounds_x": [-1, 1], "bounds_y": [-1, 1]}
        with patch("coppeliasim_mcp.scene_inspection.evaluate_scene_diagnostics") as mock_eval:
            sentinel = [{"status": "clear"}]
            mock_eval.return_value = sentinel

            res = runner.evaluate_scene_diagnostics(sim, checks, floor=floor)

            mock_eval.assert_called_once_with(sim, checks, floor=floor)
            self.assertIs(res, sentinel)

    def test_legacy_runner_evaluate_scene_diagnostics_functional_parity(self):
        checks = [
            {"kind": "collision", "objects": ["robot", "table"]},
            {"kind": "distance", "objects": ["robot", "table"], "threshold": 0.5},
            {"kind": "floor_bounds", "objects": ["robot"]},
            {"kind": "floor_bounds", "objects": ["box"]},
        ]
        direct_res = scene_inspection.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)
        runner_res = runner.evaluate_scene_diagnostics(self.sim, checks, floor=self.floor)

        self.assertEqual(runner_res, direct_res)
        self.assertEqual([r["status"] for r in runner_res], ["clear", "issue", "clear", "issue"])


if __name__ == "__main__":
    unittest.main()
