#!/usr/bin/python3
from flask import Flask, redirect, render_template_string, Response, jsonify
import subprocess
import os
from datetime import datetime
import time
import json
import psutil
import re # Import the regular expression module

app = Flask(__name__)

# --- CONFIGURATION ---
PRESENCE_SCRIPT_NAME = "presence_detector.py"
PATH_TO_PRESENCE_SCRIPT = f"/home/mickaelramilison/{PRESENCE_SCRIPT_NAME}"
COMMAND_START_PICFRAME = ["/home/mickaelramilison/start_picframe.sh"]
USER_HOME = os.path.expanduser("~")
MANUAL_OVERRIDE_FLAG = os.path.join(USER_HOME, "manual_override.flag")

# --- Environment ---
env = os.environ.copy()
env["DISPLAY"] = ":0"
env["XDG_RUNTIME_DIR"] = "/run/user/1000"

# --- HTML TEMPLATE (MODIFIED) ---
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
        .container {
            background-color: #333; padding: 15px; border-radius: 12px;
            margin: 20px auto; width: 80%; max-width: 400px;
        }
        .stats-container {
            display: flex; justify-content: space-around; align-items: center;
            flex-wrap: wrap;
        }
        .stat-item { flex: 1; min-width: 100px; }
        .stat-item h3 { margin: 0 0 5px 0; font-size: 14px; color: #aaa; }
        .stat-item p { margin: 0; font-size: 20px; font-weight: bold; color: #fff; }
        .slider-label { font-size: 14px; color: #aaa; margin-bottom: 10px; }
        .slider { -webkit-appearance: none; width: 90%; height: 15px;
                  background: #555; outline: none; border-radius: 5px;
                  opacity: 0.7; -webkit-transition: .2s; transition: opacity .2s; }
        .slider:hover { opacity: 1; }
        .slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none;
                                        width: 25px; height: 25px; background: #27ae60;
                                        cursor: pointer; border-radius: 50%; }
        hr { border-color: #444; margin: 30px auto; width: 80%; }
    </style>
</head>
<body>
    <h1>Pi Frame Controller</h1>
    <div class="container stats-container">
        <div class="stat-item"><h3>CPU Usage</h3><p id="cpu-usage">--%</p></div>
        <div class="stat-item"><h3>Memory</h3><p id="mem-usage">--%</p></div>
        <div class="stat-item"><h3>CPU Temp</h3><p id="temp-value">--°C</p></div>
    </div>

    <div class="container">
        <label for="brightness" class="slider-label">Brightness: <span id="brightness-value">{{ initial_brightness }}</span>%</label>
        <input type="range" min="0" max="100" value="{{ initial_brightness }}" class="slider" id="brightness-slider">
    </div>

    <a href="/screen/on"><button class="button">Force Screen ON</button></a>
    <a href="/screen/off"><button class="button">Force Screen OFF</button></a>
    {% if current_mode == 'Auto' %}
        <a href="/screen/off"><button class="button button-auto">Auto Mode: ON</button></a>
    {% else %}
        <a href="/screen/auto"><button class="button button-manual-red">Auto Mode: OFF</button></a>
    {% endif %}
    <hr>
    <a href="/reboot" onclick="return confirm('Are you sure you want to reboot?')"><button class="button button-danger">Reboot Pi</button></a>
    <script>
        // System Stats SSE
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

            // NEW: Brightness Slider Logic
            const brightnessSlider = document.getElementById('brightness-slider');
            const brightnessValue = document.getElementById('brightness-value');

            // Update text display as slider moves
            brightnessSlider.addEventListener('input', function() {
                brightnessValue.innerText = this.value;
            });

            // Send command to server when user releases the slider
            brightnessSlider.addEventListener('change', function() {
                const level = this.value;
                fetch('/brightness/set/' + level)
                    .then(response => response.json())
                    .then(data => console.log('Brightness set:', data));
            });
        };
    </script>
</body>
</html>
"""

# --- HELPER FUNCTIONS ---

def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except Exception:
        return 0.0

# NEW: Function to get current screen brightness
def get_brightness():
    """Gets brightness using ddcutil and parses the output."""
    try:
        # Run ddcutil to get VCP feature 10 (brightness)
        result = subprocess.run(
            ["ddcutil", "getvcp", "10"],
            capture_output=True, text=True, check=True, env=env
        )
        # Use regex to find "current value =    xx"
        match = re.search(r"current value\s*=\s*(\d+)", result.stdout)
        if match:
            return int(match.group(1))
        return 50 # Return a default value if parsing fails
    except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
        print(f"Error getting brightness: {e}")
        return 50 # Return a default value on error

# --- FLASK ROUTES ---

@app.route("/")
def index():
    current_mode = "Manual" if os.path.exists(MANUAL_OVERRIDE_FLAG) else "Auto"
    initial_brightness = get_brightness() # Get brightness on page load
    return render_template_string(
        HTML_TEMPLATE,
        current_mode=current_mode,
        initial_brightness=initial_brightness
    )

# NEW: Route to set brightness
@app.route("/brightness/set/<int:level>")
def set_brightness(level):
    """Sets screen brightness using ddcutil."""
    if 0 <= level <= 100:
        try:
            subprocess.run(
                ["ddcutil", "setvcp", "10", str(level)],
                check=True, env=env
            )
            return jsonify({"status": "success", "level": level})
        except (subprocess.CalledProcessError, FileNotFoundError, Exception) as e:
            print(f"Error setting brightness: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "Value out of range"}), 400

@app.route("/screen/<state>")
def screen_control(state):
    # This function remains unchanged
    if state == "on":
        print("Forcing screen ON and entering Manual Mode.")
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
        with open(MANUAL_OVERRIDE_FLAG, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))
        subprocess.run(["pkill", "-f", "picframe"])
        subprocess.run(["wlr-randr", "--output", "HDMI-A-1", "--off"], env=env)
    elif state == "auto":
        print("Enabling Automatic Mode.")
        subprocess.run(["pkill", "-9", "-f", PRESENCE_SCRIPT_NAME])
        if os.path.exists(MANUAL_OVERRIDE_FLAG):
            os.remove(MANUAL_OVERRIDE_FLAG)
        subprocess.run(["pkill", "-f", "picframe"])
        subprocess.Popen(["python3", PATH_TO_PRESENCE_SCRIPT], env=env)
    return redirect("/")

@app.route("/system-stats")
def system_stats():
    # This function remains unchanged
    def generate_stats():
        while True:
            try:
                stats = {
                    "cpu": psutil.cpu_percent(interval=1),
                    "mem": psutil.virtual_memory().percent,
                    "temp": get_cpu_temperature()
                }
                yield f"data: {json.dumps(stats)}\n\n"
                time.sleep(2)
            except GeneratorExit:
                break
    return Response(generate_stats(), mimetype="text/event-stream")

@app.route("/reboot")
def reboot_system():
    # This function remains unchanged
    subprocess.run(["sudo", "reboot"])
    return "<h1>Rebooting...</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
