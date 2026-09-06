# 🎬 Media Stack — Servidor Multimedia Automatizado con Docker y VPN

Stack completo y automatizado para correr tu propio servidor de películas y series en casa con **Docker** (optimizado para **macOS / OrbStack** y **Linux**), integrando la arquitectura de **YAMS** y las mejores prácticas de **TRaSH Guides**.

---

## 🌟 Características Principales

- 🛡️ **Privacidad Total con VPN y Killswitch**: qBittorrent descarga encapsulado dentro de un túnel WireGuard (**Gluetun**) con soporte de reenvío de puertos (Port Forwarding) para **ProtonVPN**. Si la VPN se desconecta, el tráfico se corta inmediatamente.
- ⚡ **Hardlinks Atómicos (TRaSH Guides)**: Las descargas terminadas se enlazan físicamente a tu biblioteca final sin duplicar espacio en disco ni gastar I/O.
- 🔍 **Prowlarr Integrado**: Indexador moderno que sincroniza automáticamente trackers y sitios de torrents con Sonarr y Radarr.
- 🛡️ **FlareSolverr**: Supera retos anti-bot de Cloudflare en trackers públicos.
- 📺 **Jellyfin**: Servidor de streaming 100% de código abierto (sin costos ni paywalls).
- 🍿 **Jellyseerr**: Interfaz visual estilo Netflix para que tú y tu familia busquen y soliciten contenido en un clic.
- 💬 **Bazarr**: Descarga automática de subtítulos para cada versión específica de video.

---

## 📐 Arquitectura

```mermaid
graph TD
    User([Usuario / Smart TV]) -->|Navega / Pide contenido| JS[Jellyseerr :5055]
    User -->|Streaming de video| JF[Jellyfin :8096]
    
    JS -->|Solicita serie| Sonarr[Sonarr :8989]
    JS -->|Solicita película| Radarr[Radarr :7878]
    
    subgraph Indexers
        Prowlarr[Prowlarr :9696] -->|Sincroniza trackers| Sonarr & Radarr
        Prowlarr -->|Bypass Cloudflare| FS[FlareSolverr :8191]
    end
    
    subgraph Red Protegida VPN (Gluetun)
        VPN[Túnel ProtonVPN WireGuard]
        QB[qBittorrent WebUI :8080]
    end
    
    Sonarr & Radarr -->|Envía Torrents a través de VPN| QB
    
    subgraph Almacenamiento (TRaSH Guides)
        QB -->|Escribe descargas| TOR["/data/torrents/"]
        Sonarr & Radarr -.->|Hardlinks atómicos| MED["/data/media/"]
        Bazarr[Bazarr :6767] -->|Descarga .srt| MED
        JF -->|Lee biblioteca final| MED
    end
```

---

## 🚀 Inicio Rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU-USUARIO/media-stack.git
cd media-stack
```

### 2. Configurar variables de entorno

Copia la plantilla `.env.example`:

```bash
cp .env.example .env
```

Edita `.env` con tus rutas y credenciales de ProtonVPN:

```env
PUID=501
PGID=20
TZ=America/Argentina/Mendoza

CONFIG_DIR=/Users/gsoliz/Code/media-stack/config
DATA_DIR=/Volumes/Media/data

# Configuración ProtonVPN (WireGuard)
VPN_SERVICE_PROVIDER=protonvpn
VPN_TYPE=wireguard
WIREGUARD_PRIVATE_KEY=tu_clave_privada_aqui
WIREGUARD_ADDRESSES=10.2.0.2/32
SERVER_COUNTRIES=Argentina
VPN_PORT_FORWARDING=on
VPN_PORT_FORWARDING_PROVIDER=protonvpn
```

> **¿Cómo obtener las claves de ProtonVPN?**
> 1. Entra a [account.protonvpn.com/downloads](https://account.protonvpn.com/downloads)
> 2. En **WireGuard Configuration**, elige plataforma **Router** o **GNU/Linux**.
> 3. Marca la casilla **"NAT-PMP (Port Forwarding)"**.
> 4. Descarga el archivo `.conf` y copia el `PrivateKey` y `Address` a tu `.env`.

### 3. Iniciar el stack

```bash
docker compose up -d
```

---

## 🌐 Servicios y Puertos

| Servicio | URL Local | Descripción |
| :--- | :--- | :--- |
| **Jellyseerr** | `http://localhost:5055` | Portal de solicitudes y descubrimiento |
| **Jellyfin** | `http://localhost:8096` | Servidor de streaming y reproducción |
| **qBittorrent** | `http://localhost:8080` | Gestor de descargas (vía VPN Gluetun) |
| **Prowlarr** | `http://localhost:9696` | Administrador de indexers/trackers |
| **Sonarr** | `http://localhost:8989` | Gestión automatizada de series |
| **Radarr** | `http://localhost:7878` | Gestión automatizada de películas |
| **Bazarr** | `http://localhost:6767` | Descarga de subtítulos |

---

## 🔗 Configuración de Conexiones Internas

Dentro de la red de Docker (`media-net`), los contenedores se comunican por nombre:

- **Download Client en Sonarr y Radarr:**
  - Tipo: **qBittorrent**
  - Host: `gluetun` *(al compartir network_mode con Gluetun, ese es su host de red)*
  - Port: `8080`
- **Root Folders en Sonarr/Radarr:**
  - Radarr: `/data/media/movies`
  - Sonarr: `/data/media/series`
- **Prowlarr ➡️ Sonarr & Radarr:**
  - Sonarr: `http://sonarr:8989`
  - Radarr: `http://radarr:7878`
  *(Prowlarr sincronizará todos tus trackers a ambos automáticamente).*

---

## 📄 Licencia

MIT License — Libre para uso personal y modificación.
