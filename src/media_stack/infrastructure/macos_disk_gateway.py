import os
import subprocess
import sys

from media_stack.domain.repositories.disk_gateway import IDiskGateway
from media_stack.domain.value_objects.storage import VolumeMountPath


class MacOSDiskUtilGateway(IDiskGateway):
    """
    Implements IDiskGateway using macOS DiskArbitration (/usr/sbin/diskutil)
    with POSIX fallback for Linux hosts.
    """

    def is_volume_mounted(self, mount_path: VolumeMountPath) -> bool:
        try:
            if sys.platform == "darwin":
                res = subprocess.run(
                    ["/usr/sbin/diskutil", "info", str(mount_path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode != 0:
                    return False
                out = res.stdout
                return (
                    "Mounted:                   Yes" in out
                    or "Mounted:                  Yes" in out
                    or "Mounted: Yes" in out
                )
            return mount_path.path.exists() and os.access(str(mount_path), os.R_OK)
        except Exception:
            return False
