from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class VolumeMountPath:
    """Immutable Value Object representing the mount point of a storage volume."""

    path: Path

    @classmethod
    def from_data_dir(
        cls, data_dir: Path, explicit_mount: Optional[str] = None
    ) -> "VolumeMountPath":
        if explicit_mount and explicit_mount.strip():
            return cls(path=Path(explicit_mount.strip()))
        parts = data_dir.parts
        if len(parts) >= 3 and parts[0] == "/" and parts[1] == "Volumes":
            return cls(path=Path("/Volumes") / parts[2])
        return cls(path=data_dir)

    @property
    def name(self) -> str:
        return self.path.name

    def __str__(self) -> str:
        return str(self.path)


@dataclass(frozen=True)
class InodeLinkCount:
    """Immutable Value Object representing POSIX inode hardlink count (st_nlink)."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("Inode link count cannot be negative.")

    @property
    def is_hardlinked(self) -> bool:
        return self.count > 1


@dataclass(frozen=True)
class FileSizeBytes:
    """Immutable Value Object representing file size in bytes with human-readable conversions."""

    bytes_count: int

    def __post_init__(self) -> None:
        if self.bytes_count < 0:
            raise ValueError("File size cannot be negative.")

    @property
    def gigabytes(self) -> float:
        return self.bytes_count / (1024**3)

    def format_gb(self) -> str:
        return f"{self.gigabytes:.2f} GB"
