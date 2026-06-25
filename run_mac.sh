#!/usr/bin/env bash
# Launcher for the Kindle Screen Mirror server on macOS.
# Creates a local virtual environment on first run, installs dependencies,
# then starts the server GUI.
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
fi

# Make sure tkinter is available in this interpreter (needed for the GUI).
if ! .venv/bin/python -c "import tkinter" 2>/dev/null; then
  echo "ERROR: tkinter is not available in this Python build."
  echo "Install a Python that includes Tk, e.g.:  brew install python-tk"
  exit 1
fi

echo "Installing/updating dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet "pillow>=9.0.0" "websockets>=11.0.0"

echo "Starting Screen Mirror Server..."
echo "If the screen looks black or capture errors appear, grant Screen Recording"
echo "permission to your Terminal/IDE (System Settings > Privacy & Security >"
echo "Screen Recording), then fully quit and reopen it."
exec .venv/bin/python mirror_server.py
