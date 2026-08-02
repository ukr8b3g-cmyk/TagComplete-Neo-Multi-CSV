"""Compiled combination indexes and single-flight cache loading."""

from __future__ import annotations

import os
import re
import threading
import time
from array import array
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts.tacjp_fast_search_common import (
        CACHE_VERSION,
        PREFIX_MAX_LENGTH,
        _MutableRecord,
        build_compact_index,
        _insert_code,
        is_compact_index,
        _scheme_code,
        _source_code,
        canonical_tag,
        normalize_search,
    )
except (ImportError, ModuleNotFoundError):
    from tacjp_fast_search_common import (  # type: ignore
        CACHE_VERSION,
        PREFIX_MAX_LENGTH,
        _MutableRecord,
        build_compact_index,
        _insert_code,
        is_compact_index,
        _scheme_code,
        _source_code,
        canonical_tag,
        normalize_search,
    )


class FastSearchIndexMixin:
    @staticmethod
    def _prefix_keys(fields: Sequence[str]) -> set[str]:
        keys: set[str] = set()
        for field in fields:
            if not field:
                continue
            candidates: list[str] = []
            if field.isascii():
                candidates.append(field)
            candidates.extend(
                part
                for part in re.split(r"[^\w]+", field, flags=re.UNICODE)
                if part and part.isascii()
            )
            for value in candidates:
                for length in range(
                    1,
                    min(PREFIX_MAX_LENGTH, len(value)) + 1,
                ):
                    keys.add(f"{length}:{value[:length]}")
        return keys

    def _compile(
        self,
        signature: str,
        manifest: str,
        tag_items: Sequence[tuple[str, Path]],
        translation_items: Sequence[tuple[str, Path]],
        persistent: bool,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        source_names = tuple(
            [name for name, _ in tag_items]
            + [name for name, _ in translation_items]
        )
        merged: dict[str, _MutableRecord] = {}
        order: list[str] = []

        for source_index, (name, path) in enumerate(tag_items):
            source_mask = 1 << source_index
            for row in self._load_parsed_tag_file(
                name,
                path,
                persistent,
            ):
                (
                    tag,
                    category,
                    count,
                    aliases,
                    translations,
                    source_type,
                    insert_mode,
                    scheme,
                ) = row
                key = canonical_tag(tag)
                if not key:
                    continue
                existing = merged.get(key)
                if existing is None:
                    merged[key] = _MutableRecord(
                        tag,
                        category,
                        count,
                        aliases,
                        translations,
                        source_type,
                        insert_mode,
                        scheme,
                        source_mask,
                    )
                    order.append(key)
                else:
                    existing.merge(
                        category=category,
                        count=count,
                        aliases=aliases,
                        translations=translations,
                        source_type=source_type,
                        insert_mode=insert_mode,
                        category_scheme=scheme,
                        source_mask=source_mask,
                    )

        translation_offset = len(tag_items)
        for relative_index, (name, path) in enumerate(translation_items):
            source_mask = 1 << (translation_offset + relative_index)
            values = self._load_parsed_translation_file(
                name,
                path,
                persistent,
            )
            for key, (translations, aliases) in values.items():
                record = merged.get(key)
                if record is None:
                    continue
                record.merge(
                    category=None,
                    count=None,
                    aliases=aliases,
                    translations=translations,
                    source_type=record.source_type,
                    insert_mode=record.insert_mode,
                    category_scheme=record.category_scheme,
                    source_mask=source_mask,
                )

        rows: list[tuple[Any, ...]] = []
        field_groups: list[
            tuple[str, tuple[str, ...], tuple[str, ...]]
        ] = []
        search_blobs: list[tuple[str, str, str]] = []
        prefix_lists: dict[str, list[int]] = {}
        unicode_gram_lists: dict[str, list[int]] = {}
        ascii_trigram_lists: dict[str, list[int]] = {}
        for index, key in enumerate(order):
            record = merged[key]
            aliases = tuple(record.aliases.values())
            translations = tuple(record.translations.values())
            row = (
                record.tag,
                record.category,
                record.count,
                ",".join(aliases),
                ", ".join(translations),
                _source_code(record.source_type),
                _insert_code(record.insert_mode),
                _scheme_code(record.category_scheme),
                record.source_mask,
            )
            tag_field = normalize_search(record.tag)
            alias_fields = tuple(
                value
                for value in (
                    normalize_search(item) for item in aliases
                )
                if value
            )
            translation_fields = tuple(
                value
                for value in (
                    normalize_search(item) for item in translations
                )
                if value
            )
            normalised_fields = tuple(
                value
                for value in (
                    tag_field,
                    *alias_fields,
                    *translation_fields,
                )
                if value
            )
            rows.append(row)
            field_groups.append(
                (tag_field, alias_fields, translation_fields)
            )
            search_blobs.append(
                (
                    tag_field,
                    "\x1f".join(alias_fields),
                    "\x1f".join(translation_fields),
                )
            )
            for prefix_key in self._prefix_keys(normalised_fields):
                prefix_lists.setdefault(prefix_key, []).append(index)

            # Japanese and other non-ASCII translations often need substring
            # matching (`髪` should match `長髪`). Index only non-ASCII fields
            # with 1–3 character grams. This keeps memory far below a universal
            # n-gram index while making translated search fast.
            unicode_keys: set[str] = set()
            for field in normalised_fields:
                if not any(ord(char) > 127 for char in field):
                    continue
                compact_field = "".join(
                    char for char in field if not char.isspace()
                )
                for width in range(1, 4):
                    if len(compact_field) < width:
                        break
                    for start in range(
                        0,
                        len(compact_field) - width + 1,
                    ):
                        unicode_keys.add(
                            f"u{width}:"
                            f"{compact_field[start:start + width]}"
                        )
            for gram_key in unicode_keys:
                unicode_gram_lists.setdefault(gram_key, []).append(index)

            # A complete ASCII substring index avoids scanning every row in
            # Count mode before applying the result limit. Final field scoring
            # still verifies matches, so these postings are only a prefilter.
            ascii_trigram_keys: set[str] = set()
            for field in normalised_fields:
                if len(field) < 3:
                    continue
                for start in range(0, len(field) - 2):
                    gram = field[start:start + 3]
                    if gram.isascii():
                        ascii_trigram_keys.add(f"a3:{gram}")
            for gram_key in ascii_trigram_keys:
                ascii_trigram_lists.setdefault(gram_key, []).append(index)

        prefix_index = build_compact_index(prefix_lists)
        unicode_gram_index = build_compact_index(
            unicode_gram_lists,
        )
        ascii_trigram_index = build_compact_index(
            ascii_trigram_lists,
        )
        tag_source_code = _source_code("tag")
        count_order = array(
            "I",
            sorted(
                (
                    row_id
                    for row_id, row in enumerate(rows)
                    if int(row[5]) == tag_source_code
                    and isinstance(row[2], int)
                    and row[2] >= 0
                ),
                key=lambda row_id: (-int(rows[row_id][2]), row_id),
            ),
        )
        counted_ids = set(count_order)
        non_count_ids = array(
            "I",
            (
                row_id
                for row_id in range(len(rows))
                if row_id not in counted_ids
            ),
        )
        self.build_count += 1
        return {
            "version": CACHE_VERSION,
            "signature": signature,
            "manifest": manifest,
            "source_names": source_names,
            "rows": rows,
            "field_groups": field_groups,
            "search_blobs": search_blobs,
            "prefix_index": prefix_index,
            "unicode_gram_index": unicode_gram_index,
            "ascii_trigram_index": ascii_trigram_index,
            "count_order": count_order,
            "non_count_ids": non_count_ids,
            "build_ms": round(
                (time.perf_counter() - started) * 1000,
                2,
            ),
            "created": time.time(),
        }

    def _remember_index(
        self,
        signature: str,
        index: dict[str, Any],
        max_entries: int,
    ) -> None:
        max_entries = max(1, min(12, int(max_entries or 1)))
        with self._lock:
            self._memory[signature] = index
            self._memory.move_to_end(signature)
            while len(self._memory) > max_entries:
                self._memory.popitem(last=False)

    def _prune_disk(self, max_entries: int) -> None:
        if not self._disk_cache_available:
            return
        max_entries = max(1, min(32, int(max_entries or 1)))
        try:
            files = sorted(
                self.index_cache_dir.glob("*.pkl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return
        for path in files[max_entries:]:
            try:
                path.unlink()
            except OSError:
                pass

    def _load_or_build(
        self,
        tag_items: Sequence[tuple[str, Path]],
        translation_items: Sequence[tuple[str, Path]],
        *,
        persistent: bool,
        memory_entries: int,
        disk_entries: int,
    ) -> tuple[dict[str, Any], str, dict[str, float]]:
        persistent = bool(
            persistent and self._disk_cache_available
        )
        signature, manifest = self._signature(
            tag_items,
            translation_items,
        )
        with self._lock:
            cached = self._memory.get(signature)
            if cached is not None:
                self._memory.move_to_end(signature)
                return cached, "memory", {"restore_ms": 0.0}
            event = self._building.get(signature)
            if event is None:
                event = threading.Event()
                self._building[signature] = event
                builder = True
            else:
                builder = False

        if not builder:
            if not event.wait(timeout=300):
                raise TimeoutError(
                    "Timed out waiting for the Multi-CSV search index"
                )
            with self._lock:
                error = self._build_errors.pop(signature, None)
                cached = self._memory.get(signature)
                if cached is not None:
                    self._memory.move_to_end(signature)
                    return cached, "memory-wait", {"restore_ms": 0.0}
            if error is not None:
                raise RuntimeError(
                    f"Search index build failed: {error}"
                ) from error
            # The builder may have used a smaller LRU and evicted immediately.
            return self._load_or_build(
                tag_items,
                translation_items,
                persistent=persistent,
                memory_entries=memory_entries,
                disk_entries=disk_entries,
            )

        try:
            cache_path = self.index_cache_dir / f"{signature}.pkl"
            if persistent:
                restore_started = time.perf_counter()
                payload = self._read_pickle(cache_path)
                if (
                    isinstance(payload, dict)
                    and payload.get("version") == CACHE_VERSION
                    and payload.get("signature") == signature
                    and payload.get("manifest") == manifest
                    and is_compact_index(
                        payload.get("prefix_index")
                    )
                    and is_compact_index(
                        payload.get("unicode_gram_index")
                    )
                    and is_compact_index(
                        payload.get("ascii_trigram_index")
                    )
                    and isinstance(payload.get("count_order"), array)
                    and isinstance(payload.get("non_count_ids"), array)
                ):
                    self._remember_index(
                        signature,
                        payload,
                        memory_entries,
                    )
                    with self._lock:
                        self._build_errors.pop(signature, None)
                    restore_ms = round(
                        (time.perf_counter() - restore_started) * 1000,
                        2,
                    )
                    try:
                        os.utime(cache_path, None)
                    except OSError:
                        pass
                    return (
                        payload,
                        "disk",
                        {"restore_ms": restore_ms},
                    )

            index = self._compile(
                signature,
                manifest,
                tag_items,
                translation_items,
                persistent,
            )
            if persistent:
                self._try_write_pickle(cache_path, index)
                self._prune_disk(disk_entries)
                self._prune_file_disk(
                    max(32, int(disk_entries or 1) * 8)
                )
            self._remember_index(
                signature,
                index,
                memory_entries,
            )
            with self._lock:
                self._build_errors.pop(signature, None)
            return index, "build", {"restore_ms": 0.0}
        except BaseException as exc:
            with self._lock:
                self._build_errors[signature] = exc
            raise
        finally:
            with self._lock:
                signal = self._building.pop(signature, None)
                if signal is not None:
                    signal.set()
