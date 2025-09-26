#!/usr/bin/python3
from flask import Flask, redirect, render_template_string, Response
import subprocess
import os
from datetime import datetime
import time
import json
import psutil

app = Flask(__name__)

# --- CONFIGURATION ---
PRESENCE_SCRIPT_NAME = "presence_detector.py"
PATH_TO_PRESENCE_SCRIPT = f"/home/mickaelramilison/{PRESENCE_SCRIPT_NAME}"
COMMAND_START_PICFRAME = ["/home/mickaelramilison/start_picframe.sh"]
# Use the user's home directory for a persistent flag
USER_HOME = os.path.expanduser("~") # Gets /home/mickaelramilison
MANUAL_OVERRIDE_FLAG = os.path.join(USER_HOME, "manual_override.flag")

# --- Environment ---
env = os.environ.copy()
env["DISPLAY"] = ":0"
env["XDG_RUNTIME_DIR"] = "/run/user/1000"

# --- HTML TEMPLATE (Unchanged) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pi Controller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; background-color: #222; color: #eee; text-align: center; }
        .button { background-color: #444; border: none; color: white; padding: 20px;
                  text-align: center; font-size: 16px; margin: 10px 2px;
                  cursor: pointer; border-radius: 12px; width: 80%; max-width: 400px; }
        .button-auto { background-color: #27ae60; }
        .button-manual-red { background-color: #c0392b; }
        .button-danger { background-color: #c0392b; }
        .stats-container {
            display: flex; justify-content: space-around; align-items: center;
            flex-wrap: wrap; background-color: #333; padding: 15px;
            border-radius: 12px; margin: 20px auto; width: 80%; max-width: 400px;
        }
        .stat-item { flex: 1; min-width: 100px; }
        .stat-item h3 { margin: 0 0 5px 0; font-size: 14px; color: #aaa; }
        .stat-item p { margin: 0; font-size: 20px; font-weight: bold; color: #fff; }
    </style>
</head>
<body>
    <h1>Pi Frame Controller</h1>
    <div class="stats-container">
        <div class="stat-item"><h3>CPU Usage</h3><p id="cpu-usage">--%</p></div>
        <div class="stat-item"><h3>Memory</h3><p id="mem-usage">--%</p></div>
        <div class="stat-item"><h3>CPU Temp</h3><p id="temp-value">--°C</p></div>
    </div>
    <a href="/screen/on"><button class="button">Force Screen ON</button></a>
    <a href="/screen/off"><button class="button">Force Screen OFF</button></a>
    {% if current_mode == 'Auto' %}
        <a href="/screen/off"><button class="button button-auto">Auto Mode: ON</button></a>
    {% else %}
        <a href="/screen/auto"><button class="button button-manual-red">Auto Mode: OFF</button></a>
    {% endif %}
    <hr style="border-color: #444; margin: 30px auto; width: 80%;">
    <a href="/reboot" onclick="return confirm('Are you sure you want to reboot?')"><button class="button button-danger">Reboot Pi</button></a>
    <script>
        window.onload = function() {
            const cpuUsage = document.getElementById('cpu-usage');
            const memUsage = document.getElementById('mem-usage');
            const tempValue = document.getElementById('temp-value');
            const statsSource = new EventSource("/system-stats");
            statsSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                cpuUsage.innerText = data.cpu.toFixed(1) + '%';
                memUsage.innerText = data.mem.toFixed(1) + '%';
                tempValue.innerText = data.temp.toFixed(1) + '°C';
            };
        };
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    if os.path.exists(MANUAL_OVERRIDE_FLAG):
        current_mode = "Manual"
    else:
        current_mode = "Auto"
    return render_template_string(HTML_TEMPLATE, current_mode=current_mode)

@app.route("/screen/<state>")
def screen_control(state):
    if state == "on":
        print("Forcing screen ON and entering Manual Mode.")
        # MODIFIED: Do NOT kill the presence script. Just create the flag.
        # The presence script will see the flag and pause itself.
        with open(MANUAL_OVERRIDE_FLAG, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))

        print("Launching picframe...")
        subprocess.Popen(COMMAND_START_PICFRAME, env=env)

        print("Waiting 20 seconds for picframe to load...")
        time.sleep(20)

        print("Turning screen on.")
        subprocess.run(["wlr-randr", "--output", "HDMI-A-1", "--on", "--mode", "1920x1080"], env=env)

    elif state == "off":
        print("Forcing screen OFF and entering Manual Mode.")
        # MODIFIED: Do NOT kill the presence script. Just create the flag.
        with open(MANUAL_OVERRIDE_FLAG, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))

        subprocess.run(["pkill", "-f", "picframe"])
        subprocess.run(["wlr-randr", "--output", "HDMI-A-1", "--off"], env=env)

    elif state == "auto":
        print("Enabling Automatic Mode.")
        # MODIFIED: Kill any running detector before starting a new one to prevent duplicates.
        subprocess.run(["pkill", "-9", "-f", PRESENCE_SCRIPT_NAME])
        # Remove the flag to allow the new script to take control.
        if os.path.exists(MANUAL_OVERRIDE_FLAG):
            os.remove(MANUAL_OVERRIDE_FLAG)

        subprocess.run(["pkill", "-f", "picframe"])
        subprocess.Popen(["python3", PATH_TO_PRESENCE_SCRIPT], env=env)

    return redirect("/")

# --- (The rest of the script is the same) ---
def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except Exception:
        return 0.0

@app.route("/system-stats")
def system_stats():
    def generate_stats():
        while True:
            try:
                stats = { "cpu": psutil.cpu_percent(interval=1), "mem": psutil.virtual_memory().percent, "temp": get_cpu_temperature() }
                yield f"data: {json.dumps(stats)}\n\n"
                time.sleep(2)
            except GeneratorExit:
                break
    return Response(generate_stats(), mimetype="text/event-stream")

@app.route("/reboot")
def reboot_system():
    subprocess.run(["sudo", "reboot"])
    return "<h1>Rebooting...</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
