import sqlite3
from pathlib import Path

import pytest

from scripts.tag_cleaning_db import TagCleaningStore


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


@pytest.mark.parametrize("rollback", [False, True])
def test_direct_factory_preserves_transactions_and_closes_on_error(tmp_path: Path, rollback: bool):
    store = TagCleaningStore(tmp_path / "transactions")
    with store._connect() as connection:
        connection.execute("CREATE TABLE probe(value INTEGER)")
    connection = store._connect()
    try:
        with connection:
            connection.execute("INSERT INTO probe VALUES (1)")
            if rollback:
                raise RuntimeError("rollback probe")
    except RuntimeError:
        assert rollback
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
    with store._connect(readonly=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM probe").fetchone()[0] == (0 if rollback else 1)
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_existing_database_can_be_rebuilt_on_windows(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "rebuild")
    for tag in ["first", "replacement"]:
        assert store.build_from_actions([{"add": ["gen:" + tag], "remove": []}])["ready"]
        with store._connect(readonly=True) as connection:
            assert connection.execute("SELECT tag FROM tag_stats").fetchall()[0][0] == tag
