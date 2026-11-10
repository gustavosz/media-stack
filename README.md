# 🎬 Media Stack — Home Streaming, eBooks & Automation Platform

Plataforma multimedia completa, autohospedada y automatizada sobre **Docker Compose Modular**, diseñada bajo principios de **DDD (Domain-Driven Design)** y **Arquitectura Hexagonal** en Python.

Incluye protección de tráfico P2P con **ProtonVPN WireGuard + Killswitch**, sincronización automática de puertos **NAT-PMP**, **Hardlinks APFS** (cero duplicación de espacio en disco), pipeline de importación y envío automático de libros a **Amazon Kindle**, y un daemon de **auto-recuperación ante desconexiones de discos externos**.

---

## 🏗️ Arquitectura del Proyecto

El proyecto separa estrictamente la **definición de servicios en contenedores (`services/`)**, la **lógica de dominio y automatización del host (`src/media_stack/`)** y los **datos de estado en tiempo de ejecución (`config/`)**:

```text
media-stack/
├── .env.example                     # Plantilla de variables de entorno
├── docker-compose.yml               # Orquestador declarativo principal (usa `include`)
├── Makefile                         # Punto de entrada único para operar el stack
├── README.md                        # Documentación general
│
├── services/                        # 📦 DEFINICIÓN MODULAR DE SERVICIOS (Docker)
│   ├── gluetun/compose.yml          # Túnel VPN WireGuard + Killswitch
│   ├── qbittorrent/                 # Cliente BitTorrent + Sidecar NAT-PMP (sync_port.sh)
│   ├── prowlarr/compose.yml         # Gestor centralizado de indexers/trackers
│   ├── flaresolverr/compose.yml     # Resolución de retos Cloudflare
│   ├── radarr/compose.yml           # Automatización de películas
│   ├── sonarr/compose.yml           # Automatización de series de TV
│   ├── bazarr/compose.yml           # Automatización de subtítulos
│   ├── jellyfin/compose.yml         # Servidor de streaming multimedia
│   ├── jellyseerr/compose.yml       # Catálogo de solicitudes (estilo Netflix)
│   ├── chaptarr/                    # Gestión de libros + Microservicio Reverse Proxy Goodreads
│   └── calibre-web/                 # Biblioteca de eBooks + Pipeline de envío automático a Kindle
│
├── src/                             # 🧠 CORE DE ADMINISTRACIÓN Y MONITOREO (DDD + Hexagonal)
│   └── media_stack/
│       ├── domain/                  # Entidades, Value Objects e Interfaces (Ports)
│       │   ├── entities/            # ContainerNode, ExternalDisk, VpnTunnelStatus, MovieMediaAsset
│       │   ├── value_objects/       # PortNumber, IpAddress, VolumeMountPath, ApiKey, InodeLinkCount
│       │   └── repositories/        # IContainerRepository, IDiskGateway, IVpnGateway, etc.
│       ├── application/             # Casos de Uso desacoplados
│       │   ├── audit_stack_use_case.py
│       │   ├── monitor_disk_use_case.py
│       │   ├── sync_vpn_port_use_case.py
│       │   └── manage_daemon_use_case.py
│       ├── infrastructure/          # Adaptadores concretos (Docker CLI, DiskUtil, HTTP, Launchd)
│       └── interface/               # CLI unificada, Presenters ANSI y Contenedor de Inyección (DI)
│
└── config/                          # 🔒 ESTADO Y BASES DE DATOS LOCALES (Ignorado en Git)
```

---

## 🚀 Inicio Rápido

### 1. Clonar y configurar variables de entorno

```bash
git clone <url-del-repositorio> media-stack
cd media-stack
cp .env.example .env
```

Edita `.env` con tus rutas y credenciales de WireGuard (ProtonVPN):

