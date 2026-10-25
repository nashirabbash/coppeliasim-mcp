# P1: structured simulation, catalog, scene save/load

## Added MCP tools
- `coppelia_simulate`: run N steps (max 10000), sample object positions and proximity sensors, stop early on `until` diagnostic issue, optional JSON export.
- `coppelia_catalog`: search `.ttm` models and `.ttt` scenes under `COPPELIASIM_ROOT`; no simulator needed.
- `coppelia_scene`: save or load `.ttt` scene.

## Added modules
- `json_log.py`: JSON log line to stderr; levels debug, info, success, error.
- `sim_connection.py`: `connect_sim`; auto-launch via `runner.launch_coppelia`.
- `sim_run.py`: request validation, sampling, `run_simulation`.
- `scene_catalog.py`: catalog search.
- `scene_io.py`: save, load, stop, export, `run_scene_action`.

## Changed
- `coppelia_mcp.py`: registers three tools.
- `README.md`: documents the three tools.

## Verified live (CoppeliaSim 4.x, port 23000)
- Catalog: `pioneer` returns `models/robots/mobile/pioneer p3dx.ttm`, 4 ms.
- Simulate: 20 steps, `sample_every=5` gives 4 samples at t=0.25..1.0; export JSON read back.
- Until: `distance` threshold 1e6 stops at step 1 with `stopped_by=condition`.
- Object positions change across samples (simulation advances).
- Proximity sensor `/PioneerP3DX/ultrasonicSensor` returns `detected` and `distance`.
- Bad object path returns `Object not found` with `success=false`.
- Save to `/tmp/smoke_scene.ttt`, load it back; save to missing parent dir fails.

## Known limits
- Root object paths need leading `/`; `Shape` is not found, `/Shape` is.
- `runner.py` is 508 lines, over the 300-line rule; untouched here.
- Load replaces the current scene; no confirmation step.
- Not committed.
