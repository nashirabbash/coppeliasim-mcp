"""Robot autonomous obstacle avoidance script for CoppeliaSim.

Algorithm:
1. Baca array sensor proximity ultrasonik bagian depan (sensor 1 s/d 6).
2. Jika terdeteksi obstacle pada jarak < 0.6 meter:
   - Berhenti sejenak.
   - Putar badan robot 90 derajat (roda kiri mundur, roda kanan maju).
3. Jika area depan aman:
   - Terus melaju lurus ke depan.
"""

import time
import math

sim.startSimulation()

left_motor = sim.getObject('/PioneerP3DX/leftMotor')
right_motor = sim.getObject('/PioneerP3DX/rightMotor')

# Sensor depan Pioneer P3DX (index 1 s/d 6 mencakup sudut pandang ~180 derajat depan)
front_sensor_indices = [1, 2, 3, 4, 5, 6]
front_sensors = [sim.getObject(f'/PioneerP3DX/ultrasonicSensor[{i}]') for i in front_sensor_indices]

BASE_SPEED = 2.5 # rad/s (~20 cm/s linier)
SAFE_DISTANCE = 0.6 # meter

# Rasio putar 90 derajat:
# Kecepatan putar motor = 2.0 rad/s (-2.0 kiri, +2.0 kanan)
# Wheel base Pioneer ~0.381m, wheel radius ~0.0975m
# Kecepatan angular robot = (w_r - w_l) * r / (2 * L) = (2.0 - (-2.0)) * 0.0975 / 0.381 = ~1.02 rad/s
# Waktu untuk putar 90 derajat (pi/2 rad): (pi / 2) / 1.02 =~ 1.54 detik
TURN_SPEED = 2.0
TURN_DURATION_90_DEG = 1.54

print("Memulai navigasi otonom robot...")

# Tambahkan satu balok rintangan di depan robot jika belum ada
obs = sim.getObject('/TestObstacle', {'noError': True})
if obs == -1:
    obs = sim.createPrimitiveShape(sim.primitiveshape_cuboid, [0.6, 0.6, 1.0], 0)
    sim.setObjectAlias(obs, 'TestObstacle')
    sim.setObjectPosition(obs, -1, [1.8, 0.0, 0.5])
    sim.setObjectInt32Param(obs, sim.shapeintparam_static, 1)
    sim.setObjectInt32Param(obs, sim.shapeintparam_respondable, 1)
    sim.setShapeColor(obs, None, sim.colorcomponent_ambient_diffuse, [0.9, 0.1, 0.1])
    print("Balok obstacle merah ditambahkan di depan robot [x=1.8, y=0.0]")

start_loop_time = time.time()
MAX_RUN_TIME = 20.0 # Jalankan demonstrasi selama 20 detik

while time.time() - start_loop_time < MAX_RUN_TIME:
    # 1. Baca semua sensor depan
    min_distance = 999.0
    detected = False

    for s in front_sensors:
        res, dist, pt, obj, normal = sim.readProximitySensor(s)
        if res > 0 and dist < min_distance:
            min_distance = dist
            detected = True

    # 2. Logika Kemudi
    if detected and min_distance < SAFE_DISTANCE:
        print(f"[OBSTACLE DETECTED] Jarak rintangan: {min_distance:.2f} m! Memutar 90 derajat ke kiri...")
        # Rem sesaat
        sim.setJointTargetVelocity(left_motor, 0.0)
        sim.setJointTargetVelocity(right_motor, 0.0)
        time.sleep(0.2)

        # Putar 90 derajat
        sim.setJointTargetVelocity(left_motor, -TURN_SPEED)
        sim.setJointTargetVelocity(right_motor, TURN_SPEED)
        time.sleep(TURN_DURATION_90_DEG)

        # Stop putar
        sim.setJointTargetVelocity(left_motor, 0.0)
        sim.setJointTargetVelocity(right_motor, 0.0)
        time.sleep(0.1)
        print("[TURN COMPLETE] Selesai memutar 90 derajat. Melanjutkan maju ke depan...")
    else:
        # Maju lurus
        sim.setJointTargetVelocity(left_motor, BASE_SPEED)
        sim.setJointTargetVelocity(right_motor, BASE_SPEED)
        time.sleep(0.05)

# Selesai demonstrasi, hentikan motor
sim.setJointTargetVelocity(left_motor, 0.0)
sim.setJointTargetVelocity(right_motor, 0.0)

pos_akhir = sim.getObjectPosition(sim.getObject('/PioneerP3DX'), -1)
print(f"Demonstrasi navigasi selesai. Posisi akhir robot: {[round(x, 2) for x in pos_akhir]}")
