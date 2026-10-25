from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from coppeliasim_mcp import runner, scene_catalog
from coppeliasim_mcp.runner import ROBOT_ALIASES


class TestResolveModelPath(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.models_dir = self.root / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_alias_normalization_and_resolution(self):
        rel = ROBOT_ALIASES["panda"]
        target = self.models_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path("  PANDA  ")
            self.assertEqual(resolved, target)
            self.assertIsInstance(resolved, Path)

    def test_direct_path_under_models(self):
        rel = "custom_dir/my_robot.ttm"
        target = self.models_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path("custom_dir/my_robot.ttm")
            self.assertEqual(resolved, target)
            self.assertIsInstance(resolved, Path)

    def test_direct_path_with_ttm_suffix_appended(self):
        rel = "custom_dir/my_robot.ttm"
        target = self.models_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path("custom_dir/my_robot")
            self.assertEqual(resolved, target)
            self.assertIsInstance(resolved, Path)

    def test_direct_absolute_path(self):
        target = self.root / "standalone_robot.ttm"
        target.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path(str(target))
            self.assertEqual(resolved, target)
            self.assertIsInstance(resolved, Path)

    def test_missing_model_raises_filenotfounderror_with_exact_message(self):
        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            missing_name = "unknown_bot"
            expected_msg = f"Robot model '{missing_name}' not found. Available aliases: {list(ROBOT_ALIASES.keys())}"
            with self.assertRaises(FileNotFoundError) as ctx:
                scene_catalog.resolve_model_path(missing_name)
            self.assertEqual(str(ctx.exception), expected_msg)

    def test_search_order_alias_precedence_over_models_name(self):
        # Create both alias target and a file named directly after alias
        alias_rel = ROBOT_ALIASES["ur5"]
        alias_target = self.models_dir / alias_rel
        alias_target.parent.mkdir(parents=True, exist_ok=True)
        alias_target.touch()

        direct_named = self.models_dir / "ur5"
        direct_named.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path("ur5")
            self.assertEqual(resolved, alias_target)

    def test_search_order_models_name_precedence_over_models_name_ttm(self):
        # When not an alias, models/name takes precedence over models/name.ttm
        name = "custom_robot"
        direct_file = self.models_dir / name
        direct_file.touch()

        ttm_file = self.models_dir / f"{name}.ttm"
        ttm_file.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = scene_catalog.resolve_model_path(name)
            self.assertEqual(resolved, direct_file)

    def test_legacy_runner_shim_delegation(self):
        with patch("coppeliasim_mcp.scene_catalog.resolve_model_path") as mock_resolve:
            mock_resolve.return_value = Path("/mock/robot.ttm")
            res = runner.resolve_model_path("panda")
            mock_resolve.assert_called_once_with("panda")
            self.assertEqual(res, Path("/mock/robot.ttm"))

    def test_legacy_runner_parity_behavior(self):
        rel = ROBOT_ALIASES["ur5"]
        target = self.models_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()

        with patch("coppeliasim_mcp.scene_catalog.COPPELIA_ROOT", self.root):
            resolved = runner.resolve_model_path("  UR5  ")
            self.assertEqual(resolved, target)
            self.assertIsInstance(resolved, Path)


class TestMakeLoadRobotFn(unittest.TestCase):
    def setUp(self):
        self.sim = MagicMock()
        self.sim.loadModel.return_value = 101

    @patch("coppeliasim_mcp.scene_catalog.resolve_model_path")
    def test_legacy_symbol_omissions(self, mock_resolve):
        mock_resolve.return_value = Path("/mock/models/panda.ttm")
        load_robot = runner.make_load_robot_fn(self.sim)

        handle = load_robot("panda")

        mock_resolve.assert_called_once_with("panda")
        self.sim.loadModel.assert_called_once_with("/mock/models/panda.ttm")
        self.sim.setObjectPosition.assert_not_called()
        self.sim.setObjectOrientation.assert_not_called()
        self.assertEqual(handle, 101)

    @patch("coppeliasim_mcp.scene_catalog.resolve_model_path")
    def test_legacy_symbol_both_optional_args(self, mock_resolve):
        mock_resolve.return_value = Path("/mock/models/panda.ttm")
        load_robot = runner.make_load_robot_fn(self.sim)

        pos = [0.1, 0.2, 0.3]
        ori = [0.0, 0.0, 1.57]
        handle = load_robot("panda", position=pos, orientation=ori)

        mock_resolve.assert_called_once_with("panda")
        self.sim.loadModel.assert_called_once_with("/mock/models/panda.ttm")
        self.sim.setObjectPosition.assert_called_once_with(101, -1, pos)
        self.sim.setObjectOrientation.assert_called_once_with(101, -1, ori)
        self.assertEqual(handle, 101)

    @patch("coppeliasim_mcp.scene_catalog.resolve_model_path")
    def test_legacy_symbol_partial_optional_args(self, mock_resolve):
        mock_resolve.return_value = Path("/mock/models/panda.ttm")
        load_robot = runner.make_load_robot_fn(self.sim)

        pos = [0.5, 0.0, 0.1]
        handle = load_robot("panda", position=pos)
        self.sim.setObjectPosition.assert_called_once_with(101, -1, pos)
        self.sim.setObjectOrientation.assert_not_called()
        self.assertEqual(handle, 101)

        self.sim.reset_mock()
        ori = [0.0, 1.57, 0.0]
        handle = load_robot("panda", orientation=ori)
        self.sim.setObjectPosition.assert_not_called()
        self.sim.setObjectOrientation.assert_called_once_with(101, -1, ori)
        self.assertEqual(handle, 101)

    def test_legacy_runner_make_load_robot_fn_delegates_to_scene_catalog(self):
        with patch("coppeliasim_mcp.scene_catalog.make_load_robot_fn") as mock_factory:
            fake_fn = object()
            mock_factory.return_value = fake_fn
            res = runner.make_load_robot_fn(self.sim)
            mock_factory.assert_called_once_with(self.sim)
            self.assertIs(res, fake_fn)

    @patch("coppeliasim_mcp.scene_catalog.resolve_model_path")
    def test_direct_scene_catalog_symbol_parity(self, mock_resolve):
        mock_resolve.return_value = Path("/mock/models/panda.ttm")
        load_robot = scene_catalog.make_load_robot_fn(self.sim)

        pos = [1.0, 1.0, 0.0]
        ori = [0.0, 0.0, 0.0]
        handle = load_robot("panda", position=pos, orientation=ori)

        mock_resolve.assert_called_once_with("panda")
        self.sim.loadModel.assert_called_once_with("/mock/models/panda.ttm")
        self.sim.setObjectPosition.assert_called_once_with(101, -1, pos)
        self.sim.setObjectOrientation.assert_called_once_with(101, -1, ori)
        self.assertEqual(handle, 101)


if __name__ == "__main__":
    unittest.main()
