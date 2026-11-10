#!/bin/sh
# ==============================================================================
# Sincronizador Automático de Puerto y Perfil de Alto Rendimiento:
# Gluetun (ProtonVPN NAT-PMP) -> qBittorrent
# Ejecutado dentro de Docker como servicio sidecar (curlimages/curl)
# ==============================================================================

PORT_FILE="/tmp/gluetun/forwarded_port"
QBIT_URL="http://127.0.0.1:8080"
LAST_SYNCED_PORT=""
PROFILE_APPLIED="false"

# Parámetros de optimización configurables por variables de entorno (.env)
UP_LIMIT_BYTES="${QBIT_UP_LIMIT_BYTES:-1048576}"        # 1 MB/s por defecto (evita upload choking)
MAX_ACTIVE_DL="${QBIT_MAX_ACTIVE_DOWNLOADS:-5}"
MAX_ACTIVE_TORRENTS="${QBIT_MAX_ACTIVE_TORRENTS:-10}"
MAX_CONNEC="${QBIT_MAX_CONNEC:-800}"
MAX_CONNEC_PER_TORRENT="${QBIT_MAX_CONNEC_PER_TORRENT:-200}"
ASYNC_IO_THREADS="${QBIT_ASYNC_IO_THREADS:-16}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Sincronizador de puerto y optimizador qBittorrent iniciado."

apply_performance_profile() {
  PERF_JSON=$(cat <<EOF
{
  "bittorrent_protocol": 1,
  "up_limit": ${UP_LIMIT_BYTES},
  "max_active_downloads": ${MAX_ACTIVE_DL},
  "max_active_torrents": ${MAX_ACTIVE_TORRENTS},
  "max_connec": ${MAX_CONNEC},
  "max_connec_per_torrent": ${MAX_CONNEC_PER_TORRENT},
  "async_io_threads": ${ASYNC_IO_THREADS},
  "announce_to_all_trackers": true,
  "announce_to_all_tiers": true,
  "enable_coalesce_read_write": true,
  "send_buffer_watermark": 3072,
  "send_buffer_low_watermark": 512,
  "socket_backlog_size": 100,
  "upnp": false
}
EOF
)
  curl -s --max-time 5 -X POST "${QBIT_URL}/api/v2/app/setPreferences" --data-urlencode "json=${PERF_JSON}" > /dev/null 2>&1
  curl -s --max-time 5 -X POST "${QBIT_URL}/api/v2/transfer/setUploadLimit" -d "limit=${UP_LIMIT_BYTES}" > /dev/null 2>&1
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚡ Perfil de alto rendimiento WireGuard/libtorrent aplicado en qBittorrent."
}

while true; do
  if [ -f "$PORT_FILE" ]; then
    PORT=$(cat "$PORT_FILE" 2>/dev/null | tr -d '[:space:]')
    
    if [ -n "$PORT" ] && [ "$PORT" -gt 0 ] 2>/dev/null; then
      CURRENT_PORT=$(curl -s --max-time 5 "${QBIT_URL}/api/v2/app/preferences" 2>/dev/null | grep -o '"listen_port":[0-9]*' | cut -d':' -f2)
      
      if [ -n "$CURRENT_PORT" ]; then
        if [ "$PROFILE_APPLIED" = "false" ]; then
          apply_performance_profile
          PROFILE_APPLIED="true"
        fi

        if [ "$CURRENT_PORT" != "$PORT" ]; then
          echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 Desajuste detectado: qBittorrent escucha en ${CURRENT_PORT}, pero ProtonVPN asignó ${PORT}."
          curl -s --max-time 5 -X POST "${QBIT_URL}/api/v2/app/setPreferences" --data-urlencode "json={\"listen_port\": ${PORT}}" > /dev/null 2>&1
          echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Puerto de qBittorrent actualizado exitosamente a: ${PORT}"
          LAST_SYNCED_PORT="$PORT"
        elif [ "$LAST_SYNCED_PORT" != "$PORT" ]; then
          echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Puerto verificado y sincronizado (${PORT}). Todo óptimo."
          LAST_SYNCED_PORT="$PORT"
        fi
      else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏳ Esperando a que qBittorrent WebUI esté disponible..."
        PROFILE_APPLIED="false"
      fi
    fi
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏳ Esperando a que Gluetun obtenga el puerto de ProtonVPN..."
  fi

  sleep 30
done
