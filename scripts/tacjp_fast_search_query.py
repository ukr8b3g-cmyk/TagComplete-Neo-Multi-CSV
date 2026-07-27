"""Query and ranking logic for Multi-CSV server search."""

from __future__ import annotations

import heapq
import re
import time
from typing import Any, Sequence

try:
    from scripts.tacjp_fast_search_common import (
        DEFAULT_RESULT_LIMIT,
        MAX_RESULT_LIMIT,
        PREFIX_MAX_LENGTH,
        SearchRequest,
        _CODE_TO_INSERT,
        _CODE_TO_SCHEME,
        _CODE_TO_SOURCE,
        _decode_code,
        normalize_search,
    )
except (ImportError, ModuleNotFoundError):
    from tacjp_fast_search_common import (  # type: ignore
        DEFAULT_RESULT_LIMIT,
        MAX_RESULT_LIMIT,
        PREFIX_MAX_LENGTH,
        SearchRequest,
        _CODE_TO_INSERT,
        _CODE_TO_SCHEME,
        _CODE_TO_SOURCE,
        _decode_code,
        normalize_search,
    )


class FastSearchQueryMixin:
    @staticmethod
    def _field_score(
        value: str,
        query: str,
        substring_only: bool,
    ) -> int:
        if not query:
            return 99
        if substring_only:
            return 30 if query in value else 99
        if value == query:
            return 0
        if value.startswith(query):
            return 10
        words = [
            part
            for part in re.split(r"[^\w]+", value, flags=re.UNICODE)
            if part
        ]
        if any(word.startswith(query) for word in words):
            return 20
        return 30 if query in value else 99

    @staticmethod
    def _source_penalty(
        prompt_mode: str,
        source_type_code: int,
        context_natural: bool,
    ) -> int:
        source = _decode_code(
            _CODE_TO_SOURCE,
            source_type_code,
            "tag",
        )
        if prompt_mode == "Natural Language":
            return 0 if source == "natural_language" else 40
        if prompt_mode == "Tag":
            return 40 if source == "natural_language" else 0
        if prompt_mode == "Hybrid":
            if context_natural:
                return 0 if source == "natural_language" else 12
            return 12 if source == "natural_language" else 0
        return 0

    @staticmethod
    def _candidate_ids(
        index: dict[str, Any],
        query: str,
        substring_only: bool,
    ) -> tuple[Sequence[int], bool]:
        rows = index["rows"]
        if not query:
            return range(len(rows)), True

        # Non-ASCII text uses a complete substring n-gram index, so Japanese
        # searches do not fall back to scanning every tag on each keystroke.
        compact_query = "".join(
            char for char in query if not char.isspace()
        )
        if compact_query and any(
            ord(char) > 127 for char in compact_query
        ):
            width = min(3, len(compact_query))
            gram_keys = [
                f"u{width}:{compact_query[start:start + width]}"
                for start in range(
                    0,
                    len(compact_query) - width + 1,
                )
            ]
            gram_index = index.get("unicode_gram_index", {})
            subsets = [gram_index.get(key) for key in gram_keys]
            if any(subset is None for subset in subsets):
                return (), True
            ordered = sorted(subsets, key=len)
            if not ordered:
                return (), True
            intersection = {int(value) for value in ordered[0]}
            for subset in ordered[1:]:
                intersection.intersection_update(
                    int(value) for value in subset
                )
                if not intersection:
                    break
            return tuple(intersection), True

        # Explicit substring searches use the pre-normalised blob prefilter.
        if substring_only:
            return (), False
        words = [
            part
            for part in re.split(r"[^\w]+", query, flags=re.UNICODE)
            if part
        ]
        if not words:
            return (), False
        prefix_index = index["prefix_index"]
        subsets = []
        for word in words:
            length = min(PREFIX_MAX_LENGTH, len(word))
            subset = prefix_index.get(
                f"{length}:{word[:length]}"
            )
            if subset is not None:
                subsets.append(subset)
        if not subsets:
            return (), False
        ordered = sorted(subsets, key=len)
        intersection = {int(value) for value in ordered[0]}
        for subset in ordered[1:]:
            intersection.intersection_update(
                int(value) for value in subset
            )
            if not intersection:
                break
        if intersection:
            return tuple(intersection), False
        return (), False

    def search(self, request: SearchRequest) -> dict[str, Any]:
        started = time.perf_counter()
        query = normalize_search(request.query)
        limit = max(
            1,
            min(
                MAX_RESULT_LIMIT,
                int(request.limit or DEFAULT_RESULT_LIMIT),
            ),
        )
        tag_items, translation_items = self._resolve_files(
            request.tag_files,
            request.translation_files,
        )
        if not tag_items or not query:
            return {
                "results": [],
                "count": 0,
                "cache": "none",
                "search_ms": 0.0,
            }

        index, cache_state = self._load_or_build(
            tag_items,
            translation_items,
            persistent=bool(request.persistent_cache),
            memory_entries=request.memory_entries,
            disk_entries=request.disk_entries,
        )
        rows = index["rows"]
        fields = index.get("fields")
        field_groups = index.get("field_groups")
        blobs = index["search_blobs"]
        candidate_ids, candidate_set_is_complete = self._candidate_ids(
            index,
            query,
            request.substring_only,
        )

        scored: list[tuple[int, int, str, int]] = []
        seen_ids: set[int] = set()

        def consider(row_id: int) -> None:
            if row_id in seen_ids:
                return
            seen_ids.add(row_id)
            if field_groups is not None:
                (
                    tag_field,
                    alias_fields,
                    translation_fields,
                ) = field_groups[row_id]
                selected_fields = [tag_field]
                if request.search_aliases:
                    selected_fields.extend(alias_fields)
                if request.search_translations:
                    selected_fields.extend(translation_fields)
                field_values = selected_fields
            else:
                field_values = (
                    fields[row_id]
                    if fields is not None
                    else (normalize_search(rows[row_id][0]),)
                )
            best = min(
                (
                    self._field_score(
                        value,
                        query,
                        request.substring_only,
                    )
                    for value in field_values
                ),
                default=99,
            )
            if best >= 99:
                return
            row = rows[row_id]
            score = best + self._source_penalty(
                request.prompt_mode,
                int(row[5]),
                request.context_natural,
            )
            scored.append(
                (
                    score,
                    -int(row[2] or 0),
                    str(row[0]).casefold(),
                    row_id,
                )
            )

        for row_id in candidate_ids:
            consider(int(row_id))

        # Prefix indexing is deliberately compact. If it produced fewer than
        # the requested pool, complete substring coverage with a fast C-level
        # `in` prefilter over pre-normalised blobs. This is also important for
        # English infix searches such as `trait` matching `portrait`.
        if (
            not candidate_set_is_complete
            and len(scored) < limit
            and len(seen_ids) < len(rows)
        ):
            for row_id, blob_group in enumerate(blobs):
                if row_id in seen_ids:
                    continue
                if isinstance(blob_group, tuple):
                    tag_blob, alias_blob, translation_blob = blob_group
                    searchable_blob = tag_blob
                    if request.search_aliases:
                        searchable_blob += "\x1f" + alias_blob
                    if request.search_translations:
                        searchable_blob += "\x1f" + translation_blob
                else:
                    searchable_blob = blob_group
                if query not in searchable_blob:
                    continue
                consider(row_id)

        if len(scored) > limit:
            selected = heapq.nsmallest(limit, scored)
        else:
            scored.sort()
            selected = scored

        output: list[list[Any]] = []
        source_names: tuple[str, ...] = index["source_names"]
        for score, _negative_count, _name, row_id in selected:
            row = rows[row_id]
            item: list[Any] = [
                row[0],
                row[1],
                row[2],
                row[3] if request.search_aliases else "",
                row[4] if request.search_translations else "",
                _decode_code(
                    _CODE_TO_SOURCE,
                    int(row[5]),
                    "tag",
                ),
                _decode_code(
                    _CODE_TO_INSERT,
                    int(row[6]),
                    "tag",
                ),
                _decode_code(
                    _CODE_TO_SCHEME,
                    int(row[7]),
                    "danbooru",
                ),
            ]
            if request.include_sources:
                mask = int(row[8])
                item.append(
                    [
                        name
                        for bit, name in enumerate(source_names)
                        if mask & (1 << bit)
                    ]
                )
            else:
                item.append([])
            item.append(score)
            output.append(item)

        return {
            "results": output,
            "count": len(output),
            "total": len(rows),
            "cache": cache_state,
            "build_ms": index.get("build_ms", 0.0),
            "search_ms": round(
                (time.perf_counter() - started) * 1000,
                2,
            ),
            "signature": str(index.get("signature", ""))[:12],
        }

    def clear(self, *, disk: bool = True) -> dict[str, int]:
        with self._lock:
            memory_count = len(self._memory) + len(self._file_memory)
            self._memory.clear()
            self._file_memory.clear()
        deleted = 0
        if disk:
            for folder in (
                self.index_cache_dir,
                self.file_cache_dir,
            ):
                for path in folder.glob("*.pkl"):
                    try:
                        path.unlink()
                        deleted += 1
                    except OSError:
                        pass
        return {
            "memory_entries": memory_count,
            "disk_files": deleted,
        }
