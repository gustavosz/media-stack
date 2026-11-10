#!/usr/bin/env python3
"""
Media Stack Auto-Recovery Disk Watcher
Monitors the external drive (configured in .env / DATA_DIR) and Docker container mounts.
When the disk is disconnected and reconnected, or if containers suffer a stale mount,
it automatically restarts the affected containers and refreshes Jellyfin.

Usage:
    python3 disk_watcher.py              # Run in foreground
    python3 disk_watcher.py --install    # Install and start as macOS LaunchAgent daemon
    python3 disk_watcher.py --uninstall  # Stop and remove LaunchAgent daemon
    python3 disk_watcher.py --status     # Check daemon status
"""

import os
import sys
import time
import subprocess
import datetime
import json
from pathlib import Path

# ------------------------------------------------------------------------------
# Dynamic Configuration & Environment Loading
# ------------------------------------------------------------------------------
def load_env(env_path: Path):
    """Loads key=value pairs from a .env file into os.environ if not already set."""
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", Path(__file__).resolve().parent.parent))
load_env(PROJECT_DIR / ".env")

COMPOSE_FILE = PROJECT_DIR / "docker-compose.yml"

config_dir_env = os.getenv("CONFIG_DIR", "./config")
CONFIG_DIR = Path(config_dir_env) if Path(config_dir_env).is_absolute() else (PROJECT_DIR / config_dir_env)
LOG_FILE = CONFIG_DIR / "disk_watcher.log"

data_dir_env = os.getenv("DATA_DIR", "/Volumes/Media/data")
DATA_DIR = Path(data_dir_env)

AFFECTED_CONTAINERS = [
    "jellyfin", "radarr", "sonarr", "bazarr",
    "qbittorrent", "chaptarr", "calibre-web"
]

SERVICE_LABEL = "com.media-stack.disk-watcher"

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def get_disk_mount_path() -> Path:
    """
    Determines the mount point of the external drive.
    Uses EXTERNAL_DISK_MOUNT if defined; otherwise extracts the volume root
    from DATA_DIR (e.g. /Volumes/Media from /Volumes/Media/data).
    """
    mount_env = os.getenv("EXTERNAL_DISK_MOUNT")
    if mount_env:
        return Path(mount_env)
    parts = DATA_DIR.parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "Volumes":
        return Path("/Volumes") / parts[2]
    return DATA_DIR

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
    if sys.platform != "darwin":
        return
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass

