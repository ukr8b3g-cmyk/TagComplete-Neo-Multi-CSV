"""File parsing and per-file persistent caches for Multi-CSV search."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence

from .tacjp_fast_search_common import (
    CACHE_VERSION, FILE_CACHE_VERSION, DataStore, _ALIAS_KEYS, _CATEGORY_KEYS,
    _CATEGORY_SCHEME_KEYS, _COUNT_KEYS, _INSERT_MODE_KEYS, _SOURCE_TYPE_KEYS,
    _TAG_KEYS, _TRANSLATION_KEYS, _as_mapping, _clean, _first, _iter_rows,
    _safe_path, _split_values, _to_category, _to_int, canonical_tag,
    infer_category_scheme, infer_insert_mode, infer_source_type,
)


class FastSearchFilesMixin:
    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.cache_dir = data_store.cache_dir / f"fast-search-v{CACHE_VERSION}"
        self.file_cache_dir = self.cache_dir / "files"
        self.index_cache_dir = self.cache_dir / "indexes"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._file_memory: OrderedDict[str, Any] = OrderedDict()
        self._building: dict[str, threading.Event] = {}
        self._build_errors: dict[str, BaseException] = {}
        self._lock = threading.RLock()
        self.build_count = 0

    def _resolve_files(
        self,
        tag_files: Sequence[str],
        translation_files: Sequence[str],
    ) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
        tag_items: list[tuple[str, Path]] = []
        translation_items: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for name in tag_files:
            clean_name = _clean(name)
            if not clean_name or clean_name.casefold() in seen:
                continue
            seen.add(clean_name.casefold())
            try:
                tag_items.append((clean_name, _safe_path(self.data_store.tag_dir, clean_name)))
            except FileNotFoundError:
                continue
        if tag_files and not tag_items:
            available = self.data_store.list_tag_files()
            if available:
                name = available[0].name
                tag_items.append((name, _safe_path(self.data_store.tag_dir, name)))

        seen.clear()
        for name in translation_files:
            clean_name = _clean(name)
            if not clean_name or clean_name.casefold() in seen:
                continue
            seen.add(clean_name.casefold())
            try:
                translation_items.append(
                    (clean_name, _safe_path(self.data_store.translation_dir, clean_name))
                )
            except FileNotFoundError:
                continue
        return tag_items, translation_items

    @staticmethod
    def _stat_token(path: Path) -> tuple[int, int]:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def _signature(
        self,
        tag_items: Sequence[tuple[str, Path]],
        translation_items: Sequence[tuple[str, Path]],
    ) -> tuple[str, str]:
        manifest = {
            "version": CACHE_VERSION,
            "tags": [[name, *self._stat_token(path)] for name, path in tag_items],
            "translations": [
                [name, *self._stat_token(path)] for name, path in translation_items
            ],
        }
        text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest(), text

    def _file_signature(self, kind: str, name: str, path: Path) -> str:
        size, mtime_ns = self._stat_token(path)
        token = f"{FILE_CACHE_VERSION}|{kind}|{name}|{size}|{mtime_ns}"
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _atomic_pickle(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    @staticmethod
    def _read_pickle(path: Path) -> Any | None:
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (FileNotFoundError, EOFError, OSError, pickle.PickleError, AttributeError, ValueError):
            try:
                path.unlink()
            except OSError:
                pass
            return None

    def _remember_file(self, key: str, value: Any, max_entries: int = 24) -> None:
        with self._lock:
            self._file_memory[key] = value
            self._file_memory.move_to_end(key)
            while len(self._file_memory) > max_entries:
                self._file_memory.popitem(last=False)

    def _load_parsed_tag_file(self, name: str, path: Path, persistent: bool) -> list[tuple[Any, ...]]:
        key = self._file_signature("tag", name, path)
        with self._lock:
            cached = self._file_memory.get(key)
            if cached is not None:
                self._file_memory.move_to_end(key)
                return cached
        cache_path = self.file_cache_dir / f"tag-{key}.pkl"
        if persistent:
            payload = self._read_pickle(cache_path)
            if isinstance(payload, dict) and payload.get("version") == FILE_CACHE_VERSION:
                rows = payload.get("rows")
                if isinstance(rows, list):
                    self._remember_file(key, rows)
                    return rows

        rows: list[tuple[Any, ...]] = []
        file_source = infer_source_type(name)
        file_scheme = infer_category_scheme(name)
        for header, row in _iter_rows(path):
            if header:
                mapping = _as_mapping(header, row)
                tag = _first(mapping, _TAG_KEYS)
                category = _to_category(_first(mapping, _CATEGORY_KEYS))
                count = _to_int(_first(mapping, _COUNT_KEYS))
                aliases = tuple(_split_values(_first(mapping, _ALIAS_KEYS)))
                translations = tuple(_split_values(_first(mapping, _TRANSLATION_KEYS)))
                source_type = infer_source_type(name, _first(mapping, _SOURCE_TYPE_KEYS))
                scheme = infer_category_scheme(name, _first(mapping, _CATEGORY_SCHEME_KEYS))
                insert_mode = infer_insert_mode(tag, source_type, _first(mapping, _INSERT_MODE_KEYS))
            else:
                tag = _clean(row[0] if row else "")
                category = _to_category(row[1] if len(row) > 1 else "")
                count = _to_int(row[2] if len(row) > 2 else "")
                aliases = tuple(_split_values(row[3] if len(row) > 3 else ""))
                translations = tuple(_split_values(row[4] if len(row) > 4 else ""))
                source_type = file_source
                scheme = file_scheme
                insert_mode = infer_insert_mode(tag, source_type)
            if tag and not tag.startswith("#"):
                rows.append(
                    (tag, category, count, aliases, translations, source_type, insert_mode, scheme)
                )
        if persistent:
            self._atomic_pickle(cache_path, {"version": FILE_CACHE_VERSION, "rows": rows})
        self._remember_file(key, rows)
        return rows

    def _load_parsed_translation_file(
        self, name: str, path: Path, persistent: bool
    ) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
        key = self._file_signature("translation", name, path)
        with self._lock:
            cached = self._file_memory.get(key)
            if cached is not None:
                self._file_memory.move_to_end(key)
                return cached
        cache_path = self.file_cache_dir / f"translation-{key}.pkl"
        if persistent:
            payload = self._read_pickle(cache_path)
            if isinstance(payload, dict) and payload.get("version") == FILE_CACHE_VERSION:
                rows = payload.get("rows")
                if isinstance(rows, dict):
                    self._remember_file(key, rows)
                    return rows

        mutable: dict[str, tuple[dict[str, str], dict[str, str]]] = {}
        for header, row in _iter_rows(path):
            if header:
                mapping = _as_mapping(header, row)
                tag = _first(mapping, _TAG_KEYS)
                translations = _split_values(_first(mapping, _TRANSLATION_KEYS))
                aliases = _split_values(_first(mapping, _ALIAS_KEYS))
            else:
                tag = _clean(row[0] if row else "")
                if len(row) >= 3:
                    translations = _split_values(row[1])
                    aliases = _split_values(row[2])
                else:
                    translations = _split_values(row[1] if len(row) > 1 else "")
                    aliases = []
            if not tag or tag.startswith("#"):
                continue
            canonical = canonical_tag(tag)
            translation_map, alias_map = mutable.setdefault(canonical, ({}, {}))
            for item in translations:
                translation_map.setdefault(item.casefold(), item)
            for item in aliases:
                alias_map.setdefault(item.casefold(), item)
        rows = {
            key_: (tuple(translations.values()), tuple(aliases.values()))
            for key_, (translations, aliases) in mutable.items()
        }
        if persistent:
            self._atomic_pickle(cache_path, {"version": FILE_CACHE_VERSION, "rows": rows})
        self._remember_file(key, rows)
        return rows