```env
PUID=501
PGID=20
TZ=America/Argentina/Mendoza

CONFIG_DIR=./config
DATA_DIR=/Volumes/Media/data

VPN_SERVICE_PROVIDER=protonvpn
VPN_TYPE=wireguard
WIREGUARD_PRIVATE_KEY=tu_clave_privada_aqui
WIREGUARD_ADDRESSES=10.2.0.2/32
SERVER_COUNTRIES=Argentina
VPN_PORT_FORWARDING=on
VPN_PORT_FORWARDING_PROVIDER=protonvpn
```

> **¿Cómo obtener las claves de ProtonVPN?**
> 1. Entra a [account.protonvpn.com/downloads](https://account.protonvpn.com/downloads).
> 2. En **WireGuard Configuration**, elige plataforma **Router** o **GNU/Linux**.
> 3. Activa la casilla **"NAT-PMP (Port Forwarding)"**.
> 4. Descarga el archivo `.conf` y copia `PrivateKey` y `Address` a tu `.env`.

### 2. Preparar carpetas en el disco externo

```bash
mkdir -p /Volumes/Media/data/{torrents/{movies,series,books},media/{movies,series,books},import_books}
```

### 3. Levantar el Stack

```bash
make up
```

---

## 🛠️ Comandos de Operación (`Makefile`)

Ejecuta `make help` para ver todos los comandos disponibles:

| Comando | Descripción |
| :--- | :--- |
| `make up` | Levanta todos los servicios del Media Stack en segundo plano |
| `make down` | Detiene todos los contenedores del stack |
| `make restart` | Reinicia todos los contenedores |
| `make ps` | Muestra el estado actual de los contenedores |
| `make logs` | Muestra los logs en tiempo real de todos los servicios |
| `make audit` | Ejecuta la auditoría completa (Contenedores, VPN, APIs, Hardlinks APFS y Subtítulos) |
| `make sync-port` | Verifica y sincroniza manualmente el puerto NAT-PMP de ProtonVPN con qBittorrent |
| `make daemon-install` | Instala y activa el daemon de auto-recuperación de discos externos en macOS (`launchd`) |
| `make daemon-status` | Verifica el estado actual del daemon de monitoreo de discos |
| `make daemon-uninstall` | Detiene y elimina el daemon de auto-recuperación de discos en macOS |
| `make test` | Ejecuta la suite completa de tests unitarios (Dominio, Aplicación, Infraestructura y Servicios) |

---

## 🌐 Catálogo de Servicios y Puertos

| Servicio | URL Local | Descripción |
| :--- | :--- | :--- |
| **Jellyseerr** | `http://localhost:5055` | Portal de solicitudes de películas y series |
| **Jellyfin** | `http://localhost:8096` | Servidor de streaming y reproducción en TV/móviles |
| **qBittorrent** | `http://localhost:8080` | Cliente de descargas BitTorrent (100% enrutado por VPN) |
| **Prowlarr** | `http://localhost:9696` | Gestor centralizado de indexers y trackers |
| **Sonarr** | `http://localhost:8989` | Automatización y monitoreo de series de TV |
| **Radarr** | `http://localhost:7878` | Automatización y monitoreo de películas |
| **Bazarr** | `http://localhost:6767` | Descarga automática de subtítulos (`.srt`) |
| **Chaptarr (Proxy)** | `http://localhost:8787` | Automatización de libros enriquecida con metadatos Goodreads |
| **Calibre-Web** | `http://localhost:8083` | Biblioteca web de eBooks y envío directo a Kindle |

---

## 🛡️ Auto-Recuperación de Discos Externos (macOS)

Si utilizas un disco duro externo como almacenamiento (`DATA_DIR`), una desconexión accidental puede dejar a los contenedores de Docker con monturas huérfanas (*stale mounts*).

El caso de uso `MonitorDiskRecoveryUseCase` supervisa continuamente el volumen físico mediante `DiskArbitration` de macOS y verifica la salud de los puntos de montaje internos de los contenedores. Al reconectar el disco, reinicia automáticamente los contenedores afectados y solicita un refresco de biblioteca a Jellyfin.

Para dejarlo instalado de forma permanente al iniciar sesión en tu Mac:

```bash
make daemon-install
```

---

## 📄 Licencia

MIT License — Libre para uso personal y modificación.
