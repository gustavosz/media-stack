from dataclasses import dataclass
from typing import Optional, Tuple

from media_stack.domain.value_objects.storage import FileSizeBytes, InodeLinkCount


@dataclass(frozen=True)
class SubtitleStream:
    """Value Object representing a subtitle track indexed by Jellyfin."""

    display_title: str
    codec: str
    is_external: bool

    def format_description(self) -> str:
        ext_tag = " - Externo" if self.is_external else ""
        return f"{self.display_title} - {self.codec.upper()}{ext_tag}"


@dataclass(frozen=True)
class MovieMediaAsset:
    """Entity representing a physical movie folder, its APFS hardlink state, and subtitles."""

    folder_name: str
    video_filename: Optional[str] = None
    size: Optional[FileSizeBytes] = None
    link_count: Optional[InodeLinkCount] = None
    external_srt_files: Tuple[str, ...] = ()
    jellyfin_title: Optional[str] = None
    jellyfin_spanish_streams: Tuple[SubtitleStream, ...] = ()

    @property
    def has_video_file(self) -> bool:
        return self.video_filename is not None

    @property
    def is_indexed_in_jellyfin(self) -> bool:
        return self.jellyfin_title is not None
