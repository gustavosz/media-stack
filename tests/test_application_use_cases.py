from pathlib import Path
from typing import List, Mapping, Optional, Sequence
import unittest
from unittest.mock import patch

from media_stack.application.audit_stack_use_case import AuditStackUseCase
from media_stack.application.bootstrap_stack_use_case import BootstrapStackUseCase
from media_stack.application.manage_daemon_use_case import ManageDaemonUseCase
from media_stack.application.monitor_disk_use_case import MonitorDiskRecoveryUseCase
from media_stack.application.sync_vpn_port_use_case import SyncVpnPortUseCase
from media_stack.domain.entities.bootstrap_step import BootstrapStepResult
from media_stack.domain.entities.container import ContainerMountCheck, ContainerNode
from media_stack.domain.entities.media_item import MovieMediaAsset
from media_stack.domain.entities.service_health import ServiceHealthResult
from media_stack.domain.entities.vpn_tunnel import VpnTunnelStatus
from media_stack.domain.repositories.container_repository import IContainerRepository
from media_stack.domain.repositories.disk_gateway import IDiskGateway
from media_stack.domain.repositories.media_library_repository import (
    IMediaLibraryRepository,
)
from media_stack.domain.repositories.service_health_gateway import (
    IServiceHealthGateway,
)
from media_stack.domain.repositories.stack_provisioner import IStackProvisioner
from media_stack.domain.repositories.system_services import (
    IDaemonManager,
    INotificationService,
)
from media_stack.domain.repositories.vpn_gateway import IVpnGateway
from media_stack.domain.value_objects.network import (
    BitTorrentPerformanceProfile,
    IpAddress,
    PortNumber,
    ServiceEndpointUrl,
)
from media_stack.domain.value_objects.storage import (
    FileSizeBytes,
    InodeLinkCount,
    VolumeMountPath,
)


# ------------------------------------------------------------------------------
# In-Memory Fakes Implementing Domain Repository Ports
# ------------------------------------------------------------------------------
class FakeContainerRepository(IContainerRepository):
    def __init__(self, stale: bool = False) -> None:
        self.stale = stale
        self.restarted_batches: List[List[str]] = []

    def get_containers_status(
        self, expected_names: Sequence[str]
    ) -> List[ContainerNode]:
        return [ContainerNode(name=n, state="running") for n in expected_names]

    def verify_container_mounts(
        self, mount_specs: Mapping[str, str]
    ) -> List[ContainerMountCheck]:
        return [
            ContainerMountCheck(
                container_name=k, mount_point=v, is_accessible=not self.stale
            )
            for k, v in mount_specs.items()
        ]

    def is_primary_media_mount_stale(self) -> bool:
        return self.stale

    def restart_containers(self, container_names: Sequence[str]) -> bool:
        self.restarted_batches.append(list(container_names))
        self.stale = False
        return True


class FakeDiskGateway(IDiskGateway):
    def __init__(self, mounted_sequence: List[bool]) -> None:
        self._sequence = list(mounted_sequence)
        self._index = 0

    def is_volume_mounted(self, mount_path: VolumeMountPath) -> bool:
        if not self._sequence:
            return True
        val = self._sequence[min(self._index, len(self._sequence) - 1)]
        self._index += 1
        return val


class FakeVpnGateway(IVpnGateway):
    def __init__(self, status: VpnTunnelStatus, update_succeeds: bool = True) -> None:
        self._status = status
        self._update_succeeds = update_succeeds
        self.updated_ports: List[PortNumber] = []
        self.applied_profiles: List[BitTorrentPerformanceProfile] = []

    def get_tunnel_status(self) -> VpnTunnelStatus:
        return self._status

    def set_bittorrent_listen_port(self, port: PortNumber) -> bool:
        if self._update_succeeds:
            self.updated_ports.append(port)
            return True
        return False

    def apply_performance_profile(self, profile: BitTorrentPerformanceProfile) -> bool:
        self.applied_profiles.append(profile)
        return True


