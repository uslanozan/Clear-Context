"""Reverse image search adapters behind one interface.

A provider returns pages where the same or a similar image appears. A match is a lead
for reading those pages, not proof of an image's original source or date.
"""

import base64
from typing import Protocol

import httpx

from clear_context.domain.investigation import ImageMatch, MediaOrigin


class ReverseImageFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class ReverseImageSearch(Protocol):
    name: str

    def search(self, data: bytes, mime_type: str) -> MediaOrigin: ...

    def close(self) -> None: ...


def build_reverse_image_search(settings) -> ReverseImageSearch | None:
    """Return the configured adapter, or None when no provider is selected."""
    return None
