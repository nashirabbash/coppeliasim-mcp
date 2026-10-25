"""Run bounded ROS 2 topic, service, and action operations."""

import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time

from .json_log import log
from .resources import resource_path

IMAGE = os.environ.get("COPPELIASIM_ROS2_IMAGE", "coppeliasim-ros2:humble")
ROOT = os.environ.get("COPPELIASIM_ROOT", str(Path.home() / ".local/opt/coppeliaSim"))
ROS_DOMAIN_ID = os.environ.get("ROS_DOMAIN_ID", "0")
MAX_TIMEOUT = 120.0
MAX_COUNT = 1000
MAX_PAYLOAD_CHARS = 65536
NAME_PATTERN = re.compile(r"^/?[A-Za-z][A-Za-z0-9_/]*$")
TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*/(msg|srv|action)/[A-Za-z][A-Za-z0-9_]*$")

def validate_ros2_request(
    operation,
    name,
    interface_type,
    payload=None,
    timeout=10.0,
    count=None,
    duration=None,
    rate=None,
    payloads=None,
    feedback_topic=None,
    feedback_type=None,
):
    valid_ops = {"publish", "echo", "capture", "publish_sequence", "session", "closed_loop", "service_call", "action_goal"}
    if operation not in valid_ops:
        raise ValueError(f"operation must be one of {', '.join(sorted(valid_ops))}")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name) or "//" in name or name.endswith("/"):
        raise ValueError("name must be a valid ROS 2 topic, service, or action name")
    if not isinstance(interface_type, str) or not TYPE_PATTERN.fullmatch(interface_type):
        raise ValueError("interface_type must use package/msg|srv|action/Type syntax")
    expected_kind = {"service_call": "srv", "action_goal": "action"}.get(operation, "msg")
    if f"/{expected_kind}/" not in interface_type:
        raise ValueError(f"{operation} requires a {expected_kind} interface")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be finite and between 0 and {MAX_TIMEOUT} seconds")

    if count is not None:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COUNT:
            raise ValueError(f"count must be an integer between 1 and {MAX_COUNT}")
    if duration is not None:
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= MAX_TIMEOUT:
            raise ValueError(f"duration must be finite and between 0 and {MAX_TIMEOUT} seconds")
    if rate is not None:
        if not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 < rate <= 1000.0:
            raise ValueError("rate must be finite and between 0 and 1000.0 Hz")

    def _check_payload(p, label="payload"):
        if not isinstance(p, dict):
            raise ValueError(f"{label} requires payload as a JSON object")
        if len(json.dumps(p)) > MAX_PAYLOAD_CHARS:
            raise ValueError(f"{label} exceeds {MAX_PAYLOAD_CHARS} encoded characters")

    if operation in {"publish", "service_call", "action_goal"}:
        _check_payload(payload)
    elif operation == "publish_sequence":
        if payloads is not None:
            if not isinstance(payloads, list) or not payloads:
                raise ValueError("payloads must be a non-empty list of JSON objects")
            if len(payloads) > MAX_COUNT:
                raise ValueError(f"payloads exceeds limit of {MAX_COUNT}")
            for idx, p in enumerate(payloads):
                _check_payload(p, f"payloads[{idx}]")
        elif payload is not None:
            _check_payload(payload)
        else:
            raise ValueError("publish_sequence requires payload or payloads as a JSON object")
    elif operation in {"session", "closed_loop"}:
        if payload is not None:
            _check_payload(payload)
        elif payloads is not None:
            if not isinstance(payloads, list) or not payloads:
                raise ValueError("payloads must be a non-empty list of JSON objects")
            for idx, p in enumerate(payloads):
                _check_payload(p, f"payloads[{idx}]")
        else:
            raise ValueError(f"{operation} requires payload or payloads as a JSON object")
        if feedback_topic is not None:
            if not isinstance(feedback_topic, str) or not NAME_PATTERN.fullmatch(feedback_topic) or "//" in feedback_topic or feedback_topic.endswith("/"):
                raise ValueError("feedback_topic must be a valid ROS 2 topic name")
        if feedback_type is not None:
            if not isinstance(feedback_type, str) or not TYPE_PATTERN.fullmatch(feedback_type) or "/msg/" not in feedback_type:
                raise ValueError("feedback_type must use package/msg/Type syntax")


def ros2_arguments(operation, name, interface_type, payload=None, count=None, rate=None):
    if operation == "publish":
        if count is not None and count > 1:
            return ["topic", "pub", "-t", str(count), "-r", str(rate or 1), "-w", "1", name, interface_type, json.dumps(payload)]
        return ["topic", "pub", "--once", "--wait-matching-subscriptions", "1", name, interface_type, json.dumps(payload)]
    if operation == "publish_sequence":
        c = count if count is not None else 1
        return ["topic", "pub", "-t", str(c), "-r", str(rate or 1), "-w", "1", name, interface_type, json.dumps(payload)]
    if operation == "echo":
        return ["topic", "echo", "--once", name, interface_type]
    if operation == "capture":
        if count == 1:
            return ["topic", "echo", "--once", name, interface_type]
        return ["topic", "echo", name, interface_type]
    if operation == "service_call":
        return ["service", "call", name, interface_type, json.dumps(payload)]
    return ["action", "send_goal", name, interface_type, json.dumps(payload), "--feedback"]


