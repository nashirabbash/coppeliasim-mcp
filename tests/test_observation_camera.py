import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from coppeliasim_mcp import observation_tools, runner


class FakeSim:
    def __init__(self, existing_handles=None):
        self.existing_handles = dict(existing_handles or {})
        self.created_sensors, self.aliases, self.properties = [], {}, {}
        self.positions, self.orientations = {}, {}
        self.objectproperty_selectable, self._next_handle = 0x0001, 100

    def getObject(self, name, options=None):
        if name in self.existing_handles:
            return self.existing_handles[name]
        alias = name.rsplit("/", 1)[-1]
        return next((handle for handle, object_alias in self.aliases.items() if object_alias == alias), -1)
    def createVisionSensor(self, sensor_type, int_params, float_params):
        handle = self._next_handle
        self._next_handle += 1
        self.created_sensors.append((handle, sensor_type, int_params, float_params))
        return handle
    def setObjectAlias(self, handle, name):
        self.aliases[handle] = name
    def setObjectProperty(self, handle, prop):
        self.properties[handle] = prop
    def setObjectPosition(self, handle, rel_to, pos):
        self.positions[handle] = (rel_to, pos)
    def setObjectOrientation(self, handle, rel_to, rot):
        self.orientations[handle] = (rel_to, rot)

