from __future__ import annotations

import datetime
from typing import Optional

from media_stack.application.audit_stack_use_case import AuditStackUseCase
from media_stack.application.bootstrap_stack_use_case import BootstrapStackUseCase
from media_stack.application.manage_daemon_use_case import ManageDaemonUseCase
from media_stack.application.monitor_disk_use_case import MonitorDiskRecoveryUseCase
from media_stack.application.sync_vpn_port_use_case import SyncVpnPortUseCase
from media_stack.infrastructure.apfs_media_library_repository import (
    ApfsMediaLibraryRepository,
)
from media_stack.infrastructure.credential_store import ConfigFileCredentialStore
from media_stack.infrastructure.docker_container_repository import (
    DockerComposeContainerRepository,
)
from media_stack.infrastructure.gluetun_qbit_vpn_gateway import GluetunQbitVpnGateway
from media_stack.infrastructure.http_service_health_gateway import (
    HttpServiceHealthGateway,
)
from media_stack.infrastructure.macos_disk_gateway import MacOSDiskUtilGateway
from media_stack.infrastructure.macos_system_services import (
    MacOSLaunchdDaemonManager,
    MacOSNotificationService,
)
from media_stack.infrastructure.settings import AppSettings
from media_stack.infrastructure.stack_provisioner_adapter import (
    HttpAndFilesystemStackProvisioner,
)


class DependencyContainer:
    """
    Composition Root / Dependency Injection Container.
    Wires concrete Infrastructure adapters into Application Use Cases.
    """

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings.from_environment()
        self.credential_store = ConfigFileCredentialStore(self.settings.config_dir)

        # Infrastructure Adapters
        self.container_repo = DockerComposeContainerRepository(
            self.settings.compose_file
        )
        self.disk_gateway = MacOSDiskUtilGateway()
        self.vpn_gateway = GluetunQbitVpnGateway(self.settings.qbittorrent_url)
        self.service_gateway = HttpServiceHealthGateway(
            credential_store=self.credential_store,
            jellyfin_url=self.settings.jellyfin_url,
        )
        self.media_repo = ApfsMediaLibraryRepository(
            movies_dir=self.settings.movies_dir,
            credential_store=self.credential_store,
            jellyfin_url=self.settings.jellyfin_url,
        )
        self.notifier = MacOSNotificationService()
        self.daemon_manager = MacOSLaunchdDaemonManager(
            project_dir=self.settings.project_dir,
            config_dir=self.settings.config_dir,
        )
        self.provisioner = HttpAndFilesystemStackProvisioner(
            data_dir=self.settings.data_dir,
            config_dir=self.settings.config_dir,
            credential_store=self.credential_store,
        )

    def build_bootstrap_use_case(self) -> BootstrapStackUseCase:
        return BootstrapStackUseCase(
            provisioner=self.provisioner,
            vpn_gateway=self.vpn_gateway,
        )

    def build_audit_use_case(self) -> AuditStackUseCase:
        return AuditStackUseCase(
            container_repo=self.container_repo,
            vpn_gateway=self.vpn_gateway,
            service_gateway=self.service_gateway,
            media_repo=self.media_repo,
            movies_dir_path=self.settings.movies_dir,
        )

    def build_monitor_disk_use_case(self) -> MonitorDiskRecoveryUseCase:
        log_file = self.settings.disk_watcher_log

        def file_and_stdout_logger(msg: str) -> None:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{now}] {msg}"
            print(line, flush=True)
            try:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

        return MonitorDiskRecoveryUseCase(
            mount_path=self.settings.external_disk_mount,
            project_dir=self.settings.project_dir,
            data_dir=self.settings.data_dir,
            disk_gateway=self.disk_gateway,
            container_repo=self.container_repo,
            service_gateway=self.service_gateway,
            notifier=self.notifier,
            logger=file_and_stdout_logger,
        )

    def build_sync_vpn_port_use_case(self) -> SyncVpnPortUseCase:
        return SyncVpnPortUseCase(vpn_gateway=self.vpn_gateway)

    def build_manage_daemon_use_case(self) -> ManageDaemonUseCase:
        return ManageDaemonUseCase(daemon_manager=self.daemon_manager)
