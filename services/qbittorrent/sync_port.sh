#!/bin/sh
# ==============================================================================
# Sincronizador Automático de Puerto: Gluetun (ProtonVPN NAT-PMP) -> qBittorrent
# Ejecutado dentro de Docker como servicio sidecar (curlimages/curl)
# ==============================================================================

PORT_FILE="/tmp/gluetun/forwarded_port"
QBIT_URL="http://127.0.0.1:8080"
LAST_SYNCED_PORT=""

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Sincronizador de puerto iniciado dentro de Docker."

while true; do
  if [ -f "$PORT_FILE" ]; then
    PORT=$(cat "$PORT_FILE" 2>/dev/null | tr -d '[:space:]')
    
    if [ -n "$PORT" ] && [ "$PORT" -gt 0 ] 2>/dev/null; then
      CURRENT_PORT=$(curl -s --max-time 5 "${QBIT_URL}/api/v2/app/preferences" 2>/dev/null | grep -o '"listen_port":[0-9]*' | cut -d':' -f2)
      
      if [ -n "$CURRENT_PORT" ]; then
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
      fi
    fi
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏳ Esperando a que Gluetun obtenga el puerto de ProtonVPN..."
  fi

  sleep 30
done
