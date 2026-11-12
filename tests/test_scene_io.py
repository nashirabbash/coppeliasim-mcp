import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coppeliasim_mcp.scene_io import load_scene


class FakeSim:
    simulation_stopped = 0

    def __init__(self):
        self.state = 1
        self.polls = 0
        self.loaded = None

    def getSimulationState(self):
        self.polls += 1
        if self.polls >= 3:
            self.state = self.simulation_stopped
        return self.state

    def stopSimulation(self):
        self.state = 2

    def loadScene(self, path):
        assert self.state == self.simulation_stopped
        self.loaded = path


class SceneStopTests(unittest.TestCase):
    def test_scene_load_waits_for_stopped_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.ttt"
            path.touch()
            sim = FakeSim()
            with patch("coppeliasim_mcp.scene_io.time.sleep"):
                result = load_scene(sim, str(path))
        self.assertEqual(sim.loaded, str(path))
        self.assertGreaterEqual(sim.polls, 3)
        self.assertEqual(result["action"], "load")


if __name__ == "__main__":
    unittest.main()
