# P2 roadmap implementation

## Added

- `coppelia_import_floorplan` converts grayscale pixel classes into static cuboid geometry, with pixel scale, class heights, respondable option, and image/segment limits. This is an MCP implementation, not a wrapper around CoppeliaSim's GUI add-on.
- `coppelia_signals` reads and writes typed integer, float, and string scene signals. It does not connect to PLC, OPC UA, or Modbus.
- `coppelia_physics_engine` reads or updates the scene `dynamicsEngine` `[index, version]` pair and `dynamicsStepSize`, only while simulation is stopped; update values are read back and rolled back on setter failure.
- `coppelia_physics_benchmark` runs identical bounded episode specifications on 2–5 caller-prepared `.ttt` scenes and returns task outcomes by engine label. Each scene must already have its engine configured; parameter equivalence is not inferred.

## Verification

- `.venv/bin/python -m unittest`: 49 tests passed; importing `coppelia_mcp` registered tool schemas successfully.
- Live CoppeliaSim 4.10.0 smoke: grayscale fixture generated 2 scene shapes; integer signal round-trip returned `17`; physics setter read back engine `[0, 0]` and dynamics step `0.004999999888241291`.
- Scene hierarchy confirmed both temporary shapes, then confirmed cleanup restored original `Floor` scene.
- Both returned image captures were black, so visual geometry verification is incomplete. Cross-engine benchmark was not run live because no distinct engine-configured scenes were supplied. Engine labels remain caller-supplied and unchecked. No hardware-safety claim.
