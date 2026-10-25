from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from coppeliasim_mcp import runner, sim_connection


class TestSimConnection(unittest.TestCase):
    @patch("coppeliasim_mcp.sim_connection.socket.create_connection")
    def test_is_coppelia_running_success_default_args(self, mock_conn):
        mock_conn.return_value.__enter__.return_value = MagicMock()
        self.assertTrue(sim_connection.is_coppelia_running())
        mock_conn.assert_called_once_with(("localhost", 23000), timeout=1.0)

    @patch("coppeliasim_mcp.sim_connection.socket.create_connection")
    def test_is_coppelia_running_custom_args_and_timeout(self, mock_conn):
        mock_conn.return_value.__enter__.return_value = MagicMock()
        self.assertTrue(sim_connection.is_coppelia_running("127.0.0.2", 24000))
        mock_conn.assert_called_once_with(("127.0.0.2", 24000), timeout=1.0)

    @patch("coppeliasim_mcp.sim_connection.socket.create_connection", side_effect=ConnectionRefusedError("Connection refused"))
    def test_is_coppelia_running_connection_refused(self, mock_conn):
        self.assertFalse(sim_connection.is_coppelia_running())

    @patch("coppeliasim_mcp.sim_connection.socket.create_connection", side_effect=OSError("Network unreachable"))
    def test_is_coppelia_running_os_error(self, mock_conn):
        self.assertFalse(sim_connection.is_coppelia_running())

    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running")
    def test_legacy_runner_symbol_delegation(self, mock_probe):
        mock_probe.return_value = True
        self.assertTrue(runner.is_coppelia_running("10.0.0.1", 23001))
        mock_probe.assert_called_once_with("10.0.0.1", 23001)

        mock_probe.reset_mock()
        mock_probe.return_value = False
        self.assertFalse(runner.is_coppelia_running())
        mock_probe.assert_called_once_with("localhost", 23000)


    @patch("coppeliasim_mcp.sim_connection.subprocess.run")
    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running", return_value=True)
    def test_launch_coppelia_already_running_no_launch(self, mock_is_running, mock_run):
        self.assertTrue(sim_connection.launch_coppelia())
        mock_is_running.assert_called_once_with()
        mock_run.assert_not_called()

    @patch("coppeliasim_mcp.sim_connection.time.sleep")
    @patch("coppeliasim_mcp.sim_connection.time.time", side_effect=[0.0, 0.0, 1.0])
    @patch("coppeliasim_mcp.sim_connection.subprocess.run")
    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running", side_effect=[False, False, True])
    def test_launch_coppelia_headless_and_polling_success(self, mock_is_running, mock_run, mock_time, mock_sleep):
        expected_cmd = ["bash", str(sim_connection.resource_path("scripts", "coppelia_launch.sh")), "--headless"]
        self.assertTrue(sim_connection.launch_coppelia(headless=True, timeout=10))
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[0], expected_cmd)
        self.assertTrue(mock_run.call_args.kwargs["check"])
        self.assertEqual(mock_run.call_args.kwargs["env"]["COPPELIASIM_PYTHON"], sim_connection.sys.executable)
        mock_sleep.assert_called_once_with(0.5)
        self.assertEqual(mock_is_running.call_count, 3)

    @patch("coppeliasim_mcp.sim_connection.time.sleep")
    @patch("coppeliasim_mcp.sim_connection.time.time", side_effect=[0.0, 0.0, 10.0])
    @patch("coppeliasim_mcp.sim_connection.subprocess.run")
    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running", return_value=False)
    def test_launch_coppelia_timeout_returns_false(self, mock_is_running, mock_run, mock_time, mock_sleep):
        expected_cmd = ["bash", str(sim_connection.resource_path("scripts", "coppelia_launch.sh"))]
        self.assertFalse(sim_connection.launch_coppelia(headless=False, timeout=10))
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.args[0], expected_cmd)
        self.assertTrue(mock_run.call_args.kwargs["check"])
        self.assertEqual(mock_run.call_args.kwargs["env"]["COPPELIASIM_PYTHON"], sim_connection.sys.executable)
        mock_sleep.assert_called_once_with(0.5)

    @patch("coppeliasim_mcp.sim_connection.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["cmd"]))
    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running", return_value=False)
    def test_launch_coppelia_subprocess_error_propagates(self, mock_is_running, mock_run):
        with self.assertRaises(subprocess.CalledProcessError):
            sim_connection.launch_coppelia()

    @patch("coppeliasim_mcp.sim_connection.launch_coppelia")
    def test_legacy_runner_launch_coppelia_delegation(self, mock_launch):
        mock_launch.return_value = True
        self.assertTrue(runner.launch_coppelia(headless=True, timeout=15))
        mock_launch.assert_called_once_with(headless=True, timeout=15)

        mock_launch.reset_mock()
        mock_launch.return_value = False
        self.assertFalse(runner.launch_coppelia())
        mock_launch.assert_called_once_with(headless=False, timeout=25)

    def test_canonical_remote_client_and_paths_ownership(self):
        self.assertIsInstance(sim_connection.COPPELIA_ROOT, Path)
        self.assertIsInstance(sim_connection.CLIENT_SRC, Path)
        expected_src = (
            sim_connection.COPPELIA_ROOT / "programming" / "zmqRemoteApi" / "clients" / "python" / "src"
        )
        self.assertEqual(sim_connection.CLIENT_SRC, expected_src)
        self.assertTrue(hasattr(sim_connection, "RemoteAPIClient"))
        self.assertNotIn("runner", sim_connection.__dict__)

    def test_runner_reexports_remote_client_and_paths(self):
        self.assertIs(runner.COPPELIA_ROOT, sim_connection.COPPELIA_ROOT)
        self.assertIs(runner.CLIENT_SRC, sim_connection.CLIENT_SRC)
        self.assertIs(runner.RemoteAPIClient, sim_connection.RemoteAPIClient)

    @patch("coppeliasim_mcp.sim_connection.RemoteAPIClient")
    @patch("coppeliasim_mcp.sim_connection.is_coppelia_running", return_value=True)
    def test_connect_sim_uses_canonical_client(self, mock_is_running, mock_client_cls):
        mock_client = MagicMock()
        mock_sim = MagicMock()
        mock_client.require.return_value = mock_sim
        mock_client_cls.return_value = mock_client

        client, sim = sim_connection.connect_sim(host="127.0.0.1", port=23005)
        mock_is_running.assert_called_once_with("127.0.0.1", 23005)
        mock_client_cls.assert_called_once_with(host="127.0.0.1", port=23005)
        mock_client.require.assert_called_once_with("sim")
        self.assertIs(client, mock_client)
        self.assertIs(sim, mock_sim)

if __name__ == "__main__":
    unittest.main()
