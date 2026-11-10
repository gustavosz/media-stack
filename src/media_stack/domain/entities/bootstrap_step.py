from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapStepResult:
    """Immutable Value Object representing the outcome of an automated provisioning step."""

    step_name: str
    succeeded: bool
    details: str
