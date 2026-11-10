from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from media_stack.domain.entities.bootstrap_step import BootstrapStepResult


class IStackProvisioner(ABC):
    """Port for idempotent zero-touch provisioning and interconnection of Media Stack services."""

    @abstractmethod
    def ensure_storage_directories(self) -> BootstrapStepResult:
        raise NotImplementedError

    @abstractmethod
    def ensure_qbittorrent_config(self) -> BootstrapStepResult:
        raise NotImplementedError

    @abstractmethod
    def ensure_arr_root_folders(self) -> List[BootstrapStepResult]:
        raise NotImplementedError

    @abstractmethod
    def ensure_arr_download_clients(self) -> List[BootstrapStepResult]:
        raise NotImplementedError

    @abstractmethod
    def ensure_prowlarr_integrations(self) -> List[BootstrapStepResult]:
        raise NotImplementedError

    @abstractmethod
    def ensure_bazarr_integrations(self) -> BootstrapStepResult:
        raise NotImplementedError

    @abstractmethod
    def ensure_calibre_library_initialized(self) -> BootstrapStepResult:
        raise NotImplementedError
