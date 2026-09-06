# Guía de Inicio Rápido: Media Stack en Mac (OrbStack)

## 1. Configurar ProtonVPN en tu archivo `.env`

Para que qBittorrent descargue de forma anónima y con máxima velocidad (port forwarding):

1. Abre en tu navegador: **https://account.protonvpn.com/downloads**
2. Desplázate hacia abajo hasta la sección **"Configuración de WireGuard"**.
3. Configuración del formulario:
   - **Nombre:** `MacMedia` (o el que quieras).
   - **Plataforma:** `Router` o `GNU/Linux`.
   - **Activar Port Forwarding:** ✅ **Marca la casilla "NAT-PMP (Port Forwarding)"** *(imprescindible)*.
   - **Servidor:** Selecciona un país (ej. Argentina, Países Bajos, etc.).
4. Haz clic en **"Crear"** o **"Descargar"** para obtener el archivo `.conf`.
5. Abre el archivo descargado con *TextEdit* y copia dos líneas:
   - `PrivateKey = XXXXXXXX`  ➡️ Pégalo en `WIREGUARD_PRIVATE_KEY` en tu `.env`
   - `Address = 10.2.0.2/32`   ➡️ Pégalo en `WIREGUARD_ADDRESSES` en tu `.env`

Edita el `.env` ubicado en:
`/Users/gsoliz/.gemini/antigravity/scratch/media-stack/.env`

---

## 2. Iniciar el Stack

Abre tu terminal en la carpeta del proyecto y ejecuta:

```bash
cd /Users/gsoliz/.gemini/antigravity/scratch/media-stack
docker compose up -d
```

OrbStack descargará las imágenes e iniciará los 9 servicios.

---

## 3. Direcciones de Acceso

Una vez levantado, accede desde tu navegador:

| Servicio | URL Local | Función |
| :--- | :--- | :--- |
| **Jellyseerr** | `http://localhost:5055` | Tu "Netflix" privado (donde pides pelis y series) |
| **Jellyfin** | `http://localhost:8096` | El reproductor de streaming |
| **qBittorrent** | `http://localhost:8080` | Cliente de descargas (protegido por VPN) |
| **Prowlarr** | `http://localhost:9696` | Administrador de indexers/trackers |
| **Sonarr** | `http://localhost:8989` | Gestor de Series de TV |
| **Radarr** | `http://localhost:7878` | Gestor de Películas |
| **Bazarr** | `http://localhost:6767` | Subtítulos automáticos |

---

## 4. Conexión entre aplicaciones (Datos clave)

* **En Sonarr y Radarr:**
  - **Root Folder para Películas (Radarr):** `/data/media/movies`
  - **Root Folder para Series (Sonarr):** `/data/media/series`
  - **Agregar Download Client (qBittorrent):**
    - Host: `gluetun` *(¡Ojo! no localhost, ya que qBittorrent comparte la red con Gluetun)*
    - Port: `8080`
* **En Prowlarr:**
  - Settings ➡️ Apps ➡️ Agregas **Sonarr** (Host: `sonarr`, Port: `8989`) y **Radarr** (Host: `radarr`, Port: `7878`). ¡Prowlarr sincronizará todos los trackers automáticamente a ambos!
* **En Jellyfin:**
  - Agregar Biblioteca de Películas: `/data/media/movies`
  - Agregar Biblioteca de Series: `/data/media/series`
