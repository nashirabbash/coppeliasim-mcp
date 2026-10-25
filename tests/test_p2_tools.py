import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from coppeliasim_mcp.model_import import import_model, ros2_status


class FakeSim:
    handle_scene = -1
    handle_all = -1
    sceneobject_joint = 1

    def __init__(self):
        self.roots = {10}
        self.positions = {}
        self.orientations = {}
        self.shape_calls = []

    def getObjectsInTree(self, root, object_type, options):
        if root == self.handle_scene:
            return list(self.roots)
        if object_type == self.sceneobject_joint:
            return [root + 1]
        return [root, root + 1]

    def importShape(self, file_format, path, options, tolerance, scale):
        self.shape_calls.append((file_format, path, scale))
        self.roots.add(20)
        return 20

    def getObjectAlias(self, handle):
        return f"Object{handle}"

    def setObjectPosition(self, handle, relative, position):
        self.positions[handle] = position

    def setObjectOrientation(self, handle, relative, orientation):
        self.orientations[handle] = orientation


class ModelImportTests(unittest.TestCase):
    def with_model(self, suffix):
        folder = tempfile.TemporaryDirectory()
        path = Path(folder.name) / f"robot{suffix}"
        path.write_text("model")
        self.addCleanup(folder.cleanup)
        return path

    def test_mesh_import_reports_root_and_moves_it(self):
        path = self.with_model(".stl")
        sim = FakeSim()
        client = Mock()
        result = import_model(sim, client, str(path), [1, 2, 3], [0, 0, 0], 0.5)
        self.assertEqual(result["models"], [{"handle": 20, "name": "Object20", "object_count": 2, "joint_count": 1}])
        self.assertEqual(sim.shape_calls[0], (0, str(path), 0.5))
        self.assertEqual(sim.positions[20], [1.0, 2.0, 3.0])

    def test_urdf_and_sdf_dispatch_to_native_importers(self):
        sim = FakeSim()
        path = self.with_model(".urdf")
        urdf = Mock()
        urdf.importFile.side_effect = lambda *_args: sim.roots.add(20) or "TestRobot"
        client = Mock()
        client.require.return_value = urdf
        result = import_model(sim, client, str(path), package_root="/tmp/models")
        self.assertEqual(result["imported_name"], "TestRobot")
        urdf.importFile.assert_called_once_with(str(path), 0, "/tmp/models")
        self.assertEqual(result["models"][0]["joint_count"], 1)

        sdf_path = self.with_model(".sdf")
        sim.roots = {10}
        sdf = Mock()
        getattr(sdf, "import").side_effect = lambda *_args: sim.roots.add(30)
        client.require.return_value = sdf
        result = import_model(sim, client, str(sdf_path))
        getattr(sdf, "import").assert_called_once_with(str(sdf_path), {})
        self.assertEqual(result["models"][0]["handle"], 30)

    def test_import_rejects_missing_files_and_nonfinite_pose(self):
        sim = FakeSim()
        with self.assertRaisesRegex(ValueError, "Model file must exist"):
            import_model(sim, Mock(), "/missing/robot.urdf")
        path = self.with_model(".obj")
        with self.assertRaisesRegex(ValueError, "orientation must contain three finite numbers"):
            import_model(sim, Mock(), str(path), orientation=[0, float("inf"), 0])
        self.assertEqual(sim.roots, {10})

    def test_ros2_status_reports_missing_plugin(self):
        client = Mock()
        client.require.side_effect = RuntimeError("ROS plugin unavailable")
        result = ros2_status(client)
        self.assertFalse(result["available"])
        self.assertIn("Source a compatible ROS 2 environment", result["required"])


if __name__ == "__main__":
    unittest.main()
