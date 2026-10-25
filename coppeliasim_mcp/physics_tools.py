"""Inspect and configure scene-level physics settings."""

from math import isfinite

from .json_log import log



def _validate_engine_property(value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in value)
    ):
        raise ValueError("engine_property must be a two-item [engine_index, version] integer list")


def configure_physics(sim, engine_property=None, dynamics_step_size=None):
    if engine_property is None and dynamics_step_size is None:
        engine = sim.getIntArrayProperty(sim.handle_scene, "dynamicsEngine")
        step_size = sim.getFloatProperty(sim.handle_scene, "dynamicsStepSize")
        return {"success": True, "engine_property": engine, "dynamics_step_size": step_size, "changed": False}

    if sim.getSimulationState() != sim.simulation_stopped:
        raise ValueError("Physics settings can only change while simulation is stopped")
    if engine_property is not None:
        _validate_engine_property(engine_property)
    if dynamics_step_size is not None:
        if (
            not isinstance(dynamics_step_size, (int, float))
            or isinstance(dynamics_step_size, bool)
            or not isfinite(dynamics_step_size)
            or dynamics_step_size <= 0
        ):
            raise ValueError("dynamics_step_size must be finite and positive")
        simulation_step = sim.getFloatParam(sim.floatparam_simulation_time_step)
        if dynamics_step_size > simulation_step:
            raise ValueError("dynamics_step_size must not exceed the simulation time step")

    old_engine = sim.getIntArrayProperty(sim.handle_scene, "dynamicsEngine")
    old_step_size = sim.getFloatProperty(sim.handle_scene, "dynamicsStepSize")
    try:
        if engine_property is not None:
            sim.setIntArrayProperty(sim.handle_scene, "dynamicsEngine", engine_property)
            if sim.getIntArrayProperty(sim.handle_scene, "dynamicsEngine") != engine_property:
                raise RuntimeError("Physics engine property readback did not match requested value")
        if dynamics_step_size is not None:
            sim.setFloatProperty(sim.handle_scene, "dynamicsStepSize", float(dynamics_step_size))
            if sim.getFloatProperty(sim.handle_scene, "dynamicsStepSize") != float(dynamics_step_size):
                raise RuntimeError("Dynamics step size readback did not match requested value")
    except Exception:
        try:
            sim.setIntArrayProperty(sim.handle_scene, "dynamicsEngine", old_engine)
            sim.setFloatProperty(sim.handle_scene, "dynamicsStepSize", old_step_size)
        except Exception as rollback_error:
            log("error", "physics.settings_rollback_failed", error=str(rollback_error))
        raise

    current_engine = sim.getIntArrayProperty(sim.handle_scene, "dynamicsEngine")
    current_step_size = sim.getFloatProperty(sim.handle_scene, "dynamicsStepSize")
    log("success", "physics.settings_updated", engine_property=current_engine, dynamics_step_size=current_step_size)
    return {"success": True, "engine_property": current_engine, "dynamics_step_size": current_step_size, "changed": True}
