"""Compatibility entrypoint for content extraction.

The active implementation lives under ``services.content``.  The old monolithic
implementation is kept separately in ``content_extractor_legacy.py`` only as a
rollback reference.
"""

from services.content.extractor import ContentExtractor, TaskCancelledError

__all__ = ["ContentExtractor", "TaskCancelledError"]
