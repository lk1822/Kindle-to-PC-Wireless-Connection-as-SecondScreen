# Running on macOS

This app was originally written for Windows, but the code is cross-platform.
It runs on macOS with two small caveats handled below.

## Quick start (just double-click)

In Finder, double-click **`Start Kindle Mirror.command`**. It opens in Terminal,
sets everything up on first run, and launches the app. Because it runs in
Terminal, it reuses the Screen Recording permission you've already granted there.

> First time only: macOS may warn the file is from an unidentified developer.
> Right-click it → **Open** → **Open**, just once. After that a double-click works.

Equivalent from a terminal:

```bash
./run_mac.sh
```

On first run this creates a `.venv`, installs Pillow + websockets, and launches
the GUI. A browser window opens automatically. On your Kindle's Experimental
Browser, open the `http://<your-mac-ip>:8000/mirrorindex.html` URL shown in the
app window (both devices must be on the same Wi-Fi network).

## Fitting a wide monitor to the Kindle (crop to a region)

A wide/ultrawide monitor is a very different shape from the Kindle, so mirroring
the whole screen makes everything tiny with big empty bars. Instead you can send
just a Kindle-shaped slice of your screen:

1. In the app, tick **Crop to region**.
2. Pick a **Shape** that matches how you hold the Kindle — e.g.
   *Kindle portrait 3:4* (upright) or *Kindle landscape 4:3* (on its side).
   Choose *Free* to draw any rectangle.
3. Click **Select Region…**, then drag a box over the part of your screen you
   want on the Kindle. The box snaps to the chosen shape. (Esc cancels.)
4. **Reset to Full Screen** clears the crop.

The selected area then fills the Kindle at full size and sharpness. You can still
use the **🔄 Rotate** button on the Kindle page to match its orientation.

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

- Fixed a black-screen bug: macOS `ImageGrab.grab()` returns an RGBA image and
  JPEG can't store alpha, so every frame failed to encode. The capture loop now
  converts to RGB first (a no-op on Windows).
- Added a **crop-to-region** feature so a wide monitor can fill the Kindle
  instead of being letterboxed.
- Added **`Start Kindle Mirror.command`** for double-click launching from Finder.
- Network-interface diagnostics now use `ifconfig` on macOS/Linux instead of the
  Windows-only `ipconfig`.
- The capture loop prints a clear Screen Recording permission hint when
  `screencapture` is blocked.
- Troubleshooting tips are OS-aware (macOS permissions/firewall vs. Windows).

The core mirroring, HTTP, and WebSocket logic is unchanged —
`PIL.ImageGrab`, `tkinter`, and the `websockets` server all work on macOS.
