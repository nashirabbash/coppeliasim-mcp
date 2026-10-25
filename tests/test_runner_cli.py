import io
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from coppeliasim_mcp import runner, runner_cli


class TestRunnerCLI(unittest.TestCase):
    def test_runner_main_delegates_to_runner_cli_main(self):
        with patch("coppeliasim_mcp.runner_cli.main") as mock_cli_main:
            mock_cli_main.return_value = 0
            res = runner.main(["--list-robots"])
            mock_cli_main.assert_called_once_with(["--list-robots"])
            self.assertEqual(res, 0)

    def test_cli_list_robots(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            runner_cli.main(["--list-robots"])
        output = json.loads(buf.getvalue())
        self.assertEqual(output, {"robot_aliases": runner.ROBOT_ALIASES})

    @patch("coppeliasim_mcp.runner_cli.launch_coppelia")
    @patch("coppeliasim_mcp.runner_cli.is_coppelia_running", return_value=False)
    def test_cli_only_launch_when_not_running(self, mock_is_running, mock_launch):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            runner_cli.main(["--only-launch", "--launch-headless"])
        mock_is_running.assert_called_once_with("localhost", 23000)
        mock_launch.assert_called_once_with(headless=True)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["success"])

    @patch("coppeliasim_mcp.runner_cli.launch_coppelia")
    @patch("coppeliasim_mcp.runner_cli.is_coppelia_running", return_value=True)
    def test_cli_only_launch_when_already_running(self, mock_is_running, mock_launch):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            runner_cli.main(["--only-launch"])
        mock_is_running.assert_called_once_with("localhost", 23000)
        mock_launch.assert_not_called()
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["success"])

    @patch("coppeliasim_mcp.runner_cli.run_code")
    def test_cli_code_dispatch_args(self, mock_run_code):
        mock_run_code.return_value = {"success": True, "output": "ok"}
        buf = io.StringIO()
        diagnostics_arg = json.dumps([{"kind": "collision", "objects": ["a", "b"]}])
        with patch("sys.stdout", buf):
            runner_cli.main([
                "--code", "print('hello')",
                "--host", "127.0.0.1",
                "--port", "23005",
                "--timeout", "12.5",
                "--no-snapshot",
                "--reset",
                "--launch-headless",
                "--diagnostics", diagnostics_arg,
            ])
        mock_run_code.assert_called_once_with(
            code="print('hello')",
            host="127.0.0.1",
            port=23005,
            take_snapshot=False,
            reset=True,
            auto_launch=True,
            headless=True,
            diagnostics=[{"kind": "collision", "objects": ["a", "b"]}],
            timeout=12.5,
        )
        self.assertEqual(json.loads(buf.getvalue()), {"success": True, "output": "ok"})

    @patch("coppeliasim_mcp.runner_cli.run_code")
    def test_cli_file_dispatch(self, mock_run_code):
        mock_run_code.return_value = {"success": True}
        file_content = "sim.setObjectPosition(1, -1, [0, 0, 0])"
        with patch("builtins.open", unittest.mock.mock_open(read_data=file_content)):
            with patch("sys.stdout", io.StringIO()):
                runner_cli.main(["--file", "/mock/path.py"])
        self.assertEqual(mock_run_code.call_args.kwargs["code"], file_content)

    @patch("coppeliasim_mcp.runner_cli.run_code")
    def test_cli_exit_code_on_execution_failure(self, mock_run_code):
        mock_run_code.return_value = {"success": False, "error": "SyntaxError"}
        with patch("sys.stdout", io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                runner_cli.main(["--code", "invalid code"])
            self.assertEqual(cm.exception.code, 1)

    def test_cli_stdin_tty_missing_code_exits_with_help(self):
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    runner_cli.main([])
                self.assertEqual(cm.exception.code, 1)

    @patch("coppeliasim_mcp.runner_cli.run_code")
    def test_cli_stdin_non_tty_reads_stdin(self, mock_run_code):
        mock_run_code.return_value = {"success": True}
        stdin_buf = io.StringIO("stdin_code()")
        with patch("sys.stdin", stdin_buf):
            with patch.object(stdin_buf, "isatty", return_value=False):
                with patch("sys.stdout", io.StringIO()):
                    runner_cli.main([])
        self.assertEqual(mock_run_code.call_args.kwargs["code"], "stdin_code()")


if __name__ == "__main__":
    unittest.main()
