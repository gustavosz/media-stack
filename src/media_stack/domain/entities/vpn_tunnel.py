from dataclasses import dataclass
from typing import Optional

from media_stack.domain.value_objects.network import IpAddress, PortNumber


@dataclass(frozen=True)
class VpnTunnelStatus:
    """Entity representing the Gluetun WireGuard VPN tunnel and NAT-PMP port state."""

    public_ip: Optional[IpAddress] = None
    country: Optional[str] = None
    city: Optional[str] = None
    organization: Optional[str] = None
    forwarded_port: Optional[PortNumber] = None
    qbit_listen_port: Optional[PortNumber] = None

    @property
    def has_public_ip(self) -> bool:
        return self.public_ip is not None

    @property
    def is_port_synced(self) -> bool:
        return (
            self.forwarded_port is not None
            and self.qbit_listen_port is not None
            and self.forwarded_port == self.qbit_listen_port
        )
