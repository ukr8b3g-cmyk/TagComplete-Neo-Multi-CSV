"""Optional Danbooru tag-cleaning index for TagComplete Neo Multi-CSV.

The runtime lookup path uses only Python's sqlite3 module. The source dataset is
Parquet, so the explicit Update/Build action installs DuckDB into an extension-
local vendor directory only when it is needed. The feature is default-off and
never imports DuckDB during normal autocomplete startup or lookup.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SOURCE_URL = (
    "https://huggingface.co/datasets/Grio43/Tag_cleaning/resolve/main/"
    "merged_2026.parquet?download=true"
)
SOURCE_REPOSITORY = "Grio43/Tag_cleaning"
DATABASE_SCHEMA_VERSION = 1
MAX_SOURCE_BYTES = 128 * 1024 * 1024

CATEGORY_TO_KIND = {
    0: "gen",
    1: "artist",
    3: "copyright",
    4: "char",
    5: "meta",
}

SENSITIVITY_PRESETS = {
    "Conservative": {
        "min_actions": 50,
        "warning_ratio": 0.85,
        "suggestion_confidence": 0.75,
        "suggestion_support": 20,
    },
    "Balanced": {
        "min_actions": 20,
        "warning_ratio": 0.75,
        "suggestion_confidence": 0.60,
        "suggestion_support": 10,
    },
    "Broad": {
        "min_actions": 8,
        "warning_ratio": 0.65,
        "suggestion_confidence": 0.45,
        "suggestion_support": 5,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_tag(value: Any) -> tuple[str, str]:
    """Return ``(kind, tag)`` while keeping Danbooru punctuation intact."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    if not text:
        return "", ""
    kind = ""
    if ":" in text:
        prefix, rest = text.split(":", 1)
        if prefix in {"gen", "artist", "copyright", "char", "meta"}:
            kind, text = prefix, rest
    text = "_".join(text.split())
    return kind, text


def sensitivity_settings(name: str) -> dict[str, Any]:
    return dict(SENSITIVITY_PRESETS.get(name, SENSITIVITY_PRESETS["Balanced"]))


