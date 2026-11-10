from dataclasses import dataclass


@dataclass(frozen=True)
class ApiKey:
    """Immutable Value Object representing a service authentication API Key."""

    _secret: str

    def __post_init__(self) -> None:
        if not self._secret or not self._secret.strip():
            raise ValueError("ApiKey secret cannot be empty.")

    def expose(self) -> str:
        """Returns the raw API key string for outbound HTTP headers."""
        return self._secret

    def __repr__(self) -> str:
        masked = (
            f"{self._secret[:4]}...{self._secret[-4:]}"
            if len(self._secret) > 8
            else "****"
        )
        return f"ApiKey({masked})"

    def __str__(self) -> str:
        return self.__repr__()
