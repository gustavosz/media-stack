from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortNumber:
    """Immutable Value Object representing a valid TCP/UDP port (1-65535)."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or not (1 <= self.value <= 65535):
            raise ValueError(
                f"Invalid port number: {self.value}. Must be between 1 and 65535."
            )

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class IpAddress:
    """Immutable Value Object representing an IPv4/IPv6 address."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("IP address cannot be empty.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ServiceEndpointUrl:
    """Immutable Value Object representing an HTTP/HTTPS service endpoint URL."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid service URL '{self.value}': must start with http:// or https://"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BitTorrentPerformanceProfile:
    """
    Immutable Value Object encapsulating high-throughput libtorrent parameters
    optimized for WireGuard VPN tunnels and external APFS storage.
    """

    bittorrent_protocol: int = 1  # 1 = TCP only (avoids uTP latency throttling over VPN)
    upload_limit_bytes: int = 1_048_576  # 1 MB/s (prevents upload ACK starvation)
    max_active_downloads: int = 5
    max_active_torrents: int = 10
    max_connections: int = 800
    max_connections_per_torrent: int = 200
    async_io_threads: int = 16
    announce_to_all_trackers: bool = True
    announce_to_all_tiers: bool = True
    enable_coalesce_read_write: bool = True
    send_buffer_watermark_kb: int = 3072
    send_buffer_low_watermark_kb: int = 512
    socket_backlog_size: int = 100

    def __post_init__(self) -> None:
        if self.bittorrent_protocol not in (0, 1, 2):
            raise ValueError(
                "bittorrent_protocol must be 0 (both), 1 (TCP), or 2 (uTP)."
            )
        if self.upload_limit_bytes < 0:
            raise ValueError("upload_limit_bytes cannot be negative.")
        if self.max_active_downloads < 1 or self.max_connections < 10:
            raise ValueError(
                "Invalid concurrency limits in BitTorrentPerformanceProfile."
            )

    def to_qbit_preferences_dict(self) -> dict[str, object]:
        return {
            "bittorrent_protocol": self.bittorrent_protocol,
            "up_limit": self.upload_limit_bytes,
            "max_active_downloads": self.max_active_downloads,
            "max_active_torrents": self.max_active_torrents,
            "max_connec": self.max_connections,
            "max_connec_per_torrent": self.max_connections_per_torrent,
            "async_io_threads": self.async_io_threads,
            "announce_to_all_trackers": self.announce_to_all_trackers,
            "announce_to_all_tiers": self.announce_to_all_tiers,
            "enable_coalesce_read_write": self.enable_coalesce_read_write,
            "send_buffer_watermark": self.send_buffer_watermark_kb,
            "send_buffer_low_watermark": self.send_buffer_low_watermark_kb,
            "socket_backlog_size": self.socket_backlog_size,
            "upnp": False,
        }