class TestEnsureCamera(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()
        self.sim.objectproperty_selectable = 1234
        self.name = "test_cam"
        self.pos = [1.0, 2.0, 3.0]
        self.rot = [0.1, 0.2, 0.3]
        self.fov_deg = 60.0

    def test_creates_vision_sensor_when_missing(self):
        self.sim.getObject.return_value = -1
        self.sim.createVisionSensor.return_value = 55
        handle = observation_tools.ensure_camera(self.sim, self.name, self.pos, self.rot, self.fov_deg)
        self.sim.getObject.assert_called_once_with(f"/{self.name}", {"noError": True})
        expected_fov_rad = self.fov_deg * 3.14159265 / 180.0
        expected_int_params = [1024, 768, 0, 0]
        expected_float_params = [0.1, 100.0, expected_fov_rad, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.sim.createVisionSensor.assert_called_once_with(3, expected_int_params, expected_float_params)
        self.sim.setObjectAlias.assert_called_once_with(55, self.name)
        self.sim.setObjectProperty.assert_called_once_with(55, self.sim.objectproperty_selectable)
        self.sim.setObjectPosition.assert_called_once_with(55, -1, self.pos)
        self.sim.setObjectOrientation.assert_called_once_with(55, -1, self.rot)
        self.assertEqual(handle, 55)

    def test_repositions_existing_camera(self):
        self.sim.getObject.return_value = 42
        handle = observation_tools.ensure_camera(self.sim, self.name, self.pos, self.rot, self.fov_deg)
        self.sim.getObject.assert_called_once_with(f"/{self.name}", {"noError": True})
        self.sim.createVisionSensor.assert_not_called()
        self.sim.setObjectAlias.assert_not_called()
        self.sim.setObjectProperty.assert_not_called()
        self.sim.setObjectPosition.assert_called_once_with(42, -1, self.pos)
        self.sim.setObjectOrientation.assert_called_once_with(42, -1, self.rot)
        self.assertEqual(handle, 42)

    def test_fake_sim_end_to_end_camera_creation(self):
        fake = FakeSim()
        handle = observation_tools.ensure_camera(fake, "MyCam", [1, 2, 3], [3.14, 0, 0], 45.0)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.getObject("/MyCam"), handle)
        h2 = observation_tools.ensure_camera(fake, "MyCam", [1, 2, 3], [3.14, 0, 0], 45.0)
        self.assertEqual(h2, 100)
        self.assertEqual(len(fake.created_sensors), 1)

    def test_legacy_runner_ensure_camera_delegates_to_observation_tools(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_camera") as mock_ensure:
            mock_ensure.return_value = 99
            res = runner.ensure_camera(self.sim, self.name, self.pos, self.rot, self.fov_deg)
            mock_ensure.assert_called_once_with(self.sim, self.name, self.pos, self.rot, self.fov_deg)
            self.assertEqual(res, 99)

    def test_legacy_runner_ensure_camera_functional_parity(self):
        fake = FakeSim()
        handle = runner.ensure_camera(fake, "RunnerCam", [1, 2, 3], [3.14, 0, 0], 45.0)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.aliases[100], "RunnerCam")
        self.assertEqual(fake.positions[100], (-1, [1, 2, 3]))
        self.assertEqual(fake.orientations[100], (-1, [3.14, 0, 0]))


class TestEnsureObserverCamera(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()

    def test_canonical_ensure_observer_camera_delegates_to_ensure_camera_with_runner_constants(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_camera") as mock_ensure:
            mock_ensure.return_value = 88
            res = observation_tools.ensure_observer_camera(self.sim)
            mock_ensure.assert_called_once_with(
                self.sim, observation_tools.OBSERVER_CAM_NAME,
                observation_tools.CALIBRATED_CAM_POS, observation_tools.CALIBRATED_CAM_ROT,
                observation_tools.CALIBRATED_FOV_DEG,
            )
            self.assertEqual(res, 88)

    def test_fake_sim_ensure_observer_camera_creates_properly(self):
        fake = FakeSim()
        handle = observation_tools.ensure_observer_camera(fake)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.aliases[100], observation_tools.OBSERVER_CAM_NAME)
        self.assertEqual(fake.positions[100], (-1, observation_tools.CALIBRATED_CAM_POS))
        self.assertEqual(fake.orientations[100], (-1, observation_tools.CALIBRATED_CAM_ROT))

    def test_legacy_runner_ensure_observer_camera_delegates_to_observation_tools(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_observer_camera") as mock_ensure_obs:
            mock_ensure_obs.return_value = 77
            res = runner.ensure_observer_camera(self.sim)
            mock_ensure_obs.assert_called_once_with(self.sim)
            self.assertEqual(res, 77)

    def test_legacy_runner_ensure_observer_camera_functional_parity(self):
        fake = FakeSim()
        handle = runner.ensure_observer_camera(fake)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.aliases[100], runner.OBSERVER_CAM_NAME)
        self.assertEqual(fake.positions[100], (-1, runner.CALIBRATED_CAM_POS))
        self.assertEqual(fake.orientations[100], (-1, runner.CALIBRATED_CAM_ROT))


class TestObserverConstants(unittest.TestCase):
    def test_canonical_constants_values(self):
        self.assertEqual(observation_tools.OBSERVER_CAM_NAME, "Agent_Observer_Cam")
        self.assertEqual(observation_tools.CALIBRATED_CAM_POS, [9.0, -9.0, 7.5])
        self.assertEqual(observation_tools.CALIBRATED_CAM_ROT, [-2.1588, -0.6940, 2.7385])
        self.assertEqual(observation_tools.CALIBRATED_FOV_DEG, 65.0)

    def test_runner_legacy_constants_reexported(self):
        self.assertEqual(runner.OBSERVER_CAM_NAME, observation_tools.OBSERVER_CAM_NAME)
        self.assertIs(runner.CALIBRATED_CAM_POS, observation_tools.CALIBRATED_CAM_POS)
        self.assertIs(runner.CALIBRATED_CAM_ROT, observation_tools.CALIBRATED_CAM_ROT)
        self.assertEqual(runner.CALIBRATED_FOV_DEG, observation_tools.CALIBRATED_FOV_DEG)

    def test_ensure_observer_camera_decoupled_from_runner_module(self):
        with patch.dict("sys.modules", {"coppeliasim_mcp.runner": None, "runner": None}):
            with patch("coppeliasim_mcp.observation_tools.ensure_camera") as mock_ensure:
                mock_ensure.return_value = 88
                sim = MagicMock()
                res = observation_tools.ensure_observer_camera(sim)
                self.assertEqual(res, 88)
                mock_ensure.assert_called_once_with(
                    sim,
                    observation_tools.OBSERVER_CAM_NAME,
                    observation_tools.CALIBRATED_CAM_POS,
                    observation_tools.CALIBRATED_CAM_ROT,
                    observation_tools.CALIBRATED_FOV_DEG,
                )


class TestEnsureTopdownCamera(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()

    def test_canonical_ensure_topdown_camera_delegates_to_ensure_camera_with_topdown_constants(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_camera") as mock_ensure:
            mock_ensure.return_value = 66
            res = observation_tools.ensure_topdown_camera(self.sim)
            mock_ensure.assert_called_once_with(
                self.sim, observation_tools.TOPDOWN_CAM_NAME,
                observation_tools.TOPDOWN_CAM_POS, observation_tools.TOPDOWN_CAM_ROT,
                observation_tools.TOPDOWN_FOV_DEG,
            )
            self.assertEqual(res, 66)

    def test_fake_sim_ensure_topdown_camera_creates_properly(self):
        fake = FakeSim()
        handle = observation_tools.ensure_topdown_camera(fake)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.aliases[100], observation_tools.TOPDOWN_CAM_NAME)
        self.assertEqual(fake.positions[100], (-1, observation_tools.TOPDOWN_CAM_POS))
        self.assertEqual(fake.orientations[100], (-1, observation_tools.TOPDOWN_CAM_ROT))

    def test_legacy_runner_ensure_topdown_camera_delegates_to_observation_tools(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_topdown_camera") as mock_ensure_top:
            mock_ensure_top.return_value = 55
            res = runner.ensure_topdown_camera(self.sim)
            mock_ensure_top.assert_called_once_with(self.sim)
            self.assertEqual(res, 55)

    def test_legacy_runner_ensure_topdown_camera_functional_parity(self):
        fake = FakeSim()
        handle = runner.ensure_topdown_camera(fake)
        self.assertEqual(handle, 100)
        self.assertEqual(fake.aliases[100], runner.TOPDOWN_CAM_NAME)
        self.assertEqual(fake.positions[100], (-1, runner.TOPDOWN_CAM_POS))
        self.assertEqual(fake.orientations[100], (-1, runner.TOPDOWN_CAM_ROT))


class TestTopdownConstants(unittest.TestCase):
    def test_canonical_constants_values(self):
        self.assertEqual(observation_tools.TOPDOWN_CAM_NAME, "Agent_TopDown_Cam")
        self.assertEqual(observation_tools.TOPDOWN_CAM_POS, [0.0, 0.0, 20.0])
        self.assertEqual(observation_tools.TOPDOWN_CAM_ROT, [3.14159, 0.0, 0.0])
        self.assertEqual(observation_tools.TOPDOWN_FOV_DEG, 90.0)

    def test_runner_legacy_constants_reexported(self):
        self.assertEqual(runner.TOPDOWN_CAM_NAME, observation_tools.TOPDOWN_CAM_NAME)
        self.assertIs(runner.TOPDOWN_CAM_POS, observation_tools.TOPDOWN_CAM_POS)
        self.assertIs(runner.TOPDOWN_CAM_ROT, observation_tools.TOPDOWN_CAM_ROT)
        self.assertEqual(runner.TOPDOWN_FOV_DEG, observation_tools.TOPDOWN_FOV_DEG)

    def test_ensure_topdown_camera_decoupled_from_runner_module(self):
        with patch.dict("sys.modules", {"coppeliasim_mcp.runner": None, "runner": None}):
            with patch("coppeliasim_mcp.observation_tools.ensure_camera") as mock_ensure:
                mock_ensure.return_value = 66
                sim = MagicMock()
                res = observation_tools.ensure_topdown_camera(sim)
                self.assertEqual(res, 66)
                mock_ensure.assert_called_once_with(
                    sim,
                    observation_tools.TOPDOWN_CAM_NAME,
                    observation_tools.TOPDOWN_CAM_POS,
                    observation_tools.TOPDOWN_CAM_ROT,
                    observation_tools.TOPDOWN_FOV_DEG,
                )


class TestAutoFrameGuiCamera(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()
        self.sim.handle_scene = 1
        self.sim.object_shape_type = 2

    def test_no_camera_early_return(self):
        self.sim.getObject.return_value = -1
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.getObject.assert_called_once_with('/DefaultCamera', {'noError': True})
        self.sim.getObjectsInTree.assert_not_called()
        self.sim.setObjectPosition.assert_not_called()
        self.sim.setObjectOrientation.assert_not_called()

    def test_extent_default_minimum_height_when_small_radius(self):
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.return_value = [101]
        self.sim.getObjectPosition.return_value = [1.0, 2.0, 0.0]
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.getObjectsInTree.assert_called_once_with(1, 2, 0)
        self.sim.getObjectPosition.assert_called_once_with(101, -1)
        self.sim.setObjectPosition.assert_called_once_with(42, -1, [0.0, 0.0, 15.0])
        self.sim.setObjectOrientation.assert_called_once_with(42, -1, [3.14159265, 0.0, 0.0])
    def test_extent_skips_handle_13_floor(self):
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.return_value = [13, 102]
        self.sim.getObjectPosition.side_effect = lambda h, rel: [100.0, 100.0, 0.0] if h == 13 else [2.0, 0.0, 0.0]
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.getObjectPosition.assert_called_once_with(102, -1)
        self.sim.setObjectPosition.assert_called_once_with(42, -1, [0.0, 0.0, 15.0])
    def test_extent_adjusts_height_for_large_scene(self):
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.return_value = [101, 102]
        self.sim.getObjectPosition.side_effect = lambda h, rel: [6.0, 8.0, 0.0] if h == 101 else [0.0, 3.0, 0.0]
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.setObjectPosition.assert_called_once_with(42, -1, [0.0, 0.0, 22.0])
        self.sim.setObjectOrientation.assert_called_once_with(42, -1, [3.14159265, 0.0, 0.0])
    def test_orientation_exact_downward_vector(self):
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.return_value = []
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.setObjectOrientation.assert_called_once_with(42, -1, [3.14159265, 0.0, 0.0])
    def test_swallowed_exception_on_sim_failure(self):
        self.sim.getObject.side_effect = RuntimeError("sim IPC error")
        observation_tools.auto_frame_gui_camera(self.sim)
        self.sim.getObject.side_effect = None
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.side_effect = Exception("failed tree")
        observation_tools.auto_frame_gui_camera(self.sim)

    def test_legacy_runner_auto_frame_gui_camera_delegates_to_observation_tools(self):
        with patch("coppeliasim_mcp.observation_tools.auto_frame_gui_camera") as mock_auto:
            runner.auto_frame_gui_camera(self.sim)
            mock_auto.assert_called_once_with(self.sim)

    def test_legacy_runner_auto_frame_gui_camera_functional_parity(self):
        self.sim.getObject.return_value = 42
        self.sim.getObjectsInTree.return_value = [101]
        self.sim.getObjectPosition.return_value = [6.0, 8.0, 0.0]
        runner.auto_frame_gui_camera(self.sim)
        self.sim.setObjectPosition.assert_called_once_with(42, -1, [0.0, 0.0, 22.0])
        self.sim.setObjectOrientation.assert_called_once_with(42, -1, [3.14159265, 0.0, 0.0])

    def test_auto_frame_gui_camera_decoupled_from_runner_module(self):
        with patch.dict("sys.modules", {"coppeliasim_mcp.runner": None, "runner": None}):
            self.sim.getObject.return_value = 42
            self.sim.getObjectsInTree.return_value = []
            observation_tools.auto_frame_gui_camera(self.sim)
            self.sim.setObjectPosition.assert_called_once_with(42, -1, [0.0, 0.0, 15.0])


if __name__ == "__main__":
    unittest.main()
