# Walkthrough: Media Stack 100% Configurado, Migrado a Docker y Verificado

Se completó exitosamente la verificación de la descarga de prueba, la indexación en Jellyfin/Bazarr y la migración definitiva del sincronizador de puerto ProtonVPN para que viva **100% dentro de Docker**.

---

## 1. Descarga y Almacenamiento Verificados

* **Película de prueba:** `Backrooms (2026)` (28.63 GB BluRay REMUX 1080p).
* **Descarga qBittorrent:** Completada al **100.0%**.
* **Hardlink Atómico en APFS:** Verificado en `/Volumes/Media/data/media/movies/Backrooms (2026)/...`.
  * Inode: `211` compartido entre carpeta de torrents y biblioteca multimedia.
  * Espacio duplicado en disco: **0 Bytes**.
* **Jellyfin:** Biblioteca actualizada, metadatos e imagen cargados.
* **Bazarr:** Película sincronizada en el catálogo y pistas de subtítulos en español (`BTM ES`) indexadas.

---

## 2. Sincronizador de Puerto Migrado 100% a Docker

1. **Servicio `gluetun-sync` en Docker Compose:**
   * Contenedor liviano oficial: `curlimages/curl:latest` (10 MB, sin dependencias del Mac).
   * Volumen compartido de solo lectura: `gluetun-data:/tmp/gluetun:ro`.
   * Enrutamiento de red: `network_mode: "service:gluetun"` (accede a qBittorrent de forma ultra-rápida y segura en `127.0.0.1:8080`).
   * Script ejecutado: [`scripts/docker_sync_port.sh`](file:///Users/gsoliz/Code/media-stack/scripts/docker_sync_port.sh).
2. **Prueba Real en Caliente:**
   * Al recrearse Gluetun con el volumen, ProtonVPN asignó un nuevo puerto aleatorio: **`50590`**.
   * `gluetun-sync` detectó el cambio en su primer ciclo de 30 segundos y actualizó qBittorrent de inmediato:
     ```text
     [2026-09-06 20:59:49] 🚀 Sincronizador de puerto iniciado dentro de Docker.
     [2026-09-06 21:00:19] 🔄 Desajuste detectado: qBittorrent escucha en 51663, pero ProtonVPN asignó 50590.
     [2026-09-06 21:00:19] ✅ Puerto de qBittorrent actualizado exitosamente a: 50590
     ```
3. **Limpieza del Mac Host:**
   * Se descargó y eliminó completamente el agente temporal de macOS: `~/Library/LaunchAgents/com.mediastack.portsync.plist`.
   * Tu Mac quedó completamente libre de scripts o procesos en segundo plano. El stack es 100% autocontenido y portable.

---

## 3. Credenciales Unificadas del Stack

| Servicio | URL Local | Usuario | Contraseña | Estado |
| :--- | :--- | :---: | :---: | :---: |
| **Jellyseerr** | [http://localhost:5055](http://localhost:5055) | `gus` | `radmika` | ✅ Verificado |
| **Jellyfin** | [http://localhost:8096](http://localhost:8096) | `gus` | `radmika` | ✅ Verificado |
| **Radarr** | [http://localhost:7878](http://localhost:7878) | `gus` | `radmika` | ✅ Verificado |
| **Sonarr** | [http://localhost:8989](http://localhost:8989) | `gus` | `radmika` | ✅ Verificado |
| **Prowlarr** | [http://localhost:9696](http://localhost:9696) | `gus` | `radmika` | ✅ Verificado |
| **qBittorrent** | [http://localhost:8080](http://localhost:8080) | `admin` | `radmika` | ✅ Verificado |
| **Bazarr** | [http://localhost:6767](http://localhost:6767) | *Sin login* | *Sin login* | ✅ Verificado |

---

## 4. Estado de los 10 Contenedores del Stack

```bash
docker compose ps
```
* `gluetun`: Healthy (VPN WireGuard activa + Killswitch + Port Forwarding).
* `qbittorrent`: Up (Enrutado por Gluetun con puerto sincronizado).
* `gluetun-sync`: Up (Sidecar de sincronización automática de puerto).
* `prowlarr`: Up (Trackers indexados y sincronizados).
* `flaresolverr`: Up (Bypass de Cloudflare para trackers).
* `radarr`: Up (Gestión de películas + Hardlinks APFS).
* `sonarr`: Up (Gestión de series).
* `bazarr`: Up (Gestión de subtítulos).
* `jellyfin`: Up (Servidor multimedia y streaming).
* `jellyseerr`: Up (Interfaz de peticiones y catálogo).
