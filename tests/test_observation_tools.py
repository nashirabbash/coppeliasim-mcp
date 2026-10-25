import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from coppeliasim_mcp import observation_tools, runner


class TestSnapshotConstants(unittest.TestCase):
    def test_canonical_constants_values(self):
        self.assertEqual(observation_tools.SNAPSHOT_PATH, Path("/tmp/coppelia_snapshot.png"))
        self.assertEqual(observation_tools.TOPDOWN_SNAPSHOT_PATH, Path("/tmp/coppelia_topdown.png"))

    def test_runner_legacy_constants_reexported(self):
        self.assertIs(runner.SNAPSHOT_PATH, observation_tools.SNAPSHOT_PATH)
        self.assertIs(runner.TOPDOWN_SNAPSHOT_PATH, observation_tools.TOPDOWN_SNAPSHOT_PATH)
        self.assertEqual(runner.SNAPSHOT_PATH, Path("/tmp/coppelia_snapshot.png"))
        self.assertEqual(runner.TOPDOWN_SNAPSHOT_PATH, Path("/tmp/coppelia_topdown.png"))


class TestCaptureSnapshot(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()
        self.sim.getVisionSensorImg.return_value = (b"fake_raw_rgb_data", [1024, 768])

    @patch("coppeliasim_mcp.observation_tools.ensure_observer_camera")
    @patch("coppeliasim_mcp.observation_tools.ensure_topdown_camera")
    def test_default_capture_snapshot_isometric_and_default_path(self, mock_topdown, mock_observer):
        mock_observer.return_value = 111
        with patch.object(Path, "mkdir") as mock_mkdir:
            result = observation_tools.capture_snapshot(self.sim)

            mock_observer.assert_called_once_with(self.sim)
            mock_topdown.assert_not_called()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            self.sim.getVisionSensorImg.assert_called_once_with(111)
            self.sim.saveImage.assert_called_once_with(
                b"fake_raw_rgb_data", [1024, 768], 0, str(observation_tools.SNAPSHOT_PATH), -1
            )
            self.assertEqual(result, str(observation_tools.SNAPSHOT_PATH))

    @patch("coppeliasim_mcp.observation_tools.ensure_observer_camera")
    @patch("coppeliasim_mcp.observation_tools.ensure_topdown_camera")
    def test_cam_type_topdown_selects_topdown_camera(self, mock_topdown, mock_observer):
        mock_topdown.return_value = 222
        with patch.object(Path, "mkdir") as mock_mkdir:
            result = observation_tools.capture_snapshot(self.sim, cam_type="topdown")

            mock_topdown.assert_called_once_with(self.sim)
            mock_observer.assert_not_called()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            self.sim.getVisionSensorImg.assert_called_once_with(222)
            self.sim.saveImage.assert_called_once_with(
                b"fake_raw_rgb_data", [1024, 768], 0, str(observation_tools.SNAPSHOT_PATH), -1
            )
            self.assertEqual(result, str(observation_tools.SNAPSHOT_PATH))

    @patch("coppeliasim_mcp.observation_tools.ensure_observer_camera")
    @patch("coppeliasim_mcp.observation_tools.ensure_topdown_camera")
    def test_cam_type_non_topdown_falls_back_to_observer_camera(self, mock_topdown, mock_observer):
        mock_observer.return_value = 333
        with patch.object(Path, "mkdir"):
            result = observation_tools.capture_snapshot(self.sim, cam_type="custom_or_isometric")

            mock_observer.assert_called_once_with(self.sim)
            mock_topdown.assert_not_called()
            self.sim.getVisionSensorImg.assert_called_once_with(333)

    def test_custom_output_path_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "subfolder" / "custom_snap.png"
            with patch("coppeliasim_mcp.observation_tools.ensure_observer_camera") as mock_obs:
                mock_obs.return_value = 111
                res = observation_tools.capture_snapshot(self.sim, output_path=out_path)

                self.assertTrue(out_path.parent.exists())
                self.sim.saveImage.assert_called_once_with(
                    b"fake_raw_rgb_data", [1024, 768], 0, str(out_path), -1
                )
                self.assertEqual(res, str(out_path))

    @patch("coppeliasim_mcp.observation_tools.ensure_observer_camera")
    def test_call_order_deterministic(self, mock_observer):
        mock_observer.return_value = 111
        sequence = []
        mock_observer.side_effect = lambda s: sequence.append("ensure") or 111
        self.sim.getVisionSensorImg.side_effect = lambda h: sequence.append("get_img") or (b"data", [1024, 768])
        self.sim.saveImage.side_effect = lambda img, res, opt, path, quality: sequence.append("save_img") or 0

        with patch.object(Path, "mkdir", side_effect=lambda **kw: sequence.append("mkdir")):
            observation_tools.capture_snapshot(self.sim)

        self.assertEqual(sequence, ["ensure", "get_img", "mkdir", "save_img"])

    def test_legacy_runner_capture_snapshot_delegates_to_observation_tools(self):
        with patch("coppeliasim_mcp.observation_tools.capture_snapshot") as mock_cap:
            mock_cap.return_value = "/tmp/mocked.png"
            res = runner.capture_snapshot(self.sim, output_path=Path("/tmp/custom.png"), cam_type="topdown")

            mock_cap.assert_called_once_with(self.sim, output_path=Path("/tmp/custom.png"), cam_type="topdown")
            self.assertEqual(res, "/tmp/mocked.png")

    def test_legacy_runner_capture_snapshot_functional_parity(self):
        with patch("coppeliasim_mcp.observation_tools.ensure_observer_camera") as mock_obs:
            mock_obs.return_value = 555
            with patch.object(Path, "mkdir") as mock_mkdir:
                res = runner.capture_snapshot(self.sim)

                mock_obs.assert_called_once_with(self.sim)
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                self.sim.getVisionSensorImg.assert_called_once_with(555)
                self.sim.saveImage.assert_called_once_with(
                    b"fake_raw_rgb_data", [1024, 768], 0, str(runner.SNAPSHOT_PATH), -1
                )
                self.assertEqual(res, str(runner.SNAPSHOT_PATH))

    def test_capture_snapshot_decoupled_from_runner_module(self):
        with patch.dict("sys.modules", {"coppeliasim_mcp.runner": None, "runner": None}):
            with patch("coppeliasim_mcp.observation_tools.ensure_observer_camera") as mock_obs:
                mock_obs.return_value = 777
                with patch.object(Path, "mkdir") as mock_mkdir:
                    res = observation_tools.capture_snapshot(self.sim)
                    self.assertEqual(res, str(observation_tools.SNAPSHOT_PATH))
                    self.sim.saveImage.assert_called_once_with(
                        b"fake_raw_rgb_data", [1024, 768], 0, str(observation_tools.SNAPSHOT_PATH), -1
                    )


class TestCaptureAllSnapshots(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()

    @patch("coppeliasim_mcp.observation_tools.capture_snapshot")
    def test_canonical_capture_all_snapshots_calls_order_and_tuple(self, mock_capture):
        mock_capture.side_effect = ["/tmp/iso.png", "/tmp/top.png"]
        res = observation_tools.capture_all_snapshots(self.sim)

        self.assertEqual(
            mock_capture.call_args_list,
            [
                unittest.mock.call(self.sim, observation_tools.SNAPSHOT_PATH, "isometric"),
                unittest.mock.call(self.sim, observation_tools.TOPDOWN_SNAPSHOT_PATH, "topdown"),
            ],
        )
        self.assertEqual(res, ("/tmp/iso.png", "/tmp/top.png"))

    @patch("coppeliasim_mcp.observation_tools.capture_snapshot")
    def test_canonical_capture_all_snapshots_exception_propagation(self, mock_capture):
        mock_capture.side_effect = RuntimeError("sensor failure")
        with self.assertRaises(RuntimeError):
            observation_tools.capture_all_snapshots(self.sim)

    def test_legacy_runner_capture_all_snapshots_delegates(self):
        with patch("coppeliasim_mcp.observation_tools.capture_all_snapshots") as mock_canonical:
            mock_canonical.return_value = ("/tmp/iso.png", "/tmp/top.png")
            res = runner.capture_all_snapshots(self.sim)

            mock_canonical.assert_called_once_with(self.sim)
            self.assertEqual(res, ("/tmp/iso.png", "/tmp/top.png"))

    def test_legacy_runner_capture_all_snapshots_exception_propagation(self):
        with patch("coppeliasim_mcp.observation_tools.capture_all_snapshots", side_effect=RuntimeError("runner failure")):
            with self.assertRaises(RuntimeError):
                runner.capture_all_snapshots(self.sim)


if __name__ == "__main__":
    unittest.main()