class FakeServiceHealthGateway(IServiceHealthGateway):
    def __init__(self) -> None:
        self.refresh_calls = 0

    def check_all_services(self) -> List[ServiceHealthResult]:
        return [
            ServiceHealthResult(
                service_name="Jellyfin",
                url=ServiceEndpointUrl("http://localhost:8096/System/Info"),
                http_status=200,
                is_online=True,
            )
        ]

    def get_bazarr_providers_summary(self) -> List[str]:
        return ["opensubtitlescom (Good)"]

    def trigger_jellyfin_library_refresh(self) -> bool:
        self.refresh_calls += 1
        return True


class FakeMediaLibraryRepository(IMediaLibraryRepository):
    def __init__(self, present: bool = True) -> None:
        self._present = present

    def is_movies_directory_present(self) -> bool:
        return self._present

    def scan_movies(self) -> List[MovieMediaAsset]:
        return [
            MovieMediaAsset(
                folder_name="8 Mile (2002)",
                video_filename="8.Mile.2002.mp4",
                size=FileSizeBytes(2 * 1024**3),
                link_count=InodeLinkCount(2),
                external_srt_files=("8.Mile.2002.es.srt",),
                jellyfin_title="8 millas",
            )
        ]


class FakeNotificationService(INotificationService):
    def __init__(self) -> None:
        self.messages: List[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.messages.append((title, message))


class FakeDaemonManager(IDaemonManager):
    def __init__(self) -> None:
        self.installed = False

    def install(self) -> Path:
        self.installed = True
        return Path("/tmp/com.media-stack.disk-watcher.plist")

    def uninstall(self) -> List[Path]:
        if self.installed:
            self.installed = False
            return [Path("/tmp/com.media-stack.disk-watcher.plist")]
        return []

    def get_status(self) -> Optional[str]:
        return "1234 0 com.media-stack.disk-watcher" if self.installed else None


class FakeStackProvisioner(IStackProvisioner):
    def ensure_storage_directories(self) -> BootstrapStepResult:
        return BootstrapStepResult("Dirs", True, "OK")

    def ensure_qbittorrent_config(self) -> BootstrapStepResult:
        return BootstrapStepResult("qBit Conf", True, "OK")

    def ensure_arr_root_folders(self) -> List[BootstrapStepResult]:
        return [BootstrapStepResult("Root Folders", True, "OK")]

    def ensure_arr_download_clients(self) -> List[BootstrapStepResult]:
        return [BootstrapStepResult("Download Clients", True, "OK")]

    def ensure_prowlarr_integrations(self) -> List[BootstrapStepResult]:
        return [BootstrapStepResult("Prowlarr", True, "OK")]

    def ensure_bazarr_integrations(self) -> BootstrapStepResult:
        return BootstrapStepResult("Bazarr", True, "OK")

    def ensure_calibre_library_initialized(self) -> BootstrapStepResult:
        return BootstrapStepResult("Calibre", True, "OK")


# ------------------------------------------------------------------------------
# Use Case Tests
# ------------------------------------------------------------------------------
class TestApplicationUseCases(unittest.TestCase):
    def test_audit_stack_use_case_produces_complete_report(self) -> None:
        container_repo = FakeContainerRepository()
        vpn_gateway = FakeVpnGateway(
            VpnTunnelStatus(
                public_ip=IpAddress("84.233.234.202"),
                country="AR",
                city="Buenos Aires",
                forwarded_port=PortNumber(63398),
                qbit_listen_port=PortNumber(63398),
            )
        )
        service_gateway = FakeServiceHealthGateway()
        media_repo = FakeMediaLibraryRepository(present=True)

        use_case = AuditStackUseCase(
            container_repo=container_repo,
            vpn_gateway=vpn_gateway,
            service_gateway=service_gateway,
            media_repo=media_repo,
            movies_dir_path=Path("/Volumes/Media/data/media/movies"),
        )
        report = use_case.execute()

        self.assertEqual(len(report.containers), 13)
        self.assertTrue(all(c.is_running for c in report.containers))
        self.assertEqual(len(report.mount_checks), 7)
        self.assertTrue(report.vpn_status.is_port_synced)
        self.assertEqual(len(report.service_results), 1)
        self.assertEqual(report.bazarr_providers, ("opensubtitlescom (Good)",))
        self.assertTrue(report.movies_dir_exists)
        self.assertEqual(len(report.movies), 1)
        self.assertEqual(report.movies[0].folder_name, "8 Mile (2002)")

    def test_sync_vpn_port_use_case_when_already_synced(self) -> None:
        vpn = FakeVpnGateway(
            VpnTunnelStatus(
                forwarded_port=PortNumber(63398),
                qbit_listen_port=PortNumber(63398),
            )
        )
        use_case = SyncVpnPortUseCase(vpn)
        self.assertTrue(use_case.execute())
        self.assertEqual(len(vpn.updated_ports), 0)

    def test_sync_vpn_port_use_case_updates_qbit_on_mismatch(self) -> None:
        vpn = FakeVpnGateway(
            VpnTunnelStatus(
                forwarded_port=PortNumber(63398),
                qbit_listen_port=PortNumber(50000),
            )
        )
        use_case = SyncVpnPortUseCase(vpn)
        self.assertTrue(use_case.execute())
        self.assertEqual(vpn.updated_ports, [PortNumber(63398)])

    def test_sync_vpn_port_use_case_returns_false_when_gluetun_port_missing(
        self,
    ) -> None:
        vpn = FakeVpnGateway(VpnTunnelStatus(forwarded_port=None))
        use_case = SyncVpnPortUseCase(vpn)
        self.assertFalse(use_case.execute())

    @patch("media_stack.application.monitor_disk_use_case.time.sleep")
    def test_monitor_disk_recover_stack_restarts_containers_and_refreshes_jellyfin(
        self, _mock_sleep: object
    ) -> None:
        container_repo = FakeContainerRepository(stale=True)
        disk_gateway = FakeDiskGateway([True])
        service_gateway = FakeServiceHealthGateway()
        notifier = FakeNotificationService()
        logs: List[str] = []

        use_case = MonitorDiskRecoveryUseCase(
            mount_path=VolumeMountPath(Path("/Volumes/Media")),
            project_dir=Path("/tmp/media-stack"),
            data_dir=Path("/Volumes/Media/data"),
            disk_gateway=disk_gateway,
            container_repo=container_repo,
            service_gateway=service_gateway,
            notifier=notifier,
            logger=logs.append,
        )

        use_case.recover_stack()

        self.assertEqual(len(container_repo.restarted_batches), 1)
        self.assertIn("jellyfin", container_repo.restarted_batches[0])
        self.assertIn("qbittorrent", container_repo.restarted_batches[0])
        self.assertEqual(service_gateway.refresh_calls, 1)
        self.assertEqual(len(notifier.messages), 2)

    def test_manage_daemon_use_case_lifecycle(self) -> None:
        manager = FakeDaemonManager()
        use_case = ManageDaemonUseCase(manager)

        self.assertIsNone(use_case.status())
        plist = use_case.install()
        self.assertEqual(plist, Path("/tmp/com.media-stack.disk-watcher.plist"))
        self.assertIsNotNone(use_case.status())

        removed = use_case.uninstall()
        self.assertEqual(len(removed), 1)
        self.assertIsNone(use_case.status())

    def test_bootstrap_stack_use_case_executes_all_provisioning_steps(self) -> None:
        provisioner = FakeStackProvisioner()
        vpn = FakeVpnGateway(
            VpnTunnelStatus(
                forwarded_port=PortNumber(63398),
                qbit_listen_port=PortNumber(50000),
            )
        )
        use_case = BootstrapStackUseCase(provisioner=provisioner, vpn_gateway=vpn)
        steps = use_case.execute()

        self.assertEqual(len(steps), 8)
        self.assertTrue(all(s.succeeded for s in steps))
        self.assertEqual(len(vpn.applied_profiles), 1)
        self.assertEqual(vpn.updated_ports, [PortNumber(63398)])


if __name__ == "__main__":
    unittest.main()
