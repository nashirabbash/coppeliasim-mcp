import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


import coppelia_mcp as legacy_mcp
from coppeliasim_mcp import coppelia_mcp as package_mcp
from coppeliasim_mcp import resources


class PackagingResourceTests(unittest.TestCase):
    def test_resource_path_prefers_checkout_then_installed_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "coppeliasim_mcp"
            source.mkdir()
            script = root / "scripts" / "coppelia_launch.sh"
            script.parent.mkdir()
            script.touch()
            with patch.object(resources, "__file__", str(source / "resources.py")):
                self.assertEqual(resources.resource_path("scripts", "coppelia_launch.sh"), script)
                installed = root / "prefix"
                installed_script = installed / "share" / "coppeliasim-mcp" / "scripts" / "coppelia_launch.sh"
                installed_script.parent.mkdir(parents=True)
                installed_script.touch()
                script.unlink()
                with patch.object(resources.sysconfig, "get_path", return_value=str(installed)):
                    self.assertEqual(resources.resource_path("scripts", "coppelia_launch.sh"), installed_script)

    def test_execute_step_runs_runner_as_package_module(self):
        process = Mock()
        process.communicate = AsyncMock(return_value=(b'{"success": true}', b""))
        process.returncode = 0
        with patch.object(package_mcp.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn:
            asyncio.run(package_mcp.execute_step("pass", False, False, 5, None))
        self.assertIn(str(Path(package_mcp.__file__).resolve().parent.parent), spawn.call_args.kwargs["env"]["PYTHONPATH"].split(os.pathsep))

    def test_root_mcp_shim_exports_package_public_names(self):
        for name in (name for name in vars(package_mcp) if not name.startswith("_")):
            self.assertIs(getattr(legacy_mcp, name), getattr(package_mcp, name))


if __name__ == "__main__":
    unittest.main()
