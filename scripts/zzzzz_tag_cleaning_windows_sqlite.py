"""Windows-safe SQLite connection handling for Tag Cleaning Assist.

Python's sqlite3.Connection context manager commits or rolls back but does not
close the connection. Windows therefore keeps the temporary SQLite file locked
when TagCleaningStore atomically replaces it after a build. Patch the store's
connection factory so leaving a ``with`` block also closes the file handle.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

try:
    from scripts.tag_cleaning_db import TagCleaningStore
except (ImportError, ModuleNotFoundError):
    from tag_cleaning_db import TagCleaningStore  # type: ignore


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _windows_safe_connect(
    self: TagCleaningStore,
    path: Path | None = None,
    *,
    readonly: bool = False,
) -> sqlite3.Connection:
    target = path or self.database_path
    kwargs = {
        "timeout": 2.0 if readonly else 10.0,
        "factory": _ClosingConnection,
    }
    if readonly:
        connection = sqlite3.connect(
            f"file:{target.as_posix()}?mode=ro",
            uri=True,
            check_same_thread=False,
            **kwargs,
        )
    else:
        connection = sqlite3.connect(target, **kwargs)
    connection.row_factory = sqlite3.Row
    return connection


TagCleaningStore._connect = _windows_safe_connect
