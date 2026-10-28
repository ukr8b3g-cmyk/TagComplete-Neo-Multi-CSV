"""Compatibility import; TagCleaningStore now owns commit/rollback/close handling."""

try:
    from scripts.tag_cleaning_db import TagCleaningStore
except (ImportError, ModuleNotFoundError):
    from tag_cleaning_db import TagCleaningStore  # type: ignore