class TagCleaningStore:
    """Small SQLite lookup layer generated from the image-level corrections."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.root / "tag_cleaning.sqlite3"
        self.vendor_path = self.root / "_vendor"
        self._lock = threading.RLock()
        self._cache: dict[tuple[Any, ...], dict[str, Any] | None] = {}
        self._cache_database_id = ""

    def _connect(self, path: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
        target = path or self.database_path
        if readonly:
            connection = sqlite3.connect(
                f"file:{target.as_posix()}?mode=ro",
                uri=True,
                timeout=2.0,
                check_same_thread=False,
            )
        else:
            connection = sqlite3.connect(target, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE tag_stats (
                kind TEXT NOT NULL,
                tag TEXT NOT NULL,
                add_count INTEGER NOT NULL DEFAULT 0,
                remove_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (kind, tag)
            ) WITHOUT ROWID;
            CREATE TABLE cooccurrence (
                source_kind TEXT NOT NULL,
                source_tag TEXT NOT NULL,
                candidate_kind TEXT NOT NULL,
                candidate_tag TEXT NOT NULL,
                pair_count INTEGER NOT NULL,
                PRIMARY KEY (source_kind, source_tag, candidate_kind, candidate_tag)
            ) WITHOUT ROWID;
            CREATE INDEX cooccurrence_source_idx
                ON cooccurrence(source_kind, source_tag, pair_count DESC);
            """
        )

    @staticmethod
    def _write_metadata(connection: sqlite3.Connection, metadata: Mapping[str, Any]) -> None:
        connection.executemany(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
            [(str(key), str(value)) for key, value in metadata.items()],
        )

    def status(self) -> dict[str, Any]:
        if not self.database_path.exists():
            return {"ready": False, "path": str(self.database_path), "size_bytes": 0, "metadata": {}}
        try:
            with self._connect(readonly=True) as connection:
                metadata = {
                    row["key"]: row["value"]
                    for row in connection.execute("SELECT key, value FROM metadata")
                }
                schema = int(metadata.get("schema_version", "0") or 0)
                if schema != DATABASE_SCHEMA_VERSION:
                    raise ValueError(f"schema {schema} != {DATABASE_SCHEMA_VERSION}")
                tag_count = connection.execute("SELECT COUNT(*) FROM tag_stats").fetchone()[0]
                pair_count = connection.execute("SELECT COUNT(*) FROM cooccurrence").fetchone()[0]
            return {
                "ready": True,
                "path": str(self.database_path),
                "size_bytes": self.database_path.stat().st_size,
                "tag_count": int(tag_count),
                "pair_count": int(pair_count),
                "metadata": metadata,
                "database_id": metadata.get("database_id", ""),
            }
        except (OSError, sqlite3.Error, ValueError) as exc:
            return {
                "ready": False,
                "path": str(self.database_path),
                "size_bytes": self.database_path.stat().st_size if self.database_path.exists() else 0,
                "metadata": {},
                "error": str(exc),
            }

    def _database_id(self, connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'database_id'"
        ).fetchone()
        return str(row[0]) if row else ""

    def _lookup_one(
        self,
        connection: sqlite3.Connection,
        tag: str,
        category: int | None,
        *,
        show_warnings: bool,
        show_suggestions: bool,
        sensitivity: str,
        max_suggestions: int = 3,
    ) -> dict[str, Any] | None:
        explicit_kind, canonical = normalize_tag(tag)
        if not canonical:
            return None
        kind = explicit_kind or CATEGORY_TO_KIND.get(category, "")
        thresholds = sensitivity_settings(sensitivity)
        cache_key = (
            kind,
            canonical,
            bool(show_warnings),
            bool(show_suggestions),
            sensitivity,
            int(max_suggestions),
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        if kind:
            rows = connection.execute(
                "SELECT kind, tag, add_count, remove_count FROM tag_stats WHERE kind = ? AND tag = ?",
                (kind, canonical),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT kind, tag, add_count, remove_count FROM tag_stats WHERE tag = ?",
                (canonical,),
            ).fetchall()
        if not rows:
            self._cache[cache_key] = None
            return None

        add_count = sum(int(row["add_count"]) for row in rows)
        remove_count = sum(int(row["remove_count"]) for row in rows)
        total_actions = add_count + remove_count
        remove_ratio = remove_count / total_actions if total_actions else 0.0
        warning = bool(
            show_warnings
            and total_actions >= int(thresholds["min_actions"])
            and remove_ratio >= float(thresholds["warning_ratio"])
        )

        suggestions: list[dict[str, Any]] = []
        if show_suggestions and remove_count:
            candidate_rows: list[tuple[sqlite3.Row, int]] = []
            for source_row in rows:
                source_remove_count = int(source_row["remove_count"])
                if not source_remove_count:
                    continue
                for candidate in connection.execute(
                    "SELECT candidate_kind, candidate_tag, pair_count "
                    "FROM cooccurrence WHERE source_kind = ? AND source_tag = ? "
                    "ORDER BY pair_count DESC, candidate_tag ASC LIMIT 12",
                    (source_row["kind"], canonical),
                ):
                    candidate_rows.append((candidate, source_remove_count))
            candidate_rows.sort(
                key=lambda item: (-int(item[0]["pair_count"]), item[0]["candidate_tag"])
            )
            seen: set[tuple[str, str]] = set()
            for candidate, source_remove_count in candidate_rows:
                candidate_key = (
                    str(candidate["candidate_kind"]),
                    str(candidate["candidate_tag"]),
                )
                if candidate_key in seen:
                    continue
                seen.add(candidate_key)
                support = int(candidate["pair_count"])
                confidence = support / max(1, source_remove_count)
                if support < int(thresholds["suggestion_support"]):
                    continue
                if confidence < float(thresholds["suggestion_confidence"]):
                    continue
                suggestions.append(
                    {
                        "kind": candidate_key[0],
                        "tag": candidate_key[1],
                        "support": support,
                        "confidence": round(confidence, 4),
                    }
                )
                if len(suggestions) >= max_suggestions:
                    break

        result = {
            "tag": canonical,
            "kind": kind or "mixed",
            "add_count": add_count,
            "remove_count": remove_count,
            "total_actions": total_actions,
            "remove_ratio": round(remove_ratio, 4),
            "warning": warning,
            "suggestions": suggestions,
        }
        self._cache[cache_key] = result
        return result

    def lookup(
        self,
        items: Sequence[Mapping[str, Any]],
        *,
        show_warnings: bool = True,
        show_suggestions: bool = True,
        sensitivity: str = "Balanced",
    ) -> dict[str, Any]:
        status = self.status()
        if not status.get("ready"):
            return {"ready": False, "database_id": "", "results": []}
        with self._lock, self._connect(readonly=True) as connection:
            database_id = self._database_id(connection)
            if database_id != self._cache_database_id:
                self._cache.clear()
                self._cache_database_id = database_id
            output = []
            for item in items[:250]:
                tag = str(item.get("tag") or "")
                category_value = item.get("category")
                try:
                    category = int(category_value) if category_value is not None else None
                except (TypeError, ValueError):
                    category = None
                match = self._lookup_one(
                    connection,
                    tag,
                    category,
                    show_warnings=show_warnings,
                    show_suggestions=show_suggestions,
                    sensitivity=sensitivity,
                )
                output.append({"requested_tag": tag, "category": category, "match": match})
            return {"ready": True, "database_id": database_id, "results": output}

    def build_from_actions(
        self,
        actions: Iterable[Mapping[str, Any]],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a database from iterable correction rows; used by tests/tools."""
        stats: dict[tuple[str, str], list[int]] = {}
        pairs: dict[tuple[str, str, str, str], int] = {}
        row_count = 0
        for row in actions:
            row_count += 1
            adds = [normalize_tag(value) for value in (row.get("add") or [])]
            removes = [normalize_tag(value) for value in (row.get("remove") or [])]
            adds = [(kind, tag) for kind, tag in adds if kind and tag]
            removes = [(kind, tag) for kind, tag in removes if kind and tag]
            for key in adds:
                stats.setdefault(key, [0, 0])[0] += 1
            for key in removes:
                stats.setdefault(key, [0, 0])[1] += 1
            for source_kind, source_tag in removes:
                for candidate_kind, candidate_tag in adds:
                    if (source_kind, source_tag) == (candidate_kind, candidate_tag):
                        continue
                    key = (source_kind, source_tag, candidate_kind, candidate_tag)
                    pairs[key] = pairs.get(key, 0) + 1

        database_id = _utc_now()
        merged_metadata = {
            "schema_version": DATABASE_SCHEMA_VERSION,
            "database_id": database_id,
            "built_at": database_id,
            "source_repository": SOURCE_REPOSITORY,
            "source_rows": row_count,
        }
        if metadata:
            merged_metadata.update(metadata)
        temp = self.root / f".{self.database_path.name}.tmp"
        if temp.exists():
            temp.unlink()
        with self._connect(temp) as connection:
            self._create_schema(connection)
            connection.executemany(
                "INSERT INTO tag_stats(kind, tag, add_count, remove_count) VALUES (?, ?, ?, ?)",
                [(kind, tag, counts[0], counts[1]) for (kind, tag), counts in stats.items()],
            )
            connection.executemany(
                "INSERT INTO cooccurrence(source_kind, source_tag, candidate_kind, candidate_tag, pair_count) "
                "VALUES (?, ?, ?, ?, ?)",
                [(*key, count) for key, count in pairs.items()],
            )
            self._write_metadata(connection, merged_metadata)
            connection.commit()
        os.replace(temp, self.database_path)
        self._cache.clear()
        self._cache_database_id = ""
        return self.status()

    def _ensure_duckdb(self):
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pass
        self.vendor_path.mkdir(parents=True, exist_ok=True)
        vendor = str(self.vendor_path)
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            print("[TagComplete Neo Multi-CSV] Installing local DuckDB for Tag Cleaning build...")
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--quiet",
                    "--target",
                    vendor,
                    "--only-binary=:all:",
                    "duckdb==1.4.1",
                ]
            )
            importlib.invalidate_caches()
            return importlib.import_module("duckdb")

    def _download_source(self, target: Path) -> dict[str, str]:
        import requests

        with requests.get(SOURCE_URL, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("Content-Length", "0") or 0)
            if content_length and content_length > MAX_SOURCE_BYTES:
                raise ValueError("Tag Cleaning source exceeds the configured size limit")
            written = 0
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > MAX_SOURCE_BYTES:
                        raise ValueError("Tag Cleaning source exceeds the configured size limit")
                    handle.write(chunk)
            return {
                "source_bytes": str(written),
                "source_etag": str(response.headers.get("ETag", "")),
                "source_last_modified": str(response.headers.get("Last-Modified", "")),
            }

    def build_from_parquet(self, parquet_path: str | Path) -> dict[str, Any]:
        """Generate the compact SQLite index using DuckDB only for this build."""
        duckdb = self._ensure_duckdb()
        parquet_path = Path(parquet_path)
        database_id = _utc_now()
        temp = self.root / f".{self.database_path.name}.tmp"
        if temp.exists():
            temp.unlink()
        source = parquet_path.as_posix().replace("'", "''")
        duck = duckdb.connect(database=":memory:")
        try:
            stats_query = f"""
                WITH actions AS (
                    SELECT unnest(add) AS raw_tag, 1 AS is_add, 0 AS is_remove
                    FROM read_parquet('{source}')
                    UNION ALL
                    SELECT unnest(remove) AS raw_tag, 0 AS is_add, 1 AS is_remove
                    FROM read_parquet('{source}')
                )
                SELECT
                    split_part(raw_tag, ':', 1) AS kind,
                    substr(raw_tag, strpos(raw_tag, ':') + 1) AS tag,
                    sum(is_add)::BIGINT AS add_count,
                    sum(is_remove)::BIGINT AS remove_count
                FROM actions
                WHERE strpos(raw_tag, ':') > 1
                GROUP BY 1, 2
                ORDER BY 1, 2
            """
            pair_query = f"""
                WITH pairs AS (
                    SELECT
                        split_part(r.raw_tag, ':', 1) AS source_kind,
                        substr(r.raw_tag, strpos(r.raw_tag, ':') + 1) AS source_tag,
                        split_part(a.raw_tag, ':', 1) AS candidate_kind,
                        substr(a.raw_tag, strpos(a.raw_tag, ':') + 1) AS candidate_tag,
                        count(*)::BIGINT AS pair_count
                    FROM read_parquet('{source}') AS t,
                         unnest(t.remove) AS r(raw_tag),
                         unnest(t.add) AS a(raw_tag)
                    WHERE strpos(r.raw_tag, ':') > 1
                      AND strpos(a.raw_tag, ':') > 1
                      AND r.raw_tag <> a.raw_tag
                    GROUP BY 1, 2, 3, 4
                ), ranked AS (
                    SELECT *, row_number() OVER (
                        PARTITION BY source_kind, source_tag
                        ORDER BY pair_count DESC, candidate_tag ASC
                    ) AS rank_no
                    FROM pairs
                    WHERE pair_count >= 2
                )
                SELECT source_kind, source_tag, candidate_kind, candidate_tag, pair_count
                FROM ranked
                WHERE rank_no <= 12
                ORDER BY source_kind, source_tag, pair_count DESC, candidate_tag
            """
            with self._connect(temp) as connection:
                self._create_schema(connection)
                stats_cursor = duck.execute(stats_query)
                while True:
                    batch = stats_cursor.fetchmany(5000)
                    if not batch:
                        break
                    connection.executemany(
                        "INSERT INTO tag_stats(kind, tag, add_count, remove_count) VALUES (?, ?, ?, ?)",
                        batch,
                    )
                pair_cursor = duck.execute(pair_query)
                while True:
                    batch = pair_cursor.fetchmany(5000)
                    if not batch:
                        break
                    connection.executemany(
                        "INSERT INTO cooccurrence(source_kind, source_tag, candidate_kind, candidate_tag, pair_count) "
                        "VALUES (?, ?, ?, ?, ?)",
                        batch,
                    )
                source_rows = duck.execute(
                    f"SELECT count(*) FROM read_parquet('{source}')"
                ).fetchone()[0]
                self._write_metadata(
                    connection,
                    {
                        "schema_version": DATABASE_SCHEMA_VERSION,
                        "database_id": database_id,
                        "built_at": database_id,
                        "source_repository": SOURCE_REPOSITORY,
                        "source_url": SOURCE_URL.split("?", 1)[0],
                        "source_rows": int(source_rows),
                    },
                )
                connection.commit()
        finally:
            duck.close()
        os.replace(temp, self.database_path)
        self._cache.clear()
        self._cache_database_id = ""
        return self.status()

    def update_from_remote(self) -> dict[str, Any]:
        """Explicit user action: download source Parquet and rebuild the SQLite DB."""
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(
                prefix="tag_cleaning_", suffix=".parquet", dir=self.root
            )
            os.close(handle)
            source_path = Path(temp_name)
            try:
                download_meta = self._download_source(source_path)
                result = self.build_from_parquet(source_path)
                if result.get("ready"):
                    with self._connect() as connection:
                        self._write_metadata(connection, download_meta)
                        connection.commit()
                    result = self.status()
                return result
            finally:
                try:
                    source_path.unlink(missing_ok=True)
                except OSError:
                    pass
