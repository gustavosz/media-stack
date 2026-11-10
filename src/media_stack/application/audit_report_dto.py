from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from media_stack.domain.entities.container import ContainerMountCheck, ContainerNode
from media_stack.domain.entities.media_item import MovieMediaAsset
from media_stack.domain.entities.service_health import ServiceHealthResult
from media_stack.domain.entities.vpn_tunnel import VpnTunnelStatus


@dataclass(frozen=True)
class StackAuditReport:
    """Immutable DTO containing the complete outcome of a Media Stack audit."""

    containers: Tuple[ContainerNode, ...]
    mount_checks: Tuple[ContainerMountCheck, ...]
    vpn_status: VpnTunnelStatus
    service_results: Tuple[ServiceHealthResult, ...]
    bazarr_providers: Tuple[str, ...]
    movies_dir_path: Path
    movies_dir_exists: bool
    movies: Tuple[MovieMediaAsset, ...]
