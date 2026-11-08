#!/usr/bin/env python3
"""
Media Stack Auto-Recovery Disk Watcher
Monitors the external drive (/Volumes/Media) and Docker container mounts.
When the disk is disconnected and reconnected, or if containers suffer a stale mount,
it automatically restarts the affected containers and refreshes Jellyfin.
"""

import os
import sys
import time
import subprocess
import datetime
from pathlib import Path

PROJECT_DIR = Path("/Users/gsoliz/Code/media-stack")
COMPOSE_FILE = PROJECT_DIR / "docker-compose.yml"
MEDIA_DIR = Path("/Volumes/Media/data/media")
LOG_FILE = PROJECT_DIR / "config" / "disk_watcher.log"

AFFECTED_CONTAINERS = [
    "jellyfin", "radarr", "sonarr", "bazarr",
    "qbittorrent", "chaptarr", "calibre-web"
]

def log(msg: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def notify_macos(title: str, message: str):
    """Sends a native macOS notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass

def is_disk_accessible() -> bool:
    """Checks if the external media volume /Volumes/Media is mounted using macOS DiskArbitration."""
    try:
        res = subprocess.run(
            ["/usr/sbin/diskutil", "info", "/Volumes/Media"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode != 0:
            return False
        return "Mounted:                   Yes" in res.stdout or "Mounted:                  Yes" in res.stdout or "Mounted: Yes" in res.stdout
    except Exception as e:
        log(f"Debug disk access error: {type(e).__name__}: {e}")
        return False

def check_container_mount_stale() -> bool:
    """
    Checks if containers running in Docker have stale mount handles.
    If the host has the disk mounted, but jellyfin cannot read files in /data/media/movies,
    the mount inside the container is stale.
    """
    try:
        chk = subprocess.run(
            ["docker", "exec", "jellyfin", "ls", "-A", "/data/media/movies"],
            capture_output=True, text=True, timeout=5
        )
        if chk.returncode != 0:
            return True
        container_files = [f for f in chk.stdout.strip().splitlines() if f]
        return len(container_files) == 0
    except Exception:
        return False

def recover_stack():
    """Restarts the affected containers and refreshes the library."""
    log("Iniciando recuperación automática del stack...")
    notify_macos("Media Stack", "Disco detectado. Reconectando servicios y restaurando reproducción...")
    
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "restart"] + AFFECTED_CONTAINERS
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode == 0:
            log("Contenedores reiniciados exitosamente.")
        else:
            log(f"Advertencia al reiniciar contenedores: {res.stderr.strip()}")
    except Exception as e:
        log(f"Error reiniciando contenedores: {e}")

    # Give Jellyfin 3 seconds to boot up then trigger library scan
    time.sleep(3)
    try:
        refresh_cmd = [
            "curl", "-s", "-X", "POST", "http://localhost:8096/Library/Refresh",
            "-H", "X-Emby-Token: 4a6d8f1e2b3c4d5e6f7a8b9c0d1e2f3a"
        ]
        subprocess.run(refresh_cmd, capture_output=True, timeout=10)
        log("Escaneo de biblioteca Jellyfin solicitado.")
    except Exception as e:
        log(f"No se pudo solicitar escaneo a Jellyfin: {e}")

    log("Recuperación automática completada con éxito.")
    notify_macos("Media Stack", "Servicios restaurados y listos para reproducir en la TV.")

def main():
    log("Iniciando daemon de monitoreo de disco y auto-recuperación (disk_watcher)...")
    disk_was_connected = is_disk_accessible()
    log(f"Estado inicial del disco: {'CONECTADO' if disk_was_connected else 'DESCONECTADO'}")

    last_container_check = 0

    while True:
        try:
            currently_connected = is_disk_accessible()

            # Caso 1: Estaba desconectado y acaba de reconectarse
            if not disk_was_connected and currently_connected:
                log("¡Disco externo reconectado! Esperando 4 segundos a que macOS estabilice el sistema de archivos...")
                time.sleep(4)
                if is_disk_accessible():
                    recover_stack()
                    disk_was_connected = True
                else:
                    log("El disco volvió a desaparecer durante la estabilización.")

            # Caso 2: Se acaba de desconectar
            elif disk_was_connected and not currently_connected:
                log("ATENCIÓN: El disco externo /Volumes/Media se ha desconectado.")
                notify_macos("Media Stack", "El disco externo se ha desconectado.")
                disk_was_connected = False

            # Caso 3: El disco está conectado, verificar periódicamente (cada 30s) si los contenedores sufrieron stale mount
            elif currently_connected:
                now = time.time()
                if now - last_container_check >= 30:
                    last_container_check = now
                    if check_container_mount_stale():
                        log("ALERTA: Se detectó una montura caída (stale mount) dentro de los contenedores.")
                        recover_stack()

            time.sleep(5)
        except KeyboardInterrupt:
            log("Deteniendo disk_watcher por señal del usuario.")
            break
        except Exception as e:
            log(f"Error inesperado en loop de monitoreo: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
