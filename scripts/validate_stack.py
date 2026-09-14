#!/usr/bin/env python3
"""
Herramienta de diagnóstico y validación para el Media Stack.
Audita:
1. Estado de los contenedores Docker.
2. VPN ProtonVPN (Gluetun) y sincronización del puerto en qBittorrent.
3. Conectividad y salud de las APIs de todos los servicios (*Arr, Jellyfin, Jellyseerr).
4. Integridad de la biblioteca multimedia:
   - Verificación de Hardlinks atómicos en APFS (0 duplicación de espacio).
   - Detección de subtítulos en español (externos .srt e incrustados).
   - Estado de reconocimiento en Jellyfin.

Uso:
    python3 scripts/validate_stack.py          # Auditoría completa
    python3 scripts/validate_stack.py --subs   # Solo auditoría de subtítulos y películas
    python3 scripts/validate_stack.py --net    # Solo VPN y sincronización de puertos
"""

import os
import sys
import json
import re
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from xml.etree import ElementTree

PROJECT_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = Path("/Volumes/Media/data/media/movies")
CONFIG_DIR = PROJECT_DIR / "config"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")

def get_api_key_from_xml(xml_path):
    try:
        tree = ElementTree.parse(xml_path)
        root = tree.getroot()
        key_elem = root.find("ApiKey")
        if key_elem is not None:
            return key_elem.text
    except Exception:
        pass
    return None

def get_bazarr_api_key():
    yaml_path = CONFIG_DIR / "bazarr" / "config" / "config.yaml"
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            for line in f:
                if "apikey:" in line:
                    return line.split("apikey:")[-1].strip()
    except Exception:
        pass
    return None

def api_get(url, headers=None, timeout=4):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            try:
                return json.loads(raw), res.status
            except Exception:
                return raw, res.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, None

def check_docker_containers():
    print_header("1. ESTADO DE CONTENEDORES DOCKER")
    expected = [
        "gluetun", "qbittorrent", "gluetun-sync", "prowlarr",
        "flaresolverr", "radarr", "sonarr", "bazarr",
        "jellyfin", "jellyseerr"
    ]
    try:
        res = subprocess.run(
            ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "ps", "--format", "json"],
            capture_output=True, text=True, check=True
        )
        lines = [json.loads(line) for line in res.stdout.strip().splitlines() if line.strip()]
        running = {item.get("Service"): item.get("State") for item in lines}
        
        all_ok = True
        for name in expected:
            state = running.get(name, "no creado / apagado")
            if state in ("running", "healthy"):
                print(f"  {GREEN}✔{RESET} {name:<16} : {GREEN}{state}{RESET}")
            else:
                all_ok = False
                print(f"  {RED}✘{RESET} {name:<16} : {RED}{state}{RESET}")

        # Comprobar si las monturas de disco externo /data están activas dentro del contenedor
        print(f"\n  {BOLD}Puntos de montaje de almacenamiento (/data):{RESET}")
        stale_containers = []
        for name in ["jellyfin", "radarr", "sonarr", "bazarr", "qbittorrent"]:
            if running.get(name) in ("running", "healthy"):
                test_dir = "/data/media" if name in ("bazarr", "jellyfin") else ("/data/torrents" if name == "qbittorrent" else "/data")
                chk = subprocess.run(
                    ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "exec", "-T", name, "test", "-d", test_dir],
                    capture_output=True
                )
                if chk.returncode == 0:
                    print(f"  {GREEN}✔{RESET} {name:<16} : {GREEN}Montura activa ({test_dir}){RESET}")
                else:
                    all_ok = False
                    stale_containers.append(name)
                    print(f"  {RED}✘{RESET} {name:<16} : {RED}DESCONECTADA (stale mount en {test_dir}){RESET}")

        if stale_containers:
            print(f"\n  {YELLOW}⚠ Detectadas monturas caídas en: {', '.join(stale_containers)}.{RESET}")
            print(f"  {YELLOW}  Ejecuta: python3 scripts/validate_stack.py --fix  para reconectarlas automáticamente.{RESET}")

        return all_ok, stale_containers
    except Exception as e:
        print(f"  {RED}✘ Error consultando Docker:{RESET} {e}")
        return False, []

