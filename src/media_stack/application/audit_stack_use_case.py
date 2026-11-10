from pathlib import Path
from typing import Mapping, Sequence

from media_stack.application.audit_report_dto import StackAuditReport
from media_stack.domain.repositories.container_repository import IContainerRepository
from media_stack.domain.repositories.media_library_repository import (
    IMediaLibraryRepository,
)
from media_stack.domain.repositories.service_health_gateway import (
    IServiceHealthGateway,
)
from media_stack.domain.repositories.vpn_gateway import IVpnGateway


class AuditStackUseCase:
    """Application Use Case that orchestrates the 4-stage Media Stack audit."""

    EXPECTED_CONTAINERS: Sequence[str] = (
        "gluetun",
        "qbittorrent",
        "gluetun-sync",
        "prowlarr",
        "flaresolverr",
        "radarr",
        "sonarr",
        "bazarr",
        "jellyfin",
        "jellyseerr",
        "chaptarr",
        "chaptarr-proxy",
        "calibre-web",
    )

    MOUNT_SPECS: Mapping[str, str] = {
        "jellyfin": "/data/media",
        "radarr": "/data",
        "sonarr": "/data",
        "chaptarr": "/data",
        "calibre-web": "/books",
        "bazarr": "/data/media",
        "qbittorrent": "/data/torrents",
    }

    def __init__(
        self,
        container_repo: IContainerRepository,
        vpn_gateway: IVpnGateway,
        service_gateway: IServiceHealthGateway,
        media_repo: IMediaLibraryRepository,
        movies_dir_path: Path,
    ) -> None:
        self._container_repo = container_repo
        self._vpn_gateway = vpn_gateway
        self._service_gateway = service_gateway
        self._media_repo = media_repo
        self._movies_dir_path = movies_dir_path

    def execute(self) -> StackAuditReport:
        containers = self._container_repo.get_containers_status(
            self.EXPECTED_CONTAINERS
        )
        mounts = self._container_repo.verify_container_mounts(self.MOUNT_SPECS)
        vpn_status = self._vpn_gateway.get_tunnel_status()
        services = self._service_gateway.check_all_services()
        bazarr_providers = self._service_gateway.get_bazarr_providers_summary()

        movies_exists = self._media_repo.is_movies_directory_present()
        movies = self._media_repo.scan_movies() if movies_exists else []

        return StackAuditReport(
            containers=tuple(containers),
            mount_checks=tuple(mounts),
            vpn_status=vpn_status,
            service_results=tuple(services),
            bazarr_providers=tuple(bazarr_providers),
            movies_dir_path=self._movies_dir_path,
            movies_dir_exists=movies_exists,
            movies=tuple(movies),
        )
