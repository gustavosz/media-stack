from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class INotificationService(ABC):
    """Port for dispatching OS-level user notifications."""

    @abstractmethod
    def notify(self, title: str, message: str) -> None:
        raise NotImplementedError


class IDaemonManager(ABC):
    """Port for installing, removing, and querying background OS daemons."""

    @abstractmethod
    def install(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def uninstall(self) -> List[Path]:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> Optional[str]:
        raise NotImplementedError