def _read_messages(proc, count=None, deadline=0.0):
    sel = selectors.DefaultSelector()
    messages, current, raw_lines = [], [], []
    try:
        try:
            sel.register(proc.stdout, selectors.EVENT_READ)
            selectable = True
        except (ValueError, OSError):
            selectable = False

        while time.time() < deadline and (count is None or len(messages) < count):
            if selectable:
                remaining = max(0.01, deadline - time.time())
                if not sel.select(timeout=min(0.2, remaining)):
                    if proc.poll() is not None:
                        break
                    continue
            line = proc.stdout.readline()
            if not line:
                break
            raw_lines.append(line)
            if line.strip() == "---":
                msg = "".join(current).strip()
                if msg:
                    messages.append(msg)
                current = []
            else:
                current.append(line)
        if current:
            msg = "".join(current).strip()
            if msg and (count is None or len(messages) < count):
                messages.append(msg)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
        sel.close()
    stderr = proc.stderr.read() if proc.stderr else ""
    return messages, "".join(raw_lines), stderr

def _container_command(arguments):
    return [
        "docker", "run", "--rm", "--network", "host", "--ipc", "host",
        "--env", f"ROS_DOMAIN_ID={ROS_DOMAIN_ID}",
        "--volume", f"{ROOT}:/opt/coppeliaSim:ro",
        IMAGE, "bash", "-lc",
        'source /opt/ros/humble/setup.bash && exec ros2 "$@"', "ros2", *arguments,
    ]



def run_ros2(
    operation,
    name,
    interface_type,
    payload=None,
    timeout=10.0,
    count=None,
    duration=None,
    rate=None,
    payloads=None,
    feedback_topic=None,
    feedback_type=None,
):
    validate_ros2_request(
        operation,
        name,
        interface_type,
        payload=payload,
        timeout=timeout,
        count=count,
        duration=duration,
        rate=rate,
        payloads=payloads,
        feedback_topic=feedback_topic,
        feedback_type=feedback_type,
    )
    log("info", "ros2.operation_started", operation=operation, name=name, interface_type=interface_type)
    try:
        script_path = resource_path("scripts", "coppelia_ros2_container.sh")
        env = os.environ.copy()
        env["COPPELIASIM_PYTHON"] = sys.executable
        subprocess.run(["bash", str(script_path), "start"], check=True, capture_output=True, text=True, timeout=70, env=env)
        if operation == "capture":
            effective = min(duration, timeout) if duration is not None else timeout
            c = count if count is not None else (None if duration is not None else 10)
            args = ros2_arguments("capture", name, interface_type, count=c)
            proc = subprocess.Popen(_container_command(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            messages, stdout, stderr = _read_messages(proc, count=c, deadline=time.time() + effective)
            response = {"success": True, "operation": operation, "name": name, "interface_type": interface_type, "messages": messages, "count": len(messages), "stdout": stdout, "stderr": stderr}
        elif operation == "publish_sequence":
            if payloads is not None:
                outputs, errors, success = [], [], True
                for p in payloads:
                    args = ros2_arguments("publish", name, interface_type, p)
                    res = subprocess.run(_container_command(args), capture_output=True, text=True, timeout=timeout)
                    outputs.append(res.stdout)
                    errors.append(res.stderr)
                    if res.returncode != 0:
                        success = False
                    if rate and rate > 0 and len(payloads) > 1:
                        time.sleep(1.0 / rate)
                response = {"success": success, "operation": operation, "name": name, "interface_type": interface_type, "published_count": len(payloads), "stdout": "\n".join(outputs), "stderr": "\n".join(errors)}
            else:
                c = count if count is not None else 1
                args = ros2_arguments("publish_sequence", name, interface_type, payload, count=c, rate=rate)
                res = subprocess.run(_container_command(args), capture_output=True, text=True, timeout=timeout)
                response = {"success": res.returncode == 0, "operation": operation, "name": name, "interface_type": interface_type, "published_count": c, "stdout": res.stdout, "stderr": res.stderr}
        elif operation in {"session", "closed_loop"}:
            fb_name = feedback_topic or name
            fb_type = feedback_type or interface_type
            c = count if count is not None else 1
            capture_args = ros2_arguments("capture", fb_name, fb_type, count=c)
            proc = subprocess.Popen(_container_command(capture_args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.3)
            items = payloads if payloads is not None else [payload]
            pub_ok = True
            for item in items:
                args = ros2_arguments("publish", name, interface_type, item)
                res = subprocess.run(_container_command(args), capture_output=True, text=True, timeout=timeout)
                if res.returncode != 0:
                    pub_ok = False
                if rate and rate > 0 and len(items) > 1:
                    time.sleep(1.0 / rate)
            messages, stdout, stderr = _read_messages(proc, count=c, deadline=time.time() + timeout)
            response = {"success": pub_ok, "operation": operation, "name": name, "interface_type": interface_type, "feedback_topic": fb_name, "feedback_type": fb_type, "published_count": len(items), "feedback_messages": messages, "count": len(messages), "stdout": stdout, "stderr": stderr}
        else:
            arguments = ros2_arguments(operation, name, interface_type, payload)
            result = subprocess.run(_container_command(arguments), capture_output=True, text=True, timeout=timeout)
            response = {"success": result.returncode == 0, "operation": operation, "name": name, "interface_type": interface_type, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or ""
        log("error", "ros2.operation_timed_out", operation=operation, name=name, timeout=timeout)
        return {"success": False, "operation": operation, "error": f"ROS 2 operation timed out after {timeout} seconds", "stdout": stdout, "stderr": stderr}
    except (OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        log("error", "ros2.operation_failed", operation=operation, error=detail)
        return {"success": False, "operation": operation, "error": detail}
    log("success" if response.get("success") else "error", "ros2.operation_completed", operation=operation, name=name)
    return response
