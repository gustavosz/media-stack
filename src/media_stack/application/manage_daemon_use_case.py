from pathlib import Path
from typing import List, Optional

from media_stack.domain.repositories.system_services import IDaemonManager


class ManageDaemonUseCase:
    """Application Use Case for managing the lifecycle of the OS background daemon."""

    def __init__(self, daemon_manager: IDaemonManager) -> None:
        self._daemon_manager = daemon_manager

    def install(self) -> Path:
        return self._daemon_manager.install()

    def uninstall(self) -> List[Path]:
        return self._daemon_manager.uninstall()

    def status(self) -> Optional[str]:
        return self._daemon_manager.get_status()
