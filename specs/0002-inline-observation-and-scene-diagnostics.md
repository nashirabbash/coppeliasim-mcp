# Specification: Visual Feedback and Scene Diagnostics for CoppeliaSim MCP

## Problem Statement

Users receive snapshot file paths after asking an agent to modify a CoppeliaSim scene. The MCP client may not be able to read files on the server host, so the agent cannot reliably inspect the generated scene. A successful Python script also does not prove that requested objects are collision-free or remain within the floor boundaries. Users must write additional Scene Scripts to gather these checks, with no standard result format.

## Solution

Keep `coppelia_step` as the existing high-level control seam. Return its existing isometric and top-down snapshots as MCP image content, alongside existing text output. Add optional, caller-requested scene diagnostics with structured results for selected object pairs and floor-boundary checks. Preserve direct Python API access and cumulative scene state.

## User Stories

1. As an agent, I want to receive the isometric snapshot as image content in the `coppelia_step` response, so that I can inspect the scene without reading a host-local path.
2. As an agent, I want to receive the top-down snapshot as image content in the same response, so that I can check object spacing and layout.
3. As a user, I want both existing snapshot paths retained in the response, so that I can save or inspect artifacts with existing workflows.
4. As an agent, I want snapshot content returned only when capture succeeds, so that a missing image does not look like valid visual evidence.
5. As an agent, I want snapshot capture failures reported explicitly, so that I can distinguish script success from incomplete visual feedback.
6. As an agent, I want to request collision checks for explicit object pairs, so that unrelated contacts inside a robot model do not overwhelm scene diagnostics.
7. As an agent, I want to request distance checks for explicit object pairs and a threshold, so that near-collisions can be identified before motion begins.
8. As an agent, I want to check whether selected objects remain within the detected floor bounds, so that scene layout violations are reported numerically.
9. As an agent, I want each diagnostic result to identify its requested check and objects, so that I can map findings to the scene without parsing log text.
10. As an agent, I want each diagnostic result to distinguish a clear result, a detected issue, and a check that could not be completed, so that unavailable data is not mistaken for success.
11. As an agent, I want invalid or unresolved object references reported against their individual checks, so that one bad reference does not hide other completed checks.
12. As a user, I want scene diagnostics to be opt-in, so that ordinary `coppelia_step` calls do not incur unrequested checks or extra simulation work.
13. As an agent, I want existing `code`, `reset`, and `headless` behavior preserved, so that current scene-building workflows continue to work.
14. As a user, I want direct `sim.*` API execution to remain available, so that the MCP does not restrict CoppeliaSim operations to a fixed set of wrappers.
15. As a user, I want the cumulative scene to remain unchanged by observation and diagnostic requests, so that checks do not unexpectedly reset or rebuild my scene.
16. As a user, I want diagnostic results and image attachments returned together after the Scene Script finishes, so that visual and numerical evidence refer to the same scene state.
17. As a developer, I want a single end-to-end MCP call to serve as the primary test seam, so that tests verify behavior visible to an MCP client.

## Implementation Decisions

- Extend the existing `coppelia_step` response rather than introducing a second execution tool. The user confirmed the single-call end-to-end seam.
- Preserve all current input parameters and text response fields.
- Return successful snapshot captures as MCP image content blocks. Retain existing snapshot paths in the text response for compatibility with local artifact workflows.
- Represent capture failures explicitly. A failed capture must not produce an image block or imply visual verification succeeded.
- Add an optional diagnostic request to `coppelia_step`. An omitted request performs no scene diagnostics.
- Support three initial diagnostic kinds: collision for a caller-selected pair of objects, distance for a caller-selected pair and threshold, and floor-boundary containment for a caller-selected object.
- Resolve requested object references against the active Cumulative Scene. Return a per-check result containing the check kind, requested object identifiers, outcome, and measured values when available.
- Use distinct outcomes for a clear check, a detected issue, and an unavailable/failed check. Do not convert unsupported checks or missing object references into a clear result.
- Isolate diagnostic failures per requested check; continue remaining checks and return their results.
- Do not run simulation steps as part of these checks. Diagnostics inspect the state after the requested Scene Script completes.
- Keep the `Scene Script`, `Simulator Host`, `Bridge Client`, `Execution Runner`, `Observation Snapshot`, and `Cumulative Scene` responsibilities consistent with the project glossary.
- Preserve the ADR decision to expose direct Python execution. Typed diagnostics supplement the API; they do not replace it with rigid scene-building operations.

## Testing Decisions

- Use one end-to-end `coppelia_step` MCP invocation as the primary test seam. The seam was confirmed during spec preparation.
- Test only externally visible behavior: MCP response content, returned image bytes, diagnostic outcomes, and observable simulator state. Do not pin internal helper calls or implementation-specific defaults.
- Run against a disposable scene with a live CoppeliaSim `Simulator Host` and the ZeroMQ Remote API enabled.
- Verify that a successful call returns both images as valid image content and retains snapshot paths in the text response.
- Verify that an induced snapshot-capture failure reports missing visual evidence without claiming capture success.
- Verify collision and distance results with a known separated pair and a known overlapping pair; include a threshold boundary case for distance.
- Verify floor containment for an object inside bounds and an object outside bounds, including a missing-floor or unresolved-object outcome.
- Verify an invalid diagnostic does not suppress valid results from other requested checks.
- Verify omission of the diagnostic request leaves the existing execution path and cumulative scene behavior intact.
- Prior art: the existing benchmark evaluates scene objects and checks snapshot validity through the runner. Extend behavior coverage at the higher MCP tool seam instead of creating a second test harness.

## Out of Scope

- Replacing arbitrary Python execution with a fixed set of scene-building tools.
- Automatically checking every possible pair of shapes in the entire scene.
- Detecting self-collision between links of the same robot model.
- Advancing simulation time or performing motion planning as part of diagnostics.
- Saving/loading complete scenes, exporting meshes, or expanding the robot/model catalog.
- Runtime plugin discovery beyond what is required to execute a requested diagnostic.
- Sandboxing Python execution or adding execution timeout and cancellation behavior.
- Changing CoppeliaSim, its plugins, installation, or ZeroMQ server configuration.

## Further Notes

- Snapshot and diagnostic evidence must describe the same post-script scene state.
- CoppeliaSim installation inspection found IK, OMPL, multiple physics-engine plugins, Vision, ROS 2, URDF, and GLTF components. Their presence does not prove they are loaded in the active `Simulator Host`.
- `get_scene_hierarchy` exposes roots and their complete non-system descendant trees. It is scene context, not a collision inventory; diagnostics still require explicit object selection.
- The installation analysis is static; runtime behavior remains to be verified during implementation.
