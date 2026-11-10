from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from media_stack.domain.value_objects.storage import VolumeMountPath


def _load_dotenv_file(env_path: Path) -> None:
    """Loads key=value pairs from a .env file into os.environ without external dependencies."""
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


@dataclass(frozen=True)
class AppSettings:
    """Centralized Infrastructure Settings resolved from environment and .env."""

    project_dir: Path
    compose_file: Path
    config_dir: Path
    data_dir: Path
    movies_dir: Path
    external_disk_mount: VolumeMountPath
    disk_watcher_log: Path
    qbittorrent_url: str
    jellyfin_url: str

    @classmethod
    def from_environment(cls, explicit_project_dir: Optional[Path] = None) -> "AppSettings":
        # Path(__file__) is src/media_stack/infrastructure/settings.py -> parent^3 is project root
        default_root = Path(__file__).resolve().parent.parent.parent.parent
        project_dir = Path(
            os.getenv("PROJECT_DIR", str(explicit_project_dir or default_root))
        ).resolve()

        _load_dotenv_file(project_dir / ".env")

        config_raw = os.getenv("CONFIG_DIR", "./config")
        config_dir = (
            Path(config_raw)
            if Path(config_raw).is_absolute()
            else (project_dir / config_raw).resolve()
        )

        data_raw = os.getenv("DATA_DIR", "/Volumes/Media/data")
        data_dir = Path(data_raw)

        mount_vo = VolumeMountPath.from_data_dir(
            data_dir=data_dir,
            explicit_mount=os.getenv("EXTERNAL_DISK_MOUNT"),
        )

        return cls(
            project_dir=project_dir,
            compose_file=project_dir / "docker-compose.yml",
            config_dir=config_dir,
            data_dir=data_dir,
            movies_dir=data_dir / "media" / "movies",
            external_disk_mount=mount_vo,
            disk_watcher_log=config_dir / "disk_watcher.log",
            qbittorrent_url=os.getenv("QBITTORRENT_URL", "http://localhost:8080"),
            jellyfin_url=os.getenv("JELLYFIN_URL", "http://localhost:8096"),
        )
