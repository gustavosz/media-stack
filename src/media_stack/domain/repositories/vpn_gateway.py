from abc import ABC, abstractmethod

from media_stack.domain.entities.vpn_tunnel import VpnTunnelStatus
from media_stack.domain.value_objects.network import (
    BitTorrentPerformanceProfile,
    PortNumber,
)


class IVpnGateway(ABC):
    """Port for inspecting the VPN tunnel and synchronizing NAT-PMP ports and tuning."""

    @abstractmethod
    def get_tunnel_status(self) -> VpnTunnelStatus:
        raise NotImplementedError

    @abstractmethod
    def set_bittorrent_listen_port(self, port: PortNumber) -> bool:
        raise NotImplementedError

    @abstractmethod
    def apply_performance_profile(self, profile: BitTorrentPerformanceProfile) -> bool:
        raise NotImplementedError
