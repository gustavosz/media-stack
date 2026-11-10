from __future__ import annotations

from datetime import datetime

from media_stack.domain.repositories.vpn_gateway import IVpnGateway
from media_stack.domain.value_objects.network import BitTorrentPerformanceProfile


class SyncVpnPortUseCase:
    """Application Use Case that synchronizes ProtonVPN NAT-PMP port and applies high-speed profile."""

    def __init__(
        self,
        vpn_gateway: IVpnGateway,
        profile: BitTorrentPerformanceProfile | None = None,
    ) -> None:
        self._vpn_gateway = vpn_gateway
        self._profile = profile or BitTorrentPerformanceProfile()

    @staticmethod
    def _log(msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}")

    def execute(self) -> bool:
        status = self._vpn_gateway.get_tunnel_status()
        if not status.forwarded_port:
            self._log(
                "Aviso: No se pudo obtener el puerto de ProtonVPN (Gluetun aún conectando o apagado)."
            )
            return False

        if not status.qbit_listen_port:
            self._log("Aviso: No se pudo conectar a la WebUI de qBittorrent.")
            return False

        self._vpn_gateway.apply_performance_profile(self._profile)

        if not status.is_port_synced:
            self._log(
                f"🔄 Desajuste detectado: qBittorrent escucha en {status.qbit_listen_port}, "
                f"pero ProtonVPN asignó {status.forwarded_port}."
            )
            if self._vpn_gateway.set_bittorrent_listen_port(status.forwarded_port):
                self._log(
                    f"✅ Puerto de qBittorrent actualizado exitosamente a: {status.forwarded_port}"
                )
                return True
            return False

        self._log(
            f"✅ Puerto ({status.qbit_listen_port}) y perfil de alto rendimiento verificados. Todo óptimo."
        )
        return True
