# P0: episode isolation and dynamic-contact retention

## Scope and contract

This change addresses the two P0 entries in [the workflow roadmap](../coppeliasim-user-workflows.md#prioritas-fitur-berikutnya), not the deferred P1/P2 entries.

- Experiments use an explicit baseline `.ttt` scene, reload it before each episode, apply initial joints while stopped, and evaluate task assertions before stopping. Reload avoids dependence on the scene's optional stop/reset settings. Handles must be resolved after reload.
- Task assertions cover world-space object position within a metric tolerance and a proximity sensor's expected detection state. Completing the step budget alone is not task success.
- Trajectory grasp checks query contacts for the selected object shape and gripper-subtree shapes. They enforce a positive normal-force threshold, relative translation limit, minimum world-Z lift, and a stationary post-lift hold. Place checks remain geometric distance checks.
- Grasp failure stops the simulation and releases stepping. Successful trajectories preserve the existing running-simulation behavior.
- The missing `base64` import in the MCP image attachment path is fixed.

### Grasp example

```json
{
  "waypoint": 0,
  "joint": "/GripperJoint",
  "position": 0.0,
  "settle_steps": 20,
  "grasp": {
    "object": "/PartShape",
    "gripper": "/Gripper",
    "min_normal_force": 0.1,
    "hold_until_waypoint": 2,
    "min_lift": 0.05,
    "max_slip": 0.01,
    "max_rotation_rad": 0.1,
    "wrench_sweep": {
      "force_n": 0.2,
      "torque_nm": 0.02,
      "steps_per_direction": 2
    },
    "hold_steps": 10
  }
}
```

`hold_until_waypoint` must be after acquisition. Contacts, relative translation, and quaternion rotation are checked after every monitored step. At the endpoint, the executor adds `hold_steps` stationary steps, then applies ±force and ±torque on all three world axes at the configured magnitudes. Each direction runs `steps_per_direction` steps with collision/contact/slip checks. The result records 12 directions and `analytic_force_closure_proven=false`: this is bounded simulated wrench resistance, not mathematical force closure. Lift is checked after the sweep. A release action at that endpoint runs afterward. `normal_force` is the strongest absolute force projection onto a contact normal across the latest pass's dynamic substeps, not a sum of repeated substep forces.

The sweep only supports claims for its configured loads, tested directions, selected physics engine, and scene model. It does not establish real contact friction, hardware behavior, release quality, or functional safety. Hardware safety needs physical risk assessment and validation with the installed E-stop, guarding, torque/current limits, payload, and operating envelope.

### Live wrench-sweep smoke

CoppeliaSim runtime accepted `sim.addForceAndTorque` for a dynamic 0.08 m block inside a synthetic four-wall clamp. A ±0.05 N force and ±0.001 N·m torque sweep used two steps in each of 12 directions; all passed. Initial strongest contact projection was 0.86 N, maximum measured translation was `2.6e-7 m`, and maximum angular slip was `4.9e-6 rad`. This fixture had no actuated arm, commercial gripper, or lift. Camera snapshots were black, so visual geometry verification was unavailable. These measurements verify the software path and tested scene only.

### Installed Franka model probe

The installed `Franka gripper.ttm` exposes two finger pads and `openCloseJoint`. A standalone, root-teleported probe detected contact, then rejected lift at `0.1685 rad` with a `0.15 rad` rotation limit and at `0.2596 rad` with a `0.20 rad` limit. Another run passed all 12 wrench directions but missed its `0.02 m` lift threshold by `0.000198 m`. This was not an actuated Panda trajectory; root teleport and black camera captures prevent treating it as a validated gripper result.

An attached Panda/Franka test aligned the hand's `attachPoint` with `/Franka/connection` and parented the hand there; the hand root was not teleported during joint motion. At a 0.005 s timestep, a 10 g dynamic cuboid produced 1.02 N maximum normal contact across six contacts, then exceeded the 0.15 rad rotation limit at 0.2529 rad during the first `-X` force direction (0.05 N; 2 steps/direction requested); the other 11 directions did not run. By failure, the cuboid fell from z=0.5195 m to z=0.5116 m. A separate kinematic-joint attempt measured 4.34 N across six contacts, then failed at 0.2182 rad rotation; the cuboid fell 0.0474 m, and the commanded arm joint changed only 0.000017 rad. At the default 0.05 s timestep, `execute_trajectory` failed acquisition after arm-joint drift and the block fell to the floor. No articulated Panda/Franka lift or completed six-axis sweep was established.

The installed Panda reports 12 N·m maximum force on its last three joints. Setting all joint target and maximum forces to 87 N·m stabilized an unloaded 20-step hold, but exceeded those configured wrist limits and was excluded from grasp evidence. This diagnostic is not a hardware validation.

## Installed CoppeliaSim: REA findings

Observed artifact: `/home/myarchlinux/.local/opt/coppeliaSim/libcoppeliaSim.so`, ELF64 x86-64. SHA-256: `6c7be9f28f6d6236587dcd11ea108a8b5c08d52e6028912a3b533e4517ce59ae`. The shell entry point resolves to `coppeliaSim.sh`; it is not the native library. Live RPC reported version `41000`.

| Question | Observation | Evidence |
|---|---|---|
| What is installed? | Bounded desktop-directory scan examined 5032 entries and probed 4424 files. This digest covers metadata/read ranges, not every file byte. | `ev_39876123089bef1e6926306d1cf053b3ae827180dfcd54c4355ca21d924e8b8d` |
| Does the shipped core declare relevant APIs? | Complete dynamic export inventory contains 14754 exports. Selected exports include `simLoadScene`, `simSaveScene`, `simStopSimulation`, `simGetContactInfo`, and `simGetContactInfo_D`. Export presence alone does not prove execution. | `ev_095610fe9a6bdbafd34fa187e1b4835cce42935c8cdd2b70d58230dd0649e2c0` |
| What does the selected native wrapper do? | Symbol-scoped disassembly of `simGetContactInfo_D` shows handle translation, a call to `simGetContactInfo_internal`, and translation of returned handles. No whole-program decompilation or physics-solver audit was performed. | `ev_f7c21e48fcb21beacc1c3e93b4cfb067470a5ce8f6162135a9afdd0db613daf1` |
| What contact termination does the installed Python RPC return? | No contact returns four empty arrays, not `None`. The implementation stops enumeration on an empty object-pair array. | Live RPC and controlled replay below |
| Does contact plus lift/hold work? | A supported dynamic block on a synthetic prismatic lift passed 130 steps, including 10 stationary post-lift steps; measured lift was `0.1999999289031128` m. Contact without lift failed; displacing the block off its support failed at step 85. | `ev_1793b738aeb36ebab82866a7e5f124d515f252061bfb0e2d7e624584b7e0e2d8` |
| Do MCP handlers exercise the new behavior? | A fresh stdio MCP client initialized the actual server, received two valid PNG attachments from `coppelia_step`, executed the 130-step lift via `coppelia_trajectory`, and ran three independent four-step experiments. Position/proximity assertions passed for one task and correctly failed two deliberately wrong tasks. Initial state and samples matched across baseline reloads; a leaked object was removed. | `ev_524cda9808d164aba61c0182fd993d0d54873b902b0f4fd866d4045b177b2590` |

The final MCP replay bundle is exported locally to `/tmp/coppelia_p0_rea_evidence.json`. Earlier static and grasp Evidence IDs above identify tool responses in the investigation transcript; they are not in this post-close runtime bundle. The native analysis session was closed. Controlled replays record Python client processes interacting with live CoppeliaSim; they are not binary instrumentation of the physics engine. They observe terminal output, not network traffic or filesystem effects. REA could not verify ownership of some unrelated processes and left them untouched. The final grasp and MCP captures are not output-truncated.

## Reproducible regression check

```bash
.venv/bin/python -m unittest discover -q
```

All 27 discovered tests passed; none skipped. P0 regressions cover scene-state isolation, initial joints applied before start, required task assertions, wrong sensor types, diagnostic stops, no-lift false success, contact loss during lift, tangential-force false success, and contact/slip failure during post-lift dwell.

For live episodes, save a stopped baseline and call:

```python
coppelia_experiments(
    initial_scene="/absolute/baseline.ttt",
    observe=["/Part"],
    episodes=[{
        "steps": 100,
        "joint_positions": {"/Lift": 0.0},
        "success_conditions": [{
            "kind": "object_position",
            "object": "/Part",
            "position": [0, 0, 0.5],
            "tolerance": 0.01,
        }],
    }],
)
```

This deliberately replaces the active scene. Save unsaved work first. `initial_state` and the step-zero sample describe the reloaded baseline; subsequent samples and assertions are read before stopping. The batch finishes stopped with stepping disabled. Top-level `success` confirms batch execution; episode `success` and summary counts express task outcomes.

## Verification boundary

The synthetic clamp's standard and top-down camera images were black; visual geometry verification was unavailable. The simulator scene was restored to its original Floor-only state after the probes.

The synthetic clamp verifies only contact and translation retention for its stated loads. The attached Panda/Franka probes measured rotational slip but failed; they did not complete a lift or six-axis wrench sweep. Neither result proves mathematical force closure, realistic material friction, hardware behavior, or functional safety. Contacts are examined at simulation-step cadence using the latest pass's substeps; uninterrupted contact at every physics substep is not guaranteed. Thresholds require scene-specific calibration. Reloading a scene does not reset external controllers, ROS 2 nodes, network peers, filesystem state, or external random generators. Simulation does not certify hardware safety.

Official references: [contact API](https://manual.coppeliarobotics.com/en/sim/simGetContactInfo.htm), [stop API](https://manual.coppeliarobotics.com/en/sim/simStopSimulation.htm), [simulation settings](https://manual.coppeliarobotics.com/en/simulationPropertiesDialog.htm).
