from datetime import datetime

from media_stack.domain.repositories.vpn_gateway import IVpnGateway


class SyncVpnPortUseCase:
    """Application Use Case that synchronizes ProtonVPN NAT-PMP forwarded port with qBittorrent."""

    def __init__(self, vpn_gateway: IVpnGateway) -> None:
        self._vpn_gateway = vpn_gateway

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
            f"✅ Puerto verificado y sincronizado ({status.qbit_listen_port}). Todo óptimo."
        )
        return True
