"""The part of feedparser that PulseAI uses. feedparser ships no type information."""

from typing import IO, Any

class FeedParserDict(dict[str, Any]):
    """feedparser's dict, which also answers to attribute access for the keys it always sets."""

    bozo: int
    entries: list[FeedParserDict]

def parse(url_file_stream_or_string: IO[bytes], **kwargs: object) -> FeedParserDict:
    """Parse a feed from a stream.

    feedparser also takes a URL, a path or the document itself, and fetches or opens the first
    two. Only a stream is declared here, so a bytes or str argument is a type error.
    """
