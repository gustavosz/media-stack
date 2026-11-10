from abc import ABC, abstractmethod
from typing import List

from media_stack.domain.entities.service_health import ServiceHealthResult


class IServiceHealthGateway(ABC):
    """Port for probing web service APIs and triggering library actions."""

    @abstractmethod
    def check_all_services(self) -> List[ServiceHealthResult]:
        raise NotImplementedError

    @abstractmethod
    def get_bazarr_providers_summary(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def trigger_jellyfin_library_refresh(self) -> bool:
        raise NotImplementedError
