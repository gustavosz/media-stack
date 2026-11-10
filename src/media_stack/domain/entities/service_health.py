from dataclasses import dataclass
from typing import Optional

from media_stack.domain.value_objects.network import ServiceEndpointUrl


@dataclass(frozen=True)
class ServiceHealthResult:
    """Entity representing the health probe outcome for a web service."""

    service_name: str
    url: ServiceEndpointUrl
    http_status: Optional[int]
    is_online: bool
