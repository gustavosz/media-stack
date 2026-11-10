from abc import ABC, abstractmethod
from typing import List, Mapping, Sequence

from media_stack.domain.entities.container import ContainerMountCheck, ContainerNode


class IContainerRepository(ABC):
    """Port for querying and managing Docker containers and their storage mounts."""

    @abstractmethod
    def get_containers_status(
        self, expected_names: Sequence[str]
    ) -> List[ContainerNode]:
        raise NotImplementedError

    @abstractmethod
    def verify_container_mounts(
        self, mount_specs: Mapping[str, str]
    ) -> List[ContainerMountCheck]:
        raise NotImplementedError

    @abstractmethod
    def is_primary_media_mount_stale(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def restart_containers(self, container_names: Sequence[str]) -> bool:
        raise NotImplementedError
