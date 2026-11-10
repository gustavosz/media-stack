from abc import ABC, abstractmethod

from media_stack.domain.value_objects.storage import VolumeMountPath


class IDiskGateway(ABC):
    """Port for checking physical volume mount status at the operating system level."""

    @abstractmethod
    def is_volume_mounted(self, mount_path: VolumeMountPath) -> bool:
        raise NotImplementedError