def check_vpn_and_port():
    print_header("2. VPN PROTONVPN Y SINCRONIZACIÓN DE PUERTO")
    try:
        cmd = ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "exec", "gluetun", "wget", "-qO-", "https://ipinfo.io/json"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode()
        ip_data = json.loads(out)
        print(f"  {GREEN}✔{RESET} IP Pública VPN    : {GREEN}{ip_data.get('ip')}{RESET} ({ip_data.get('city')}, {ip_data.get('country')}) - {ip_data.get('org')}")
    except Exception:
        print(f"  {YELLOW}⚠ No se pudo consultar la IP pública a través del contenedor gluetun.{RESET}")

    try:
        cmd_port = ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "exec", "gluetun", "cat", "/tmp/gluetun/forwarded_port"]
        fwd_port = subprocess.check_output(cmd_port, stderr=subprocess.DEVNULL, timeout=4).decode().strip()
        fwd_port = int(fwd_port) if fwd_port.isdigit() else None
    except Exception:
        fwd_port = None

    qbit_data, _ = api_get("http://localhost:8080/api/v2/app/preferences")
    qbit_port = qbit_data.get("listen_port") if isinstance(qbit_data, dict) else None

    if fwd_port:
        print(f"  {GREEN}✔{RESET} Puerto ProtonVPN  : {GREEN}{fwd_port}{RESET}")
    else:
        print(f"  {YELLOW}⚠ Puerto ProtonVPN  : No disponible aún{RESET}")

    if qbit_port:
        print(f"  {GREEN}✔{RESET} Puerto qBittorrent: {GREEN}{qbit_port}{RESET}")
    else:
        print(f"  {RED}✘ Puerto qBittorrent: Inaccesible{RESET}")

    if fwd_port and qbit_port:
        if fwd_port == qbit_port:
            print(f"  {GREEN}✔ Sincronización   : ÓPTIMA (qBittorrent escucha exactamente en el puerto forwarded){RESET}")
            return True
        else:
            print(f"  {RED}✘ Desincronización : qBittorrent ({qbit_port}) != ProtonVPN ({fwd_port}){RESET}")
            return False
    return False

def check_services_api():
    print_header("3. ESTADO DE SERVICIOS Y APIS WEB")
    radarr_key = get_api_key_from_xml(CONFIG_DIR / "radarr" / "config.xml")
    sonarr_key = get_api_key_from_xml(CONFIG_DIR / "sonarr" / "config.xml")
    prowlarr_key = get_api_key_from_xml(CONFIG_DIR / "prowlarr" / "config.xml")
    bazarr_key = get_bazarr_api_key()
    jellyfin_key = "4a6d8f1e2b3c4d5e6f7a8b9c0d1e2f3a"

    services = [
        ("Jellyfin",    "http://localhost:8096/System/Info", {"X-Emby-Token": jellyfin_key}),
        ("Jellyseerr",  "http://localhost:5055/api/v1/status", {}),
        ("Radarr",      "http://localhost:7878/api/v3/system/status", {"X-Api-Key": radarr_key}),
        ("Sonarr",      "http://localhost:8989/api/v3/system/status", {"X-Api-Key": sonarr_key}),
        ("Prowlarr",    "http://localhost:9696/api/v1/system/status", {"X-Api-Key": prowlarr_key}),
        ("Bazarr",      "http://localhost:6767/api/system/status", {"X-Api-Key": bazarr_key}),
        ("qBittorrent", "http://localhost:8080/api/v2/app/version", {}),
        ("Flaresolverr","http://localhost:8191/health", {})
    ]

    all_ok = True
    for name, url, headers in services:
        data, status = api_get(url, headers=headers)
        if status in (200, 204):
            print(f"  {GREEN}✔{RESET} {name:<14} : {GREEN}En línea (HTTP {status}){RESET}")
        else:
            all_ok = False
            code_str = f"HTTP {status}" if status else "Inaccesible"
            print(f"  {RED}✘{RESET} {name:<14} : {RED}{code_str}{RESET}")

    if bazarr_key:
        p_data, _ = api_get("http://localhost:6767/api/providers", headers={"X-Api-Key": bazarr_key})
        if isinstance(p_data, dict) and "data" in p_data:
            providers = [f"{p['name']} ({p['status']})" for p in p_data["data"]]
            print(f"  {CYAN}ℹ Proveedores Bazarr:{RESET} {', '.join(providers)}")

    return all_ok

