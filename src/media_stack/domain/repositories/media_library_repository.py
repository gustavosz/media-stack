from abc import ABC, abstractmethod
from typing import List

from media_stack.domain.entities.media_item import MovieMediaAsset


class IMediaLibraryRepository(ABC):
    """Port for inspecting the physical media library, hardlinks, and indexed metadata."""

    @abstractmethod
    def is_movies_directory_present(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def scan_movies(self) -> List[MovieMediaAsset]:
        raise NotImplementedError
