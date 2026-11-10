from dataclasses import dataclass
from enum import Enum

from media_stack.domain.value_objects.storage import VolumeMountPath


class DiskConnectionState(Enum):
    CONNECTED = "CONECTADO"
    DISCONNECTED = "DESCONECTADO"


@dataclass
class ExternalDisk:
    """Aggregate Root representing the physical external storage drive."""

    mount_path: VolumeMountPath
    state: DiskConnectionState

    @property
    def is_connected(self) -> bool:
        return self.state == DiskConnectionState.CONNECTED

    def mark_connected(self) -> None:
        self.state = DiskConnectionState.CONNECTED

    def mark_disconnected(self) -> None:
        self.state = DiskConnectionState.DISCONNECTED
