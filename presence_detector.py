#!/usr/bin/python3
import subprocess
import time
import os
from datetime import datetime, date

# Give the desktop environment 10 seconds to fully load after a reboot.
print("Script started. Waiting 10 seconds for desktop to initialize...")
time.sleep(10)

# --- Configuration ---
WIFI_MAC_ADDRESS = "9C:73:B1:F5:40:1B"
BLUETOOTH_MAC_ADDRESS = "9C:73:B1:F5:40:1A"
HOME_SCAN_INTERVAL = 300
AWAY_SCAN_INTERVAL = 60
SLEEPING_SCAN_INTERVAL = 1800
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 23

# --- Use the user's home directory for persistent flags ---
# The /tmp directory is wiped on reboot, so we use the home directory instead.
USER_HOME = os.path.expanduser("~") # Gets /home/mickaelramilison
MANUAL_OVERRIDE_FLAG = os.path.join(USER_HOME, "manual_override.flag")
REBOOT_FLAG = os.path.join(USER_HOME, "reboot_done.flag")


# --- Environment and Commands ---
env = os.environ.copy()
env['DISPLAY'] = ':0'
env['XDG_RUNTIME_DIR'] = '/run/user/1000'
COMMAND_ON = ["wlr-randr", "--output", "HDMI-A-1", "--on", "--mode", "1920x1080"]
COMMAND_OFF = ["wlr-randr", "--output", "HDMI-A-1", "--off"]
COMMAND_START_PICFRAME = ["/home/mickaelramilison/start_picframe.sh"]
COMMAND_STOP_PICFRAME = ["pkill", "-f", "picframe"]
COMMAND_SYSTEM_UPDATE = "sudo apt-get update && sudo apt-get upgrade -y"
COMMAND_REBOOT = ["sudo", "reboot"]

def is_manual_override_active():
    """Checks if the manual override flag file exists."""
    return os.path.exists(MANUAL_OVERRIDE_FLAG)

def is_picframe_running():
    """Checks if the picframe process is running."""
    try:
        result = subprocess.run(["pgrep", "-f", "picframe"], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False

def is_within_active_hours():
    """Checks if the current time is within the active hours."""
    current_hour = datetime.now().hour
    return ACTIVE_START_HOUR <= current_hour < ACTIVE_END_HOUR

def check_presence():
    """Scans for the user's phone via Wi-Fi and Bluetooth."""
    print("Scanning for phone...")
    try:
        command_wifi = ['sudo', 'nmap', '-sn', '192.168.1.0/24']
        result_wifi = subprocess.run(command_wifi, capture_output=True, text=True, timeout=60)
        if WIFI_MAC_ADDRESS.lower() in result_wifi.stdout.lower():
            print("Phone DETECTED on Wi-Fi.")
            return True
    except Exception as e:
        print(f"An error occurred during nmap scan: {e}")
    try:
        command_bt = ['sudo', 'l2ping', '-c', '1', BLUETOOTH_MAC_ADDRESS]
        result_bt = subprocess.run(command_bt, capture_output=True, text=True, timeout=10)
        if "1 sent, 1 received" in result_bt.stdout.lower():
            print("Phone DETECTED via Bluetooth.")
            return True
    except Exception as e:
        print(f"An error occurred during Bluetooth scan: {e}")
    print("Phone NOT found.")
    return False

# --- Main Loop ---
print("Initialization complete. Starting main loop...")
last_daily_reset = None

while True:
    # Daily Reset Logic
    now = datetime.now()
    today = date.today()
    if now.hour == 8 and today != last_daily_reset:
        print("It's 8 AM, performing daily reset...")
        if is_manual_override_active():
            os.remove(MANUAL_OVERRIDE_FLAG)
            print("Manual override flag removed.")

        if os.path.exists(REBOOT_FLAG):
            os.remove(REBOOT_FLAG)
            print("Daily reboot flag file has been removed.")

        last_daily_reset = today

    # Main Control Logic
    if is_manual_override_active():
        print("Manual override is active. Pausing for 60 seconds.")
        time.sleep(60)
        continue

    if not is_within_active_hours():
        print("Sleeping time. Ensuring screen and picframe are OFF.")
        subprocess.run(COMMAND_STOP_PICFRAME)
        subprocess.run(COMMAND_OFF, env=env)
        print(f"Waiting for {SLEEPING_SCAN_INTERVAL} seconds...")
        time.sleep(SLEEPING_SCAN_INTERVAL)
        continue

    phone_is_present = check_presence()

    if phone_is_present:
        if not is_picframe_running():
            print("User is home. Starting picframe and waiting 20s...")
            subprocess.Popen(COMMAND_START_PICFRAME, env=env)
            time.sleep(20)
            print("Turning screen ON.")
            subprocess.run(COMMAND_ON, env=env)
        else:
            print("User is home. Picframe already running, ensuring screen is ON.")
            subprocess.run(COMMAND_ON, env=env)

        print(f"Waiting for {HOME_SCAN_INTERVAL} seconds for next check...")
        time.sleep(HOME_SCAN_INTERVAL)
    else:
        print("User not detected. Waiting 5 minutes for confirmation before shutdown...")
        time.sleep(300)

        phone_is_still_present = check_presence()

        if phone_is_still_present:
            print("User re-detected. Aborting shutdown.")
            continue
        else:
            print("User still not detected after 5 minutes. Shutting down screen and picframe.")
            subprocess.run(COMMAND_STOP_PICFRAME)
            subprocess.run(COMMAND_OFF, env=env)

            if not os.path.exists(REBOOT_FLAG):
                print("Daily update has not been performed. Starting system update...")
                try:
                    # Create the flag file to prevent another reboot today
                    with open(REBOOT_FLAG, 'w') as f:
                        pass # Create an empty file

                    print(f"Reboot flag created at {REBOOT_FLAG}. Proceeding with update and reboot.")
                    subprocess.run(COMMAND_SYSTEM_UPDATE, shell=True, check=True)
                    print("System update successful. Rebooting now...")
                    subprocess.run(COMMAND_REBOOT)
                except subprocess.CalledProcessError as e:
                    print(f"An error occurred during system update: {e}")
                    print("Skipping reboot. The script will not attempt another update until tomorrow.")
                    print(f"Waiting for {AWAY_SCAN_INTERVAL} seconds...")
                    time.sleep(AWAY_SCAN_INTERVAL)
            else:
                print("Daily update & reboot already performed. Skipping.")
                print(f"Waiting for {AWAY_SCAN_INTERVAL} seconds...")
                time.sleep(AWAY_SCAN_INTERVAL)
