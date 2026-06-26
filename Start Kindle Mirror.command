#!/bin/bash
# Double-click this file in Finder to start Kindle Mirror.
# macOS opens it in Terminal, which already has your Screen Recording
# permission, so capture works without any extra setup. On first run it
# creates the local Python environment and installs dependencies.
cd "$(dirname "$0")" || exit 1

# Remember which Terminal tab this is so we can close it when the app exits.
MY_TTY="$(tty)"

echo "Starting Kindle Mirror..."
./run_mac.sh

# The app has exited (you closed the GUI window). Close the Terminal window
# that launched it so nothing is left running in the background.
osascript >/dev/null 2>&1 <<OSA
tell application "Terminal"
    repeat with w in windows
        repeat with t in tabs of w
            try
                if tty of t is "$MY_TTY" then close w saving no
            end try
        end repeat
    end repeat
end tell
OSA
