from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ContainerMountCheck:
    """Represents the accessibility state of a bind mount inside a container."""

    container_name: str
    mount_point: str
    is_accessible: bool
    error_reason: Optional[str] = None


@dataclass(frozen=True)
class ContainerNode:
    """Entity representing a Docker container within the Media Stack."""

    name: str
    state: str

    @property
    def is_running(self) -> bool:
        return self.state.lower() == "running"
