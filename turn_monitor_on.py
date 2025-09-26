#!/usr/bin/python3
import subprocess
import os

# --- CONFIGURATION ---
# IMPORTANT: Use the FULL path to your presence detection script
PATH_TO_PRESENCE_SCRIPT = "/home/mickaelramilison/presence_detector.py"

# Create a clean environment for Wayland commands
env = os.environ.copy()
env['DISPLAY'] = ':0'
env['XDG_RUNTIME_DIR'] = '/run/user/1000'

try:
    # 1. Turn the screen on
    on_command = ["wlr-randr", "--output", "HDMI-A-1", "--on", "--mode", "1920x1080"]
    subprocess.run(on_command, env=env, check=True)
    print("Command successful: HDMI signal turned ON.")

    # 2. Launch the presence detection script in the background
    print(f"Launching '{PATH_TO_PRESENCE_SCRIPT}' in the background...")
    start_command = ["python3", PATH_TO_PRESENCE_SCRIPT]
    
    # Use Popen to run the script in the background and not wait for it.
    # This is essential because the presence script runs in an infinite loop.
    subprocess.Popen(start_command, env=env)

except Exception as e:
    print(f"An error occurred: {e}")
