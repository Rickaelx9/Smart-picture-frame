#!/usr/bin/python3
import subprocess
import os

# --- CONFIGURATION ---
# The filename of your main presence detection script
PRESENCE_SCRIPT_NAME = "presence_detector.py"

# Create a clean environment for Wayland commands
env = os.environ.copy()
env['DISPLAY'] = ':0'
env['XDG_RUNTIME_DIR'] = '/run/user/1000'

try:
    # 1. Turn the screen off
    off_command = ["wlr-randr", "--output", "HDMI-A-1", "--off"]
    subprocess.run(off_command, env=env, check=True)
    print("Command successful: HDMI signal turned OFF.")

    # 2. Stop the presence detection script
    # We use pkill to find and stop the script by its name.
    kill_presence_command = ["pkill", "-f", PRESENCE_SCRIPT_NAME]
    subprocess.run(kill_presence_command) # Don't use check=True, it's ok if it's not found
    print(f"Attempted to stop '{PRESENCE_SCRIPT_NAME}'.")

    # 3. Stop the picframe process as well
    kill_picframe_command = ["pkill", "-f", "picframe"]
    subprocess.run(kill_picframe_command)
    print("Attempted to stop 'picframe'.")

except Exception as e:
    print(f"An error occurred: {e}")
