from __future__ import annotations

from typing import List, Tuple

from media_stack.domain.entities.bootstrap_step import BootstrapStepResult
from media_stack.domain.repositories.stack_provisioner import IStackProvisioner
from media_stack.domain.repositories.vpn_gateway import IVpnGateway
from media_stack.domain.value_objects.network import BitTorrentPerformanceProfile


class BootstrapStackUseCase:
    """
    Application Use Case that provisions directories, initial configurations,
    and API interconnections across all Media Stack services idempotently.
    """

    def __init__(
        self,
        provisioner: IStackProvisioner,
        vpn_gateway: IVpnGateway,
        profile: BitTorrentPerformanceProfile | None = None,
    ) -> None:
        self._provisioner = provisioner
        self._vpn_gateway = vpn_gateway
        self._profile = profile or BitTorrentPerformanceProfile()

    def execute(self) -> Tuple[BootstrapStepResult, ...]:
        results: List[BootstrapStepResult] = []

        results.append(self._provisioner.ensure_storage_directories())
        results.append(self._provisioner.ensure_qbittorrent_config())

        # Apply high-speed profile & sync NAT-PMP port if qBittorrent is reachable
        perf_ok = self._vpn_gateway.apply_performance_profile(self._profile)
        tunnel = self._vpn_gateway.get_tunnel_status()
        if tunnel.forwarded_port and not tunnel.is_port_synced:
            self._vpn_gateway.set_bittorrent_listen_port(tunnel.forwarded_port)

        results.append(
            BootstrapStepResult(
                step_name="qBittorrent Performance & VPN Port",
                succeeded=perf_ok,
                details=(
                    f"Perfil TCP/1MBs aplicado (Puerto VPN: {tunnel.forwarded_port or 'pendiente'})"
                    if perf_ok
                    else "qBittorrent aún iniciando (el sidecar gluetun-sync lo aplicará automáticamente)"
                ),
            )
        )

        results.extend(self._provisioner.ensure_arr_root_folders())
        results.extend(self._provisioner.ensure_arr_download_clients())
        results.extend(self._provisioner.ensure_prowlarr_integrations())
        results.append(self._provisioner.ensure_bazarr_integrations())
        results.append(self._provisioner.ensure_calibre_library_initialized())

        return tuple(results)
