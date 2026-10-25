# P2: model import and ROS 2

## Added

- `coppelia_import_model`: import URDF, SDF, STL, OBJ, or DAE; report new roots and joint counts.
- Optional pose placement and mesh scaling; URDF package URI replacement.
- `coppelia_ros2_status`: check `simROS2` plugin loading.
- `coppelia_ros2`: bounded ROS 2 topic publish/echo, service call, and action goal operations.
- Humble Docker runtime with simulator dependencies, demo interfaces, host networking, and shared IPC.

## Device findings

- Installed simulator is CoppeliaSim 4.10.0 x86_64; bundled `libsimROS2.so` targets ROS 2 Humble.
- Host is Arch Linux without ROS 2; Docker keeps Humble dependencies isolated from host packages.
- The ROS 2 Docker image includes Python ZMQ/CBOR dependencies required by CoppeliaSim's remote API add-on.

## Verification

- `.venv/bin/python -m unittest test_ros2_tools test_p2_tools test_p1_tools test_trajectory_tools`: 17 tests pass.
- Live CoppeliaSim loaded `simROS2`; ROS 2 CLI publish/echo roundtrip passed between ROS 2 endpoints. Scene-script publisher behavior was not verified.
- Service `example_interfaces/srv/AddTwoInts` returned `sum=5`.
- Fibonacci action accepted goal `order=5`, emitted feedback, and returned a successful sequence.
- Model importer smoke test loaded installed `redundantManipulator.stl` and removed its temporary root.
