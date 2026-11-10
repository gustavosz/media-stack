#!/bin/bash
echo "[custom-init] Starting book auto-import watcher daemon..."
(
  # Give container services 5 seconds to initialize
  sleep 5
  while true; do
    python3 /app/auto_import.py >> /config/auto_import.log 2>&1
    sleep 5
  done
) &
echo "[custom-init] Book auto-import watcher daemon started in background."
