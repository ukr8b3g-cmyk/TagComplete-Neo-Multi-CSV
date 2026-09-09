import sqlite3
from pathlib import Path

import pytest

from scripts.tag_cleaning_db import TagCleaningStore
import scripts.zzzzz_tag_cleaning_windows_sqlite  # noqa: F401


def test_tag_cleaning_connection_closes_after_context_manager(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "cleaning")
    connection = store._connect(store.root / "context.sqlite3")
    with connection as active:
        active.execute("CREATE TABLE probe(value INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_tag_cleaning_atomic_replace_has_no_open_sqlite_handle(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "cleaning")
    status = store.build_from_actions(
        [
            {"add": ["gen:new_tag"], "remove": ["gen:old_tag"]},
            {"add": [], "remove": ["gen:old_tag"]},
        ]
    )
    assert status["ready"] is True
    assert store.database_path.exists()
