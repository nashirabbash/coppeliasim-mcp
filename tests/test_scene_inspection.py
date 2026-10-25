import unittest
from unittest.mock import MagicMock, patch

from coppeliasim_mcp import runner, scene_inspection


class FakeSim:
    def __init__(self, objects=None, shapes=None, aliases=None, bbs=None, positions=None):
        self.objects = dict(objects or {})
        self.shapes = list(shapes or [])
        self.aliases = dict(aliases or {})
        self.bbs = dict(bbs or {})
        self.positions = dict(positions or {})
        self.handle_scene = 1
        self.object_shape_type = 2
        self.get_object_calls = []

    def getObject(self, name, options=None):
        self.get_object_calls.append((name, options))
        return self.objects.get(name, -1)

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


class TestSceneInspection(unittest.TestCase):
    def test_path_priority_first_candidate(self):
        sim = FakeSim(
            objects={
                "/Floor": 10,
                "/floor": 20,
                "/Floor_5_25": 30,
                "/resizableFloor": 40,
            },
            aliases={10: "Floor"},
            bbs={10: ([10.0, 10.0, 0.2], None)},
            positions={10: [0.0, 0.0, 0.0]},
        )
        info = scene_inspection.get_floor_info(sim)

        self.assertEqual(info["handle"], 10)
        self.assertEqual(info["name"], "Floor")
        self.assertEqual(sim.get_object_calls, [("/Floor", {"noError": True})])

    def test_path_priority_stops_at_first_valid_candidate(self):
        candidates = ["/Floor", "/floor", "/Floor_5_25", "/resizableFloor"]
        for idx, match_cand in enumerate(candidates):
            sim = FakeSim(
                objects={match_cand: 50 + idx},
                aliases={50 + idx: match_cand.strip("/")},
                bbs={50 + idx: ([4.0, 4.0, 0.1], None)},
                positions={50 + idx: [1.0, 2.0, 0.0]},
            )
            info = scene_inspection.get_floor_info(sim)
            self.assertEqual(info["handle"], 50 + idx)
            expected_calls = [(c, {"noError": True}) for c in candidates[: idx + 1]]
            self.assertEqual(sim.get_object_calls, expected_calls)

    def test_alias_fallback_when_path_candidates_miss(self):
        sim = FakeSim(
            objects={},
            shapes=[101, 102, 103],
            aliases={
                101: "Wall_East",
                102: "Custom_Floor_Mesh",
                103: "Second_floor",
            },
            bbs={102: ([8.0, 6.0, 0.5], None)},
            positions={102: [0.0, 0.0, 0.0]},
        )
        info = scene_inspection.get_floor_info(sim)

        self.assertEqual(info["handle"], 102)
        self.assertEqual(info["name"], "Custom_Floor_Mesh")

    def test_output_math_and_rounding(self):
        sim = FakeSim(
            objects={"/Floor": 77},
            aliases={77: "MainFloor"},
            bbs={77: ([10.126, 20.344, 0.456], None)},
            positions={77: [1.234, 2.345, 3.456]},
        )
        info = scene_inspection.get_floor_info(sim)

        self.assertEqual(info["handle"], 77)
        self.assertEqual(info["name"], "MainFloor")
        self.assertEqual(info["size_x"], 10.13)
        self.assertEqual(info["size_y"], 20.34)
        self.assertEqual(info["size_z"], 0.46)
        self.assertEqual(info["pos"], [1.23, 2.35, 3.46])
        self.assertEqual(info["bounds_x"], [-3.84, 6.29])
        self.assertEqual(info["bounds_y"], [-7.82, 12.52])
        self.assertEqual(info["surface_z"], 3.69)

    def test_absent_floor_returns_default_dict(self):
        sim = FakeSim(
            objects={},
            shapes=[201, 202],
            aliases={201: "Wall", 202: "Robot"},
        )
        info = scene_inspection.get_floor_info(sim)

        expected = {
            "exists": False,
            "size_x": 0.0,
            "size_y": 0.0,
            "bounds_x": [0, 0],
            "bounds_y": [0, 0],
            "surface_z": 0.0,
        }
        self.assertEqual(info, expected)

    def test_geometry_exception_swallowed_on_shape_bb(self):
        sim = FakeSim(
            objects={"/Floor": 99},
            aliases={99: "Floor"},
        )
        # getShapeBB will raise RuntimeError since 99 not in bbs
        info = scene_inspection.get_floor_info(sim)

        expected = {
            "exists": False,
            "size_x": 0.0,
            "size_y": 0.0,
            "bounds_x": [0, 0],
            "bounds_y": [0, 0],
            "surface_z": 0.0,
        }
        self.assertEqual(info, expected)

    def test_geometry_exception_swallowed_on_position(self):
        sim = FakeSim(
            objects={"/Floor": 99},
            aliases={99: "Floor"},
            bbs={99: ([10.0, 10.0, 0.2], None)},
        )
        # getObjectPosition will raise RuntimeError since 99 not in positions
        info = scene_inspection.get_floor_info(sim)

        expected = {
            "exists": False,
            "size_x": 0.0,
            "size_y": 0.0,
            "bounds_x": [0, 0],
            "bounds_y": [0, 0],
            "surface_z": 0.0,
        }
        self.assertEqual(info, expected)

    def test_legacy_runner_get_floor_info_delegates_to_scene_inspection(self):
        sim = MagicMock()
        with patch("coppeliasim_mcp.scene_inspection.get_floor_info") as mock_get_floor_info:
            sentinel = {"exists": True, "size_x": 5.0}
            mock_get_floor_info.return_value = sentinel

            res = runner.get_floor_info(sim)

            mock_get_floor_info.assert_called_once_with(sim)
            self.assertIs(res, sentinel)

    def test_legacy_runner_get_floor_info_functional_parity(self):
        sim = FakeSim(
            objects={"/floor": 42},
            aliases={42: "MyFloor"},
            bbs={42: ([5.0, 5.0, 0.1], None)},
            positions={42: [0.0, 0.0, 0.0]},
        )
        direct_res = scene_inspection.get_floor_info(sim)
        runner_res = runner.get_floor_info(sim)

        self.assertEqual(runner_res, direct_res)
        self.assertEqual(runner_res["handle"], 42)


if __name__ == "__main__":
    unittest.main()
