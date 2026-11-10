#!/usr/bin/env bash
# ==============================================================================
# Desinstalador del Daemon de Monitoreo y Auto-Recuperación de Discos (macOS)
# Detiene el servicio y elimina el LaunchAgent
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/disk_watcher.py" --uninstall
