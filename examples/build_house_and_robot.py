"""End-to-End Verification: House with 5m walls, roof, and a walking/mobile robot."""

# Stop any running simulation and clear old scene objects if present
sim.stopSimulation()

# Helper to configure static & respondable obstacle
def make_box(size, pos, color=None):
    handle = sim.createPrimitiveShape(sim.primitiveshape_cuboid, size, 0)
    sim.setObjectPosition(handle, -1, pos)
    sim.setObjectInt32Param(handle, sim.shapeintparam_static, 1)
    sim.setObjectInt32Param(handle, sim.shapeintparam_respondable, 1)
    if color:
        sim.setShapeColor(handle, None, sim.colorcomponent_ambient_diffuse, color)
    return handle

print("Building house with 5m walls and roof...")

# Floor: 10m x 10m x 0.2m at z=0.1
floor = make_box([10.0, 10.0, 0.2], [0.0, 0.0, 0.1], [0.8, 0.8, 0.8])

# 4 Walls: height 5.0m, thickness 0.3m, length 10.0m. Center z = 0.2 + 2.5 = 2.7
# North wall (y = +5.0)
w_north = make_box([10.0, 0.3, 5.0], [0.0, 5.0, 2.7], [0.9, 0.6, 0.4])

# South wall (y = -5.0)
w_south = make_box([10.0, 0.3, 5.0], [0.0, -5.0, 2.7], [0.9, 0.6, 0.4])

# East wall (x = +5.0)
w_east = make_box([0.3, 10.0, 5.0], [5.0, 0.0, 2.7], [0.9, 0.6, 0.4])

# West wall (x = -5.0)
w_west = make_box([0.3, 10.0, 5.0], [-5.0, 0.0, 2.7], [0.9, 0.6, 0.4])

# Roof: 10.6m x 10.6m x 0.2m at z = 5.3 (top of 5m walls)
# Make roof slightly transparent or blueish so interior is visible
roof = make_box([10.6, 10.6, 0.2], [0.0, 0.0, 5.3], [0.2, 0.4, 0.8])

print("Spawning robot inside the house...")
# Load mobile robot (Pioneer P3DX) inside house at [0, 0, 0.3]
robot = load_robot("pioneer", [0.0, 0.0, 0.3])
print(f"Robot spawned with handle: {robot}")

# Verify robot position
pos = sim.getObjectPosition(robot, -1)
print(f"Verified Robot Position: {pos}")

# Start simulation so physics takes effect
sim.startSimulation()
print("Simulation started successfully.")
