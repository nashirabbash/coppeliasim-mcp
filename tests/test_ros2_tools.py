import io
import sys
import time
import unittest
from unittest.mock import Mock, patch

from coppeliasim_mcp import ros2_tools
from coppeliasim_mcp.ros2_tools import (
    _container_command,
    _read_messages,
    ros2_arguments,
    run_ros2,
    validate_ros2_request,
)


class Ros2ToolsTests(unittest.TestCase):
    def test_publisher_serializes_message_as_one_cli_argument(self):
        payload = {"data": "part; touch /tmp/not-run"}
        arguments = ros2_arguments("publish", "/robot/cmd", "std_msgs/msg/String", payload)
        self.assertEqual(arguments[-1], '{"data": "part; touch /tmp/not-run"}')
        command = _container_command(arguments)
        self.assertEqual(command[-1], arguments[-1])
        self.assertIn("--ipc", command)
        self.assertIn('exec ros2 "$@"', command[14])

    def test_operation_requires_matching_interface_kind(self):
        with self.assertRaisesRegex(ValueError, "requires a srv interface"):
            validate_ros2_request("service_call", "/reset", "std_msgs/msg/String", {}, 5)
        with self.assertRaisesRegex(ValueError, "valid ROS 2"):
            validate_ros2_request("echo", "/robot//state", "std_msgs/msg/String", None, 5)

    def test_timeout_and_payload_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 120"):
            validate_ros2_request("echo", "/robot/state", "std_msgs/msg/String", None, 121)
        with self.assertRaisesRegex(ValueError, "payload exceeds"):
            validate_ros2_request("publish", "/robot/state", "std_msgs/msg/String", {"data": "x" * 70000}, 5)

    def test_service_and_action_arguments_match_ros2_cli_shape(self):
        service = ros2_arguments("service_call", "/add", "example_interfaces/srv/AddTwoInts", {"a": 2, "b": 3})
        action = ros2_arguments("action_goal", "/sequence", "example_interfaces/action/Fibonacci", {"order": 5})
        self.assertEqual(service[0:3], ["service", "call", "/add"])
        self.assertEqual(action[0:3], ["action", "send_goal", "/sequence"])
        self.assertEqual(action[-1], "--feedback")

    def test_capture_and_publish_sequence_argument_building(self):
        cap_multi = ros2_arguments("capture", "/robot/state", "std_msgs/msg/String", count=5)
        self.assertEqual(cap_multi, ["topic", "echo", "/robot/state", "std_msgs/msg/String"])
        cap_once = ros2_arguments("capture", "/robot/state", "std_msgs/msg/String", count=1)
        self.assertEqual(cap_once, ["topic", "echo", "--once", "/robot/state", "std_msgs/msg/String"])

        payload = {"linear": {"x": 1.0}}
        seq_args = ros2_arguments("publish_sequence", "/robot/cmd_vel", "geometry_msgs/msg/Twist", payload, count=10, rate=20.0)
        self.assertEqual(seq_args[0:7], ["topic", "pub", "-t", "10", "-r", "20.0", "-w"])
        self.assertEqual(seq_args[7:], ["1", "/robot/cmd_vel", "geometry_msgs/msg/Twist", '{"linear": {"x": 1.0}}'])

        pub_multi = ros2_arguments("publish", "/robot/cmd", "std_msgs/msg/String", {"data": "hi"}, count=3, rate=2.0)
        self.assertEqual(pub_multi[0:6], ["topic", "pub", "-t", "3", "-r", "2.0"])

    def test_validation_bounds_count_duration_rate_and_payloads(self):
        with self.assertRaisesRegex(ValueError, "count must be an integer between 1 and 1000"):
            validate_ros2_request("capture", "/state", "std_msgs/msg/String", count=0)
        with self.assertRaisesRegex(ValueError, "count must be an integer between 1 and 1000"):
            validate_ros2_request("capture", "/state", "std_msgs/msg/String", count=1001)
        with self.assertRaisesRegex(ValueError, "duration must be finite"):
            validate_ros2_request("capture", "/state", "std_msgs/msg/String", duration=-1.0)
        with self.assertRaisesRegex(ValueError, "rate must be finite"):
            validate_ros2_request("publish_sequence", "/cmd", "std_msgs/msg/String", payload={"data": "x"}, rate=0)
        with self.assertRaisesRegex(ValueError, "payloads must be a non-empty list"):
            validate_ros2_request("publish_sequence", "/cmd", "std_msgs/msg/String", payloads=[])
        with self.assertRaisesRegex(ValueError, "feedback_topic must be a valid"):
            validate_ros2_request("session", "/cmd", "std_msgs/msg/String", payload={"data": "go"}, feedback_topic="/invalid//name")
        with self.assertRaisesRegex(ValueError, "feedback_type must use"):
            validate_ros2_request("session", "/cmd", "std_msgs/msg/String", payload={"data": "go"}, feedback_topic="/state", feedback_type="invalid_type")

    def test_read_messages_parses_stream_and_respects_count(self):
        stream = io.StringIO("data: msg_1\n---\ndata: msg_2\n---\ndata: msg_3\n---\n")
        proc = Mock()
        proc.stdout = stream
        proc.poll.side_effect = [None, None, None, 0]
        proc.stderr = None
        messages, stdout, stderr = _read_messages(proc, count=2, deadline=time.time() + 2.0)
        self.assertEqual(messages, ["data: msg_1", "data: msg_2"])
        self.assertIn("data: msg_1", stdout)

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_closed_loop_session_flow(self, mock_popen, mock_run):
        fake_echo_proc = Mock()
        fake_echo_proc.stdout = io.StringIO("data: feedback_ready\n---\n")
        fake_echo_proc.poll.return_value = 0
        fake_echo_proc.stderr = None
        mock_popen.return_value = fake_echo_proc

        mock_pub_res = Mock()
        mock_pub_res.returncode = 0
        mock_pub_res.stdout = "published #1"
        mock_pub_res.stderr = ""
        mock_run.return_value = mock_pub_res

        result = run_ros2(
            "session",
            "/robot/cmd",
            "std_msgs/msg/String",
            payload={"data": "step"},
            feedback_topic="/robot/state",
            feedback_type="std_msgs/msg/String",
            count=1,
            timeout=2.0,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["feedback_messages"], ["data: feedback_ready"])
        self.assertEqual(result["feedback_topic"], "/robot/state")

        startup = mock_run.call_args_list[0]
        self.assertEqual(startup.args[0], ["bash", str(ros2_tools.resource_path("scripts", "coppelia_ros2_container.sh")), "start"])
        self.assertEqual(startup.kwargs["env"]["COPPELIASIM_PYTHON"], sys.executable)
if __name__ == "__main__":
    unittest.main()
