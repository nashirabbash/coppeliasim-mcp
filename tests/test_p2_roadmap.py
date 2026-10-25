import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from coppeliasim_mcp.floorplan_tools import import_floorplan
from coppeliasim_mcp.physics_benchmark import compare_physics_engines
from coppeliasim_mcp.signal_tools import operate_signal
from coppeliasim_mcp.p2_mcp_tools import register_p2_tools
from coppeliasim_mcp.physics_tools import configure_physics


class FakeSim:
    primitiveshape_cuboid = 1
    shapeintparam_static = 2
    shapeintparam_respondable = 3

    def __init__(self):
        self.next_handle = 1
        self.shapes = {}
        self.signals = {}

    def createPrimitiveShape(self, _shape, dimensions, _options):
        handle = self.next_handle
        self.next_handle += 1
        self.shapes[handle] = {"dimensions": dimensions}
        return handle

    def setObjectPosition(self, handle, _relative, position):
        self.shapes[handle]["position"] = position

    def setObjectInt32Param(self, handle, parameter, value):
        self.shapes[handle][parameter] = value

    def removeObject(self, handle):
        del self.shapes[handle]

    def getInt32Signal(self, name):
        return self.signals.get(("integer", name))

    def setInt32Signal(self, name, value):
        self.signals[("integer", name)] = value

    def getFloatSignal(self, name):
        return self.signals.get(("float", name))

    def setFloatSignal(self, name, value):
        self.signals[("float", name)] = value

    def getStringSignal(self, name):
        return self.signals.get(("string", name))

    def setStringSignal(self, name, value):
        self.signals[("string", name)] = value


class FakePhysics:
    handle_scene = -1
    simulation_stopped = 0
    floatparam_simulation_time_step = 1

    def __init__(self):
        self.engine = [0, 0]
        self.step_size = 0.005
        self.state = self.simulation_stopped

    def getSimulationState(self):
        return self.state

    def getIntArrayProperty(self, _target, _name):
        return self.engine.copy()

    def setIntArrayProperty(self, _target, _name, value):
        self.engine = value.copy()

    def getFloatProperty(self, _target, _name):
        return self.step_size

    def setFloatProperty(self, _target, _name, value):
        self.step_size = value

    def getFloatParam(self, _parameter):
        return 0.01


class P2RoadmapTests(unittest.TestCase):
    def test_typed_signals_round_trip_and_reject_wrong_type(self):
        sim = FakeSim()
        result = operate_signal(sim, "set", "integer", "plc.ready", 1)
        self.assertEqual(result["value"], 1)
        self.assertTrue(operate_signal(sim, "get", "integer", "plc.ready")["found"])
        with self.assertRaisesRegex(ValueError, "integer signal value"):
            operate_signal(sim, "set", "integer", "plc.ready", True)

    def test_floorplan_groups_pixels_and_reports_categories(self):
        sim = FakeSim()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.png"
            image = Image.new("L", (3, 1), color=255)
            image.putpixel((0, 0), 0)
            image.putpixel((1, 0), 80)
            image.save(path)
            result = import_floorplan(sim, path, 0.1, 2.0, 1.8, 1.0, [0, 10], [70, 90], [150, 200])
        self.assertEqual(result["segments_by_kind"], {"wall": 1, "door": 1, "window": 0})
        self.assertEqual(len(sim.shapes), 2)
        self.assertEqual(sim.shapes[1]["dimensions"], [0.1, 0.1, 2.0])

    def test_physics_benchmark_runs_same_episodes_per_scene_and_summarizes(self):
        scene_a = Path(__file__).resolve()
        scene_b = Path(__file__).resolve().parent.parent / "README.md"
        episode = [{"name": "same", "steps": 1, "success_conditions": [{"kind": "object_position", "object": "/Part", "position": [0, 0, 0], "tolerance": 0.1}]}]
        result = {"success": True, "summary": {"successful_episodes": 1}, "episodes": [{"name": "same", "success": True, "stopped_by": "steps", "steps_run": 1, "simulation_time": 0.05, "success_checks": []}]}
        with patch("coppeliasim_mcp.physics_benchmark.run_experiments", return_value=result) as run:
            output = compare_physics_engines({"bullet": str(scene_a), "ode": str(scene_b)}, episode)
        self.assertTrue(output["success"])
        self.assertEqual([item["engine"] for item in output["comparisons"]], ["bullet", "ode"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].kwargs["episodes"], run.call_args_list[1].kwargs["episodes"])


    def test_physics_settings_update_only_while_stopped_and_within_step_limit(self):
        sim = FakePhysics()
        result = configure_physics(sim, [1, 0], 0.002)
        self.assertEqual(result["engine_property"], [1, 0])
        self.assertEqual(result["dynamics_step_size"], 0.002)
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            configure_physics(sim, dynamics_step_size=0.02)
        sim.state = 1
        with self.assertRaisesRegex(ValueError, "only change while simulation is stopped"):
            configure_physics(sim, [0, 0])

    def test_p2_tool_registration_exposes_roadmap_tools(self):
        class Server:
            def __init__(self):
                self.tools = {}

            def tool(self, name, description):
                def register(function):
                    self.tools[name] = function
                    return function

                return register

        server = Server()
        register_p2_tools(server, lambda result: result)
        expected = {
            "coppelia_signals",
            "coppelia_import_floorplan",
            "coppelia_physics_engine",
            "coppelia_physics_benchmark",
        }
        self.assertTrue(expected.issubset(server.tools))

if __name__ == "__main__":
    unittest.main()
