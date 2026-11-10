from pathlib import Path
import subprocess
import sys
from typing import List, Optional

from media_stack.domain.repositories.system_services import (
    IDaemonManager,
    INotificationService,
)


class MacOSNotificationService(INotificationService):
    """Dispatches native macOS notifications via osascript."""

    def notify(self, title: str, message: str) -> None:
        if sys.platform != "darwin":
            return
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
        except Exception:
            pass


class MacOSLaunchdDaemonManager(IDaemonManager):
    """Manages the macOS LaunchAgent .plist lifecycle for the disk watcher daemon."""

    SERVICE_LABEL = "com.media-stack.disk-watcher"
    LEGACY_LABEL = "com.gusz.media-stack.disk-watcher"

    def __init__(self, project_dir: Path, config_dir: Path) -> None:
        self._project_dir = project_dir
        self._config_dir = config_dir

    @property
    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{self.SERVICE_LABEL}.plist"

    @property
    def _legacy_plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{self.LEGACY_LABEL}.plist"

    def install(self) -> Path:
        if sys.platform != "darwin":
            raise RuntimeError(
                "La instalación como LaunchAgent solo está soportada en macOS."
            )

        self._plist_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_dir.mkdir(parents=True, exist_ok=True)

        for candidate in (self._legacy_plist_path, self._plist_path):
            if candidate.exists():
                subprocess.run(
                    ["launchctl", "unload", str(candidate)], capture_output=True
                )
        if self._legacy_plist_path.exists():
            self._legacy_plist_path.unlink(missing_ok=True)

        stdout_log = self._config_dir / "disk_watcher_stdout.log"
        stderr_log = self._config_dir / "disk_watcher_stderr.log"
        src_dir = self._project_dir / "src"

        plist_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>media_stack</string>
        <string>watch-disk</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{self._project_dir}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
        <key>PYTHONPATH</key>
        <string>{src_dir}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
</dict>
</plist>
"""
        self._plist_path.write_text(plist_xml, encoding="utf-8")
        res = subprocess.run(
            ["launchctl", "load", "-w", str(self._plist_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Error al cargar daemon con launchctl: {res.stderr.strip()}"
            )
        return self._plist_path

    def uninstall(self) -> List[Path]:
        removed: List[Path] = []
        for candidate in (self._plist_path, self._legacy_plist_path):
            if candidate.exists():
                subprocess.run(
                    ["launchctl", "unload", str(candidate)], capture_output=True
                )
                candidate.unlink(missing_ok=True)
                removed.append(candidate)
        return removed

    def get_status(self) -> Optional[str]:
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "disk-watcher" in line:
                return line.strip()
        return None
