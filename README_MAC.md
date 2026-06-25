# Running on macOS

This app was originally written for Windows, but the code is cross-platform.
It runs on macOS with two small caveats handled below.

## Quick start

```bash
./run_mac.sh
```

On first run this creates a `.venv`, installs Pillow + websockets, and launches
the GUI. A browser window opens automatically. On your Kindle's Experimental
Browser, open the `http://<your-mac-ip>:8000/mirrorindex.html` URL shown in the
app window (both devices must be on the same Wi-Fi network).

## 1. Screen Recording permission (required)

macOS blocks screen capture until you explicitly allow it. Without this you'll
see "Screen capture blocked" and the Kindle shows a black screen.

1. Open **System Settings > Privacy & Security > Screen Recording**.
2. Enable the app you launch the script from (e.g. **Terminal**, **iTerm**, or
   your IDE). If it isn't listed, run the app once so macOS adds it.
3. **Fully quit and reopen** that app (Cmd+Q — a restart of the terminal is
   required for the permission to take effect).
4. Run `./run_mac.sh` again.

## 2. Firewall (only if the Kindle can't connect)

If your Mac firewall is on, allow incoming connections for Python:
**System Settings > Network > Firewall** — allow `python` when prompted, or
temporarily turn the firewall off to test.

## Manual setup (instead of run_mac.sh)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "pillow>=9.0.0" "websockets>=11.0.0"
python mirror_server.py
```

> If `python3 -c "import tkinter"` fails, your Python lacks Tk. Install one that
> includes it, e.g. `brew install python-tk`, or use the python.org installer.

## What was changed for macOS

- Network-interface diagnostics now use `ifconfig` on macOS/Linux instead of the
  Windows-only `ipconfig`.
- The capture loop prints a clear Screen Recording permission hint when
  `screencapture` is blocked.
- Troubleshooting tips are OS-aware (macOS permissions/firewall vs. Windows).

No changes were needed to the core mirroring, HTTP, or WebSocket logic —
`PIL.ImageGrab`, `tkinter`, and the `websockets` server all work on macOS.
