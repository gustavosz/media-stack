import datetime
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from media_stack.domain.entities.external_disk import DiskConnectionState, ExternalDisk
from media_stack.domain.repositories.container_repository import IContainerRepository
from media_stack.domain.repositories.disk_gateway import IDiskGateway
from media_stack.domain.repositories.service_health_gateway import (
    IServiceHealthGateway,
)
from media_stack.domain.repositories.system_services import INotificationService
from media_stack.domain.value_objects.storage import VolumeMountPath


class MonitorDiskRecoveryUseCase:
    """
    Application Use Case managing the ExternalDisk state machine.
    Detects physical drive disconnections, reconnections, and stale Docker bind mounts,
    automatically recovering affected containers and triggering a Jellyfin scan.
    """

    AFFECTED_CONTAINERS: Sequence[str] = (
        "jellyfin",
        "radarr",
        "sonarr",
        "bazarr",
        "qbittorrent",
        "chaptarr",
        "calibre-web",
    )

    def __init__(
        self,
        mount_path: VolumeMountPath,
        project_dir: Path,
        data_dir: Path,
        disk_gateway: IDiskGateway,
        container_repo: IContainerRepository,
        service_gateway: IServiceHealthGateway,
        notifier: INotificationService,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._mount_path = mount_path
        self._project_dir = project_dir
        self._data_dir = data_dir
        self._disk_gateway = disk_gateway
        self._container_repo = container_repo
        self._service_gateway = service_gateway
        self._notifier = notifier
        self._log = logger or self._default_log

    @staticmethod
    def _default_log(msg: str) -> None:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] {msg}", flush=True)

    def recover_stack(self) -> None:
        self._log(
            f"Iniciando recuperación automática del stack para volumen {self._mount_path}..."
        )
        self._notifier.notify(
            "Media Stack",
            "Disco detectado. Reconectando servicios y restaurando reproducción...",
        )

        if self._container_repo.restart_containers(self.AFFECTED_CONTAINERS):
            self._log("Contenedores reiniciados exitosamente.")
        else:
            self._log("Advertencia al reiniciar uno o más contenedores.")

        time.sleep(3)
        if self._service_gateway.trigger_jellyfin_library_refresh():
            self._log("Escaneo de biblioteca Jellyfin solicitado.")
        else:
            self._log("No se pudo solicitar escaneo a Jellyfin.")

        self._log("Recuperación automática completada con éxito.")
        self._notifier.notify(
            "Media Stack", "Servicios restaurados y listos para reproducir en la TV."
        )

    def run_forever(self, poll_interval_sec: int = 5, stale_check_sec: int = 30) -> None:
        self._log("Iniciando daemon de monitoreo de disco y auto-recuperación...")
        self._log(f"Directorio de proyecto: {self._project_dir}")
        self._log(f"Volumen monitoreado: {self._mount_path} (DATA_DIR: {self._data_dir})")

        initial_mounted = self._disk_gateway.is_volume_mounted(self._mount_path)
        disk = ExternalDisk(
            mount_path=self._mount_path,
            state=(
                DiskConnectionState.CONNECTED
                if initial_mounted
                else DiskConnectionState.DISCONNECTED
            ),
        )
        self._log(f"Estado inicial del disco: {disk.state.value}")

        last_container_check = 0.0

        while True:
            try:
                currently_mounted = self._disk_gateway.is_volume_mounted(
                    self._mount_path
                )

                if not disk.is_connected and currently_mounted:
                    self._log(
                        f"¡Disco externo ({self._mount_path}) reconectado! "
                        "Esperando 4 segundos a que el SO estabilice el sistema de archivos..."
                    )
                    time.sleep(4)
                    if self._disk_gateway.is_volume_mounted(self._mount_path):
                        self.recover_stack()
                        disk.mark_connected()
                    else:
                        self._log(
                            "El disco volvió a desaparecer durante la estabilización."
                        )

                elif disk.is_connected and not currently_mounted:
                    self._log(
                        f"ATENCIÓN: El disco externo ({self._mount_path}) se ha desconectado."
                    )
                    self._notifier.notify(
                        "Media Stack",
                        f"El disco externo ({self._mount_path.name}) se ha desconectado.",
                    )
                    disk.mark_disconnected()

                elif currently_mounted:
                    now = time.time()
                    if now - last_container_check >= stale_check_sec:
                        last_container_check = now
                        if self._container_repo.is_primary_media_mount_stale():
                            self._log(
                                "ALERTA: Se detectó una montura caída (stale mount) dentro de los contenedores."
                            )
                            self.recover_stack()

                time.sleep(poll_interval_sec)
            except KeyboardInterrupt:
                self._log("Deteniendo disk_watcher por señal del usuario.")
                break
            except Exception as e:
                self._log(f"Error inesperado en loop de monitoreo: {e}")
                time.sleep(10)
