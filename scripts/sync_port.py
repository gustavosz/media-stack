#!/usr/bin/env python3
"""
Sincronizador automático de puerto ProtonVPN (Gluetun) -> qBittorrent.
Lee el puerto asignado por NAT-PMP en Gluetun y lo actualiza en qBittorrent vía API
sin reiniciar contenedores ni cortar descargas activas.
"""
import sys
import time
import json
import urllib.request
import urllib.parse
import subprocess
from datetime import datetime

PROJECT_DIR = "/Users/gsoliz/Code/media-stack"
QBITTORRENT_URL = "http://localhost:8080"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def get_forwarded_port(max_retries=6, delay=3):
    for i in range(max_retries):
        try:
            cmd = ["docker", "compose", "-f", f"{PROJECT_DIR}/docker-compose.yml", "exec", "gluetun", "cat", "/tmp/gluetun/forwarded_port"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            if out.isdigit() and int(out) > 0:
                return int(out)
        except Exception:
            pass
        time.sleep(delay)
    return None

def get_qbittorrent_port():
    try:
        req = urllib.request.Request(f"{QBITTORRENT_URL}/api/v2/app/preferences")
        res = urllib.request.urlopen(req, timeout=5)
        data = json.loads(res.read().decode())
        return data.get("listen_port")
    except Exception as e:
        log(f"Error conectando a qBittorrent: {e}")
        return None

def set_qbittorrent_port(port):
    try:
        payload = urllib.parse.urlencode({"json": json.dumps({"listen_port": port})}).encode()
        req = urllib.request.Request(f"{QBITTORRENT_URL}/api/v2/app/setPreferences", data=payload)
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        log(f"Error actualizando puerto en qBittorrent: {e}")
        return False

def sync():
    forwarded = get_forwarded_port()
    if not forwarded:
        log("Aviso: No se pudo obtener el puerto de ProtonVPN (Gluetun aún conectando o apagado).")
        return False

    current = get_qbittorrent_port()
    if current is None:
        log("Aviso: No se pudo conectar a la WebUI de qBittorrent.")
        return False

    if current != forwarded:
        log(f"🔄 Desajuste detectado: qBittorrent escucha en {current}, pero ProtonVPN asignó {forwarded}.")
        if set_qbittorrent_port(forwarded):
            log(f"✅ Puerto de qBittorrent actualizado exitosamente a: {forwarded}")
            return True
        else:
            return False
    else:
        log(f"✅ Puerto verificado y sincronizado ({current}). Todo óptimo.")
        return True

if __name__ == "__main__":
    success = sync()
    sys.exit(0 if success else 1)
