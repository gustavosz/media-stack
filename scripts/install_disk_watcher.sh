#!/usr/bin/env bash
# ==============================================================================
# Instalador del Daemon de Monitoreo y Auto-Recuperación de Discos (macOS)
# Registra disk_watcher.py como LaunchAgent en ~/Library/LaunchAgents/
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/disk_watcher.py" --install