def is_disk_accessible() -> bool:
    """Checks if the external media volume is mounted using macOS DiskArbitration."""
    mount_path = get_disk_mount_path()
    try:
        if sys.platform == "darwin":
            res = subprocess.run(
                ["/usr/sbin/diskutil", "info", str(mount_path)],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode != 0:
                return False
            out = res.stdout
            return "Mounted:                   Yes" in out or "Mounted:                  Yes" in out or "Mounted: Yes" in out
        else:
            return mount_path.exists() and os.access(str(mount_path), os.R_OK)
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

def get_jellyfin_api_key() -> str:
    """Retrieves Jellyfin API key from env or from existing service configs."""
    token = os.getenv("JELLYFIN_API_KEY")
    if token:
        return token
    
    # Try reading from jellyseerr settings
    jellyseerr_settings = CONFIG_DIR / "jellyseerr" / "settings.json"
    if jellyseerr_settings.is_file():
        try:
            with open(jellyseerr_settings, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("apiKey")
                if key:
                    return key
        except Exception:
            pass

    # Try reading from bazarr config
    bazarr_config = CONFIG_DIR / "bazarr" / "config" / "config.yaml"
    if bazarr_config.is_file():
        try:
            with open(bazarr_config, "r", encoding="utf-8") as f:
                for line in f:
                    if "apikey:" in line:
                        return line.split("apikey:")[-1].strip()
        except Exception:
            pass

    return ""

def recover_stack():
    """Restarts the affected containers and refreshes the library."""
    mount_path = get_disk_mount_path()
    log(f"Iniciando recuperación automática del stack para volumen {mount_path}...")
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
        token = get_jellyfin_api_key()
        headers = ["-H", f"X-Emby-Token: {token}"] if token else []
        refresh_cmd = ["curl", "-s", "-X", "POST", "http://localhost:8096/Library/Refresh"] + headers
        subprocess.run(refresh_cmd, capture_output=True, timeout=10)
        log("Escaneo de biblioteca Jellyfin solicitado.")
    except Exception as e:
        log(f"No se pudo solicitar escaneo a Jellyfin: {e}")

    log("Recuperación automática completada con éxito.")
    notify_macos("Media Stack", "Servicios restaurados y listos para reproducir en la TV.")

# ------------------------------------------------------------------------------
# LaunchAgent Installer / Uninstaller (macOS)
# ------------------------------------------------------------------------------
def get_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"

def install_daemon():
    if sys.platform != "darwin":
        print("La instalación como LaunchAgent solo está soportada en macOS.")
        sys.exit(1)

    plist_path = get_plist_path()
    plist_dir = plist_path.parent
    plist_dir.mkdir(parents=True, exist_ok=True)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_log = CONFIG_DIR / "disk_watcher_stdout.log"
    stderr_log = CONFIG_DIR / "disk_watcher_stderr.log"
    script_path = Path(__file__).resolve()

    # Unload any previous version (including legacy label com.gusz.media-stack.disk-watcher)
    legacy_plist = Path.home() / "Library" / "LaunchAgents" / "com.gusz.media-stack.disk-watcher.plist"
    if legacy_plist.exists():
        subprocess.run(["launchctl", "unload", str(legacy_plist)], capture_output=True)
        try:
            legacy_plist.unlink()
        except Exception:
            pass

    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{PROJECT_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
</dict>
</plist>
"""
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist_content)

    res = subprocess.run(["launchctl", "load", "-w", str(plist_path)], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✅ Daemon instalado y activado exitosamente en: {plist_path}")
        print(f"   Logs: {LOG_FILE}")
    else:
        print(f"❌ Error al cargar daemon con launchctl: {res.stderr.strip()}")
        sys.exit(1)

def uninstall_daemon():
    if sys.platform != "darwin":
        print("La desinstalación como LaunchAgent solo aplica a macOS.")
        sys.exit(1)

    plist_path = get_plist_path()
    legacy_plist = Path.home() / "Library" / "LaunchAgents" / "com.gusz.media-stack.disk-watcher.plist"

    for p in [plist_path, legacy_plist]:
        if p.exists():
            subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
            p.unlink(missing_ok=True)
            print(f"✅ Daemon detenido y eliminado: {p}")
        else:
            print(f"ℹ️ No se encontró plist en: {p}")

def status_daemon():
    res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    found = False
    for line in res.stdout.splitlines():
        if "disk-watcher" in line:
            print(f"Estado en launchctl: {line}")
            found = True
    if not found:
        print("El daemon no está registrado actualmente en launchctl.")

# ------------------------------------------------------------------------------
# Main Monitoring Loop
# ------------------------------------------------------------------------------
def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--install", "-i"]:
            install_daemon()
            return
        elif arg in ["--uninstall", "-u"]:
            uninstall_daemon()
            return
        elif arg in ["--status", "-s"]:
            status_daemon()
            return
        elif arg in ["--help", "-h"]:
            print(__doc__)
            return

    mount_path = get_disk_mount_path()
    log(f"Iniciando daemon de monitoreo de disco y auto-recuperación...")
    log(f"Directorio de proyecto: {PROJECT_DIR}")
    log(f"Volumen monitoreado: {mount_path} (DATA_DIR: {DATA_DIR})")

    disk_was_connected = is_disk_accessible()
    log(f"Estado inicial del disco: {'CONECTADO' if disk_was_connected else 'DESCONECTADO'}")

    last_container_check = 0

    while True:
        try:
            currently_connected = is_disk_accessible()

            # Caso 1: Estaba desconectado y acaba de reconectarse
            if not disk_was_connected and currently_connected:
                log(f"¡Disco externo ({mount_path}) reconectado! Esperando 4 segundos a que macOS estabilice el sistema de archivos...")
                time.sleep(4)
                if is_disk_accessible():
                    recover_stack()
                    disk_was_connected = True
                else:
                    log("El disco volvió a desaparecer durante la estabilización.")

            # Caso 2: Se acaba de desconectar
            elif disk_was_connected and not currently_connected:
                log(f"ATENCIÓN: El disco externo ({mount_path}) se ha desconectado.")
                notify_macos("Media Stack", f"El disco externo ({mount_path.name}) se ha desconectado.")
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
