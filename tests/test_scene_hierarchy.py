import unittest
from unittest.mock import MagicMock, patch

from coppeliasim_mcp import runner, scene_inspection


class FakeHierarchySim:
    def __init__(
        self,
        tree=None,
        parents=None,
        aliases=None,
        paths=None,
        types=None,
        model_props=None,
        positions=None,
        modelproperty_not_model=1,
    ):
        self.handle_scene = 1
        self.handle_all = -1
        self.modelproperty_not_model = modelproperty_not_model
        self.sceneobject_shape = 0
        self.sceneobject_joint = 1
        self.sceneobject_graph = 2
        self.sceneobject_camera = 3
        self.sceneobject_light = 4
        self.sceneobject_dummy = 5
        self.sceneobject_proximitysensor = 6
        self.sceneobject_octree = 7
        self.sceneobject_pointcloud = 8
        self.sceneobject_visionsensor = 9
        self.sceneobject_forcesensor = 10
        self.sceneobject_script = 11

        self.tree = list(tree or [])
        self.parents = dict(parents or {})
        self.aliases = dict(aliases or {})
        self.paths = dict(paths or {})
        self.types = dict(types or {})
        self.model_props = dict(model_props or {})
        self.positions = dict(positions or {})

    def getObjectsInTree(self, root, obj_type, options):
        if root == self.handle_scene and obj_type == self.handle_all:
            return list(self.tree)
        return []

    def getObjectParent(self, handle):
        return self.parents.get(handle, -1)

    def getObjectAlias(self, handle, options=0):
        if options == 1:
            return self.paths.get(handle, f"/{self.aliases.get(handle, f'obj_{handle}')}")
        return self.aliases.get(handle, f"obj_{handle}")

    def getObjectType(self, handle):
        return self.types.get(handle, 0)

    def getModelProperty(self, handle):
        val = self.model_props.get(handle, 0)
        if isinstance(val, Exception):
            raise val
        return val

    def getObjectPosition(self, handle, rel_to):
        return self.positions.get(handle, [0.0, 0.0, 0.0])


