from dataclasses import dataclass


@dataclass(frozen=True)
class PortNumber:
    """Immutable Value Object representing a valid TCP/UDP port (1-65535)."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or not (1 <= self.value <= 65535):
            raise ValueError(
                f"Invalid port number: {self.value}. Must be between 1 and 65535."
            )

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class IpAddress:
    """Immutable Value Object representing an IPv4/IPv6 address."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("IP address cannot be empty.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ServiceEndpointUrl:
    """Immutable Value Object representing an HTTP/HTTPS service endpoint URL."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid service URL '{self.value}': must start with http:// or https://"
            )

    def __str__(self) -> str:
        return self.value
