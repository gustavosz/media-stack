import json
from pathlib import Path
import subprocess
from typing import Dict, List, Mapping, Optional, Sequence

from media_stack.domain.entities.container import ContainerMountCheck, ContainerNode
from media_stack.domain.repositories.container_repository import IContainerRepository


class DockerComposeContainerRepository(IContainerRepository):
    """Docker CLI & Docker Compose adapter implementing IContainerRepository."""

    def __init__(self, compose_file: Path) -> None:
        self._compose_file = compose_file

    @staticmethod
    def _run_cmd(cmd: Sequence[str], timeout: int = 10) -> Optional[str]:
        try:
            res = subprocess.run(
                list(cmd), capture_output=True, text=True, timeout=timeout
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def get_containers_status(
        self, expected_names: Sequence[str]
    ) -> List[ContainerNode]:
        raw = self._run_cmd(["docker", "ps", "-a", "--format", "{{json .}}"])
        running_map: Dict[str, str] = {}
        if raw:
            for line in raw.splitlines():
                try:
                    data = json.loads(line)
                    running_map[data.get("Names", "")] = data.get("State", "unknown")
                except Exception:
                    pass

        results: List[ContainerNode] = []
        for name in expected_names:
            state = running_map.get(name, "missing")
            results.append(ContainerNode(name=name, state=state))
        return results

    def verify_container_mounts(
        self, mount_specs: Mapping[str, str]
    ) -> List[ContainerMountCheck]:
        checks: List[ContainerMountCheck] = []
        for cname, mount_point in mount_specs.items():
            out = self._run_cmd(
                ["docker", "exec", cname, "ls", "-A", mount_point], timeout=5
            )
            checks.append(
                ContainerMountCheck(
                    container_name=cname,
                    mount_point=mount_point,
                    is_accessible=out is not None,
                    error_reason=(
                        None if out is not None else "Stale/Inaccesible"
                    ),
                )
            )
        return checks

    def is_primary_media_mount_stale(self) -> bool:
        try:
            res = subprocess.run(
                ["docker", "exec", "jellyfin", "ls", "-A", "/data/media/movies"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return True
            files = [f for f in res.stdout.strip().splitlines() if f]
            return len(files) == 0
        except Exception:
            return False

    def restart_containers(self, container_names: Sequence[str]) -> bool:
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self._compose_file),
            "restart",
            *container_names,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            return res.returncode == 0
        except Exception:
            return False
