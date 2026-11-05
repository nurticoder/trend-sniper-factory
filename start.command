#!/bin/sh
# macOS: double-click this file from Finder after the one-time installation.
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/trend-sniper ]; then
  echo 'One-time setup is needed. Follow the dashboard quick start in README.md.'
  exit 1
fi
# Open the browser once the local server responds; no internet connection needed.
.venv/bin/python -c 'import time, urllib.request, webbrowser
for attempt in range(60):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=1) as response:
            if response.status == 200:
                webbrowser.open("http://127.0.0.1:8765")
                break
    except OSError:
        time.sleep(0.25)' &
exec .venv/bin/trend-sniper serve
