from __future__ import annotations

import json
import subprocess
from typing import Optional
import urllib.parse
import urllib.request

from media_stack.domain.entities.vpn_tunnel import VpnTunnelStatus
from media_stack.domain.repositories.vpn_gateway import IVpnGateway
from media_stack.domain.value_objects.network import IpAddress, PortNumber


class GluetunQbitVpnGateway(IVpnGateway):
    """Adapter for inspecting Gluetun VPN state and managing qBittorrent port forwarding."""

    def __init__(self, qbittorrent_url: str = "http://localhost:8080") -> None:
        self._qbittorrent_url = qbittorrent_url.rstrip("/")

    def get_tunnel_status(self) -> VpnTunnelStatus:
        ip_vo: Optional[IpAddress] = None
        country: Optional[str] = None
        city: Optional[str] = None
        org: Optional[str] = None

        ip_raw = self._docker_exec(
            ["docker", "exec", "gluetun", "wget", "-qO-", "https://ipinfo.io/json"]
        )
        if ip_raw:
            try:
                info = json.loads(ip_raw)
                raw_ip = info.get("ip")
                if raw_ip:
                    ip_vo = IpAddress(raw_ip)
                country = info.get("country")
                city = info.get("city")
                org = info.get("org")
            except Exception:
                pass

        fwd_port: Optional[PortNumber] = None
        port_raw = self._docker_exec(
            ["docker", "exec", "gluetun", "cat", "/tmp/gluetun/forwarded_port"]
        )
        if port_raw and port_raw.isdigit() and int(port_raw) > 0:
            fwd_port = PortNumber(int(port_raw))

        qbit_port = self._fetch_qbit_listen_port()

        return VpnTunnelStatus(
            public_ip=ip_vo,
            country=country,
            city=city,
            organization=org,
            forwarded_port=fwd_port,
            qbit_listen_port=qbit_port,
        )

    def set_bittorrent_listen_port(self, port: PortNumber) -> bool:
        try:
            payload = urllib.parse.urlencode(
                {"json": json.dumps({"listen_port": port.value})}
            ).encode()
            req = urllib.request.Request(
                f"{self._qbittorrent_url}/api/v2/app/setPreferences", data=payload
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def _fetch_qbit_listen_port(self) -> Optional[PortNumber]:
        try:
            req = urllib.request.Request(
                f"{self._qbittorrent_url}/api/v2/app/preferences"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_port = data.get("listen_port")
                if isinstance(raw_port, int) and 1 <= raw_port <= 65535:
                    return PortNumber(raw_port)
        except Exception:
            pass
        return None

    @staticmethod
    def _docker_exec(cmd: list[str], timeout: int = 8) -> Optional[str]:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None
