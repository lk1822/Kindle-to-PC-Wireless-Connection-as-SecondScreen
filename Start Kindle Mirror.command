#!/bin/bash
# Double-click this file in Finder to start Kindle Mirror.
# macOS opens it in Terminal, which already has your Screen Recording
# permission, so capture works without any extra setup. On first run it
# creates the local Python environment and installs dependencies.
cd "$(dirname "$0")" || exit 1

echo "Starting Kindle Mirror..."
./run_mac.sh

# Keep the window open if the server exits so any message stays readable.
echo
echo "Kindle Mirror has stopped. You can close this window."