def check_media_and_subtitles():
    print_header("4. BIBLIOTECA MULTIMEDIA, HARDLINKS Y SUBTÍTULOS")
    if not MEDIA_DIR.exists():
        print(f"  {RED}✘ Directorio de medios no encontrado en {MEDIA_DIR}{RESET}")
        return False

    jellyfin_key = "4a6d8f1e2b3c4d5e6f7a8b9c0d1e2f3a"
    jf_items_url = "http://localhost:8096/Items?recursive=true&includeItemTypes=Movie&fields=MediaStreams,Path"
    jf_data, _ = api_get(jf_items_url, headers={"X-Emby-Token": jellyfin_key})
    jf_items = jf_data.get("Items", []) if isinstance(jf_data, dict) else []
    
    # Mapear por nombre de carpeta física
    jf_by_folder = {}
    for item in jf_items:
        p = item.get("Path", "")
        for part in Path(p).parts:
            if "(" in part and ")" in part:
                jf_by_folder[part] = item
                break

    movie_folders = sorted([f for f in MEDIA_DIR.iterdir() if f.is_dir()])
    print(f"  Películas detectadas en disco: {BOLD}{len(movie_folders)}{RESET}\n")

    for folder in movie_folders:
        print(f"  {BOLD}📁 {folder.name}{RESET}")
        video_files = [f for f in folder.glob("*") if f.suffix.lower() in (".mkv", ".mp4", ".avi")]
        if not video_files:
            print(f"     {YELLOW}⚠ No se encontró archivo de video principal.{RESET}")
            continue

        video = video_files[0]
        stat = video.stat()
        nlink = stat.st_nlink
        size_gb = stat.st_size / (1024**3)

        if nlink >= 2:
            print(f"     {GREEN}✔ Hardlink APFS :{RESET} Compartido con torrents ({nlink} enlaces). {GREEN}0 bytes duplicados.{RESET} ({size_gb:.2f} GB)")
        else:
            print(f"     {YELLOW}⚠ Hardlink APFS :{RESET} Enlace simple ({nlink}). Podría estar duplicando espacio.")

        srts = [f.name for f in folder.glob("*.srt")]
        es_srts = [f for f in srts if any(x in f.lower() for x in (".es.", ".spa.", ".es-", ".latin."))]
        
        if es_srts:
            for s in es_srts:
                print(f"     {GREEN}✔ Subtítulo .srt:{RESET} {s}")
        elif srts:
            print(f"     {YELLOW}ℹ Subtítulos .srt (otros idiomas):{RESET} {', '.join(srts)}")
        else:
            print(f"     {CYAN}ℹ Sin archivos .srt externos (usa pistas incrustadas del contenedor){RESET}")

        jf_item = jf_by_folder.get(folder.name)
        if jf_item:
            streams = jf_item.get("MediaStreams", [])
            sub_streams = [s for s in streams if s.get("Type") == "Subtitle"]
            es_subs = [
                s.get("DisplayTitle") or s.get("Language") or "Español"
                for s in sub_streams
                if s.get("Language") in ("spa", "es", "spl")
            ]
            
            title_display = f"{jf_item.get('Name')}"
            if es_subs:
                print(f"     {GREEN}✔ Jellyfin [{title_display}]:{RESET} {len(es_subs)} pista(s) en español -> {', '.join(es_subs[:3])}{'...' if len(es_subs) > 3 else ''}")
            elif sub_streams:
                other_langs = list(set([s.get("Language", "?") for s in sub_streams]))
                print(f"     {YELLOW}⚠ Jellyfin [{title_display}]:{RESET} Subtítulos disponibles pero ninguno en español (Idiomas: {', '.join(other_langs)})")
            else:
                print(f"     {RED}✘ Jellyfin [{title_display}]:{RESET} 0 subtítulos disponibles.")
        else:
            print(f"     {YELLOW}⚠ Jellyfin       : No indexado aún en la biblioteca.{RESET}")
        print()

def main():
    parser = argparse.ArgumentParser(description="Media Stack System Validator")
    parser.add_argument("--subs", action="store_true", help="Auditar solo medios, hardlinks y subtítulos")
    parser.add_argument("--net", action="store_true", help="Auditar solo VPN y sincronización de puertos")
    parser.add_argument("--services", action="store_true", help="Auditar solo estado de Docker y APIs")
    parser.add_argument("--fix", action="store_true", help="Reiniciar automáticamente contenedores con monturas desconectadas")
    args = parser.parse_args()

    print(f"\n{BOLD}{GREEN}🔍 INICIANDO AUDITORÍA DEL MEDIA STACK{RESET}")

    stale_containers = []
    if args.subs:
        check_media_and_subtitles()
    elif args.net:
        check_vpn_and_port()
    elif args.services:
        _, stale_containers = check_docker_containers()
        check_services_api()
    else:
        _, stale_containers = check_docker_containers()
        check_vpn_and_port()
        check_services_api()
        check_media_and_subtitles()

    if args.fix and stale_containers:
        print(f"\n{BOLD}{CYAN}🔧 REPARANDO MONTURAS DESCONECTADAS...{RESET}")
        cmd = ["docker", "compose", "-f", str(PROJECT_DIR / "docker-compose.yml"), "restart"] + stale_containers
        subprocess.run(cmd, check=True)
        print(f"{GREEN}✔ Contenedores reiniciados y monturas reconectadas exitosamente.{RESET}\n")

    print(f"{BOLD}{GREEN}✨ Auditoría completada.{RESET}\n")

if __name__ == "__main__":
    main()