class TestSceneHierarchy(unittest.TestCase):
    def test_hierarchy_nested_tree_and_children(self):
        sim = FakeHierarchySim(
            tree=[10, 20, 30],
            parents={20: 10, 30: 20},
            aliases={10: "Base", 20: "Arm", 30: "Hand"},
            paths={10: "/Base", 20: "/Base/Arm", 30: "/Base/Arm/Hand"},
            types={10: 0, 20: 1, 30: 5},
            model_props={10: 0, 20: 1, 30: 0},
            positions={10: [0.0, 0.0, 0.0], 20: [0.0, 0.0, 1.0], 30: [0.0, 0.0, 2.0]},
        )
        roots = scene_inspection.get_scene_hierarchy(sim)

        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual(root["name"], "Base")
        self.assertEqual(root["path"], "/Base")
        self.assertEqual(root["handle"], 10)
        self.assertEqual(root["type"], "shape")
        self.assertTrue(root["is_model"])
        self.assertEqual(root["pos"], [0.0, 0.0, 0.0])

        self.assertEqual(len(root["children"]), 1)
        child = root["children"][0]
        self.assertEqual(child["name"], "Arm")
        self.assertEqual(child["path"], "/Base/Arm")
        self.assertEqual(child["handle"], 20)
        self.assertEqual(child["type"], "joint")
        self.assertFalse(child["is_model"])

        self.assertEqual(len(child["children"]), 1)
        grandchild = child["children"][0]
        self.assertEqual(grandchild["name"], "Hand")
        self.assertEqual(grandchild["path"], "/Base/Arm/Hand")
        self.assertEqual(grandchild["handle"], 30)
        self.assertEqual(grandchild["type"], "dummy")
        self.assertTrue(grandchild["is_model"])
        self.assertEqual(grandchild["children"], [])

    def test_hierarchy_pos_rounding(self):
        sim = FakeHierarchySim(
            tree=[1],
            parents={},
            aliases={1: "Obj"},
            paths={1: "/Obj"},
            positions={1: [1.23456, -2.67891, 0.00499]},
        )
        roots = scene_inspection.get_scene_hierarchy(sim)
        self.assertEqual(roots[0]["pos"], [1.23, -2.68, 0.0])

    def test_hierarchy_sorting_by_path(self):
        sim = FakeHierarchySim(
            tree=[1, 2, 3, 4, 5],
            parents={4: 2, 5: 2},
            aliases={1: "zebra", 2: "apple", 3: "mango", 4: "z_child", 5: "a_child"},
            paths={
                1: "/zebra",
                2: "/apple",
                3: "/mango",
                4: "/apple/z_child",
                5: "/apple/a_child",
            },
        )
        roots = scene_inspection.get_scene_hierarchy(sim)
        self.assertEqual([r["path"] for r in roots], ["/apple", "/mango", "/zebra"])
        apple_children = roots[0]["children"]
        self.assertEqual([c["path"] for c in apple_children], ["/apple/a_child", "/apple/z_child"])

    def test_hierarchy_type_mapping_and_unknown_type(self):
        sim = FakeHierarchySim(
            tree=[1, 2, 3],
            parents={},
            aliases={1: "Cam", 2: "Light", 3: "Mysterious"},
            paths={1: "/Cam", 2: "/Light", 3: "/Mysterious"},
            types={1: 3, 2: 4, 3: 9999},
        )
        roots = scene_inspection.get_scene_hierarchy(sim)
        type_by_path = {r["path"]: r["type"] for r in roots}
        self.assertEqual(type_by_path["/Cam"], "camera")
        self.assertEqual(type_by_path["/Light"], "light")
        self.assertEqual(type_by_path["/Mysterious"], "unknown:9999")

    def test_hierarchy_system_object_prefix_filtering(self):
        sim = FakeHierarchySim(
            tree=[1, 2, 3, 4, 5],
            parents={4: 3, 5: 3},
            aliases={
                1: "XYZCamera_view",
                2: "DefaultLights",
                3: "UserRobot",
                4: "Agent_internal",
                5: "UserArm",
            },
            paths={
                1: "/XYZCamera_view",
                2: "/DefaultLights",
                3: "/UserRobot",
                4: "/UserRobot/Agent_internal",
                5: "/UserRobot/UserArm",
            },
        )
        with patch("coppeliasim_mcp.scene_inspection.log") as mock_log:
            roots = scene_inspection.get_scene_hierarchy(sim)
            self.assertEqual(len(roots), 1)
            self.assertEqual(roots[0]["name"], "UserRobot")
            self.assertEqual(len(roots[0]["children"]), 1)
            self.assertEqual(roots[0]["children"][0]["name"], "UserArm")
            mock_log.assert_called_once_with(
                "info",
                "simulator.scene_hierarchy_read",
                object_count=2,
                root_count=1,
            )

    def test_hierarchy_model_property_handling(self):
        sim = FakeHierarchySim(
            tree=[1, 2, 3],
            parents={},
            aliases={1: "ModelObj", 2: "NonModelObj", 3: "ErrorObj"},
            paths={1: "/ModelObj", 2: "/NonModelObj", 3: "/ErrorObj"},
            model_props={
                1: 0,
                2: 1,
                3: RuntimeError("Failed getting model property"),
            },
        )
        roots = scene_inspection.get_scene_hierarchy(sim)
        model_by_path = {r["path"]: r["is_model"] for r in roots}
        self.assertTrue(model_by_path["/ModelObj"])
        self.assertFalse(model_by_path["/NonModelObj"])
        self.assertFalse(model_by_path["/ErrorObj"])

    def test_legacy_runner_re_exports_constants(self):
        self.assertIs(runner.SYSTEM_OBJECT_PREFIXES, scene_inspection.SYSTEM_OBJECT_PREFIXES)
        self.assertIs(runner.SCENE_OBJECT_TYPE_NAMES, scene_inspection.SCENE_OBJECT_TYPE_NAMES)

    def test_legacy_runner_get_scene_hierarchy_delegates_to_scene_inspection(self):
        sim = MagicMock()
        with patch("coppeliasim_mcp.scene_inspection.get_scene_hierarchy") as mock_get_hierarchy:
            sentinel = [{"name": "fake_root"}]
            mock_get_hierarchy.return_value = sentinel

            res = runner.get_scene_hierarchy(sim)

            mock_get_hierarchy.assert_called_once_with(sim)
            self.assertIs(res, sentinel)

    def test_legacy_runner_get_scene_hierarchy_functional_parity(self):
        sim = FakeHierarchySim(
            tree=[1, 2],
            parents={2: 1},
            aliases={1: "Base", 2: "Joint"},
            paths={1: "/Base", 2: "/Base/Joint"},
            types={1: 0, 2: 1},
            positions={1: [1.111, 2.222, 3.333], 2: [4.444, 5.555, 6.666]},
        )
        direct_res = scene_inspection.get_scene_hierarchy(sim)
        runner_res = runner.get_scene_hierarchy(sim)

        self.assertEqual(runner_res, direct_res)
        self.assertEqual(len(runner_res), 1)
        self.assertEqual(runner_res[0]["children"][0]["name"], "Joint")


if __name__ == "__main__":
    unittest.main()
