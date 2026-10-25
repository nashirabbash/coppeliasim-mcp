#!/usr/bin/env python3
"""Interactive WASD Keyboard Teleoperation for CoppeliaSim Mobile Robot."""

import sys
import tty
import termios
from pathlib import Path

# Add CoppeliaSim ZMQ client
COPPELIA_ROOT = Path("/home/myarchlinux/.local/opt/coppeliaSim")
CLIENT_SRC = COPPELIA_ROOT / "programming" / "zmqRemoteApi" / "clients" / "python" / "src"
if CLIENT_SRC.exists() and str(CLIENT_SRC) not in sys.path:
    sys.path.insert(0, str(CLIENT_SRC))

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

HELP = """
========================================
   CoppeliaSim WASD Keyboard Control   
========================================
  [W] : Maju (Forward)
  [S] : Mundur (Backward)
  [A] : Belok Kiri (Turn Left)
  [D] : Belok Kanan (Turn Right)
  [X] or [SPACE] : Berhenti (Stop)
  [Q] : Keluar (Quit)
========================================
"""

def get_char():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def main():
    print("Menghubungkan ke CoppeliaSim di localhost:23000...")
    client = RemoteAPIClient()
    sim = client.require('sim')

    if sim.getSimulationState() == sim.simulation_stopped:
        print("Memulai simulasi...")
        sim.startSimulation()

    print(HELP)
    print("Tekan tombol W/A/S/D untuk menggerakkan robot (Q untuk keluar):")

    try:
        while True:
            char = get_char()
            lower_char = char.lower()
            if lower_char == 'q':
                print("\rKeluar dari teleoperation...")
                sim.setStringSignal('wasd_cmd', 'x')
                break
            elif lower_char in ['w', 'a', 's', 'd', ' ', 'x']:
                cmd_map = {
                    'w': '▲ MAJU',
                    's': '▼ MUNDUR',
                    'a': '◄ KIRI',
                    'd': '► KANAN',
                    ' ': '■ STOP',
                    'x': '■ STOP'
                }
                print(f"\rPerintah: {cmd_map.get(lower_char, lower_char)}    ", end="", flush=True)
                sim.setStringSignal('wasd_cmd', lower_char)
    except KeyboardInterrupt:
        print("\rDihentikan oleh pengguna.")
        sim.setStringSignal('wasd_cmd', 'x')

if __name__ == "__main__":
    main()
