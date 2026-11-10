import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request

from media_stack.domain.entities.media_item import MovieMediaAsset, SubtitleStream
from media_stack.domain.repositories.media_library_repository import (
    IMediaLibraryRepository,
)
from media_stack.domain.value_objects.storage import FileSizeBytes, InodeLinkCount
from media_stack.infrastructure.credential_store import ConfigFileCredentialStore


class ApfsMediaLibraryRepository(IMediaLibraryRepository):
    """
    Repository that inspects the APFS media storage directory, verifies inode hardlinks,
    and correlates local files with Jellyfin's indexed subtitle streams.
    """

    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}
    SPANISH_CODES = ("spa", "es", "es-mx", "es-es", "spanish", "español", "latino")

    def __init__(
        self,
        movies_dir: Path,
        credential_store: ConfigFileCredentialStore,
        jellyfin_url: str = "http://localhost:8096",
    ) -> None:
        self._movies_dir = movies_dir
        self._creds = credential_store
        self._jellyfin_url = jellyfin_url.rstrip("/")

    def is_movies_directory_present(self) -> bool:
        return self._movies_dir.exists()

    def scan_movies(self) -> List[MovieMediaAsset]:
        if not self.is_movies_directory_present():
            return []

        jf_by_folder = self._fetch_jellyfin_movies_map()
        movie_folders = sorted([f for f in self._movies_dir.iterdir() if f.is_dir()])

        assets: List[MovieMediaAsset] = []
        for folder in movie_folders:
            videos = [
                f
                for f in folder.glob("*")
                if f.suffix.lower() in self.VIDEO_EXTENSIONS
            ]
            if not videos:
                assets.append(MovieMediaAsset(folder_name=folder.name))
                continue

            vfile = videos[0]
            stat = vfile.stat()
            size_vo = FileSizeBytes(stat.st_size)
            links_vo = InodeLinkCount(stat.st_nlink)

            srt_files = tuple(sorted(s.name for s in folder.glob("*.srt")))

            jf_item = jf_by_folder.get(folder.name)
            jf_title: Optional[str] = None
            spanish_streams: List[SubtitleStream] = []

            if jf_item:
                jf_title = jf_item.get("Name", folder.name)
                for stream in jf_item.get("MediaStreams", []):
                    if stream.get("Type") != "Subtitle":
                        continue
                    lang = (stream.get("Language") or "").lower()
                    display = (stream.get("DisplayTitle") or "").lower()
                    if any(
                        code in lang or code in display for code in self.SPANISH_CODES
                    ):
                        spanish_streams.append(
                            SubtitleStream(
                                display_title=stream.get("DisplayTitle", "Español"),
                                codec=stream.get("Codec", "sub"),
                                is_external=bool(stream.get("IsExternal", False)),
                            )
                        )

            assets.append(
                MovieMediaAsset(
                    folder_name=folder.name,
                    video_filename=vfile.name,
                    size=size_vo,
                    link_count=links_vo,
                    external_srt_files=srt_files,
                    jellyfin_title=jf_title,
                    jellyfin_spanish_streams=tuple(spanish_streams),
                )
            )
        return assets

    def _fetch_jellyfin_movies_map(self) -> Dict[str, Dict[str, Any]]:
        jf_key = self._creds.get_jellyfin_api_key()
        headers = (
            {
                "Authorization": f'MediaBrowser Token="{jf_key.expose()}"',
                "X-Emby-Token": jf_key.expose(),
            }
            if jf_key
            else {}
        )
        url = f"{self._jellyfin_url}/Items?recursive=true&includeItemTypes=Movie&fields=MediaStreams,Path"
        req = urllib.request.Request(url, headers=headers)
        jf_by_folder: Dict[str, Dict[str, Any]] = {}
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                for item in data.get("Items", []):
                    raw_path = item.get("Path", "")
                    for part in Path(raw_path).parts:
                        if "(" in part and ")" in part:
                            jf_by_folder[part] = item
                            break
        except Exception:
            pass
        return jf_by_folder
