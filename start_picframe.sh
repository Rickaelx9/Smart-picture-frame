#!/bin/bash
# Set monitor brightness to minimum (e.g., 0)
ddcutil setvcp 10 0

# Run picframe using its full, absolute path
/home/mickaelramilison/venv_picframe/bin/picframe
