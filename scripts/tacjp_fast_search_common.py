"""Fast persistent server-side search for TagComplete Neo Multi-CSV.

The legacy Multi-CSV path serialises the complete merged dataset to the browser and
builds a JavaScript index on first input.  This module keeps the merged index on the
server, persists compiled caches across WebUI restarts, and returns only the best
candidate pool for the current query.

The module intentionally has no Forge imports so it can be unit-tested directly.
"""

import bisect
import re
import unicodedata
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from scripts.jp_assist_core import (
        DataStore,
        infer_category_scheme,
        infer_insert_mode,
        infer_source_type,
        _ALIAS_KEYS, _CATEGORY_KEYS, _CATEGORY_SCHEME_KEYS, _COUNT_KEYS,
        _INSERT_MODE_KEYS, _SOURCE_TYPE_KEYS, _TAG_KEYS, _TRANSLATION_KEYS,
        _clean, _normalise_header, _first, _split_values, _to_category, _to_int,
        _tag_key as canonical_tag, _decode_tag_row, _decode_translation_row,
    )
except (ImportError, ModuleNotFoundError):
    from jp_assist_core import (  # type: ignore
        DataStore,
        infer_category_scheme,
        infer_insert_mode,
        infer_source_type,
        _ALIAS_KEYS, _CATEGORY_KEYS, _CATEGORY_SCHEME_KEYS, _COUNT_KEYS,
        _INSERT_MODE_KEYS, _SOURCE_TYPE_KEYS, _TAG_KEYS, _TRANSLATION_KEYS,
        _clean, _normalise_header, _first, _split_values, _to_category, _to_int,
        _tag_key as canonical_tag, _decode_tag_row, _decode_translation_row,
    )

_iter_rows = DataStore._iter_rows
_as_mapping = DataStore._as_mapping

CACHE_VERSION = 8
FILE_CACHE_VERSION = 2
PREFIX_MAX_LENGTH = 3
DEFAULT_RESULT_LIMIT = 250
MAX_RESULT_LIMIT = 2000
UINT32_MAX = (1 << 32) - 1


_SOURCE_TO_CODE = {"tag": 0, "natural_language": 1, "custom": 2}
_CODE_TO_SOURCE = ("tag", "natural_language", "custom")
_INSERT_TO_CODE = {"tag": 0, "phrase": 1, "word": 2, "raw": 3, "wildcard": 4}
_CODE_TO_INSERT = ("tag", "phrase", "word", "raw", "wildcard")
_SCHEME_TO_CODE = {
    "danbooru": 0,
    "e621": 1,
    "derpibooru": 2,
    "danbooru_e621_merged": 3,
    "natural_language": 4,
    "custom": 5,
}
_CODE_TO_SCHEME = (
    "danbooru",
    "e621",
    "derpibooru",
    "danbooru_e621_merged",
    "natural_language",
    "custom",
)


def build_compact_index(
    values_by_key: Mapping[str, Sequence[int]],
) -> dict[str, Any]:
    keys = tuple(sorted(values_by_key))
    offsets = array("I", [0])
    values = array("I")
    for key in keys:
        group = values_by_key[key]
        if len(values) + len(group) > UINT32_MAX:
            raise OverflowError("Compact index exceeds uint32 offset capacity")
        for value in group:
            row_id = int(value)
            if row_id < 0 or row_id > UINT32_MAX:
                raise OverflowError("Compact index row ID exceeds uint32 capacity")
            values.append(row_id)
        offsets.append(len(values))
    return {
        "keys": keys,
        "offsets": offsets,
        "values": values,
    }


def compact_index_get(
    index: Mapping[str, Any],
    key: str,
) -> Sequence[int] | None:
    keys = index["keys"]
    position = bisect.bisect_left(keys, key)
    if position >= len(keys) or keys[position] != key:
        return None
    offsets = index["offsets"]
    values = index["values"]
    return memoryview(values)[
        offsets[position] : offsets[position + 1]
    ]


def is_compact_index(index: object) -> bool:
    if not isinstance(index, Mapping):
        return False
    keys = index.get("keys")
    offsets = index.get("offsets")
    values = index.get("values")
    if (
        not isinstance(keys, tuple)
        or not isinstance(offsets, array)
        or offsets.typecode != "I"
        or not isinstance(values, array)
        or values.typecode != "I"
        or len(offsets) != len(keys) + 1
        or not offsets
        or offsets[0] != 0
        or offsets[-1] != len(values)
    ):
        return False
    return (
        all(
            keys[index - 1] < keys[index]
            for index in range(1, len(keys))
        )
        and all(
            offsets[index - 1] <= offsets[index]
            for index in range(1, len(offsets))
        )
    )


def normalize_search(
    value: Any,
    preserve_trailing_separator: bool = False,
) -> str:
    """Normalise search text while optionally keeping a final underscore."""

    text = unicodedata.normalize("NFKC", _clean(value)).casefold()
    trailing_separator = (
        preserve_trailing_separator and text.endswith("_")
    )
    text = text.replace("_", " ")
    normalised = re.sub(r"\s+", " ", text).strip()
    return f"{normalised} " if trailing_separator and normalised else normalised


def _dedupe_mapping(values: Iterable[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        item = _clean(value)
        if item:
            output.setdefault(item.casefold(), item)
    return output


def _safe_path(directory: Path, name: str) -> Path:
    raw = _clean(name).replace("\\", "/")
    if not raw or raw.casefold() in {"none", "all"}:
        raise ValueError("A concrete file name is required")
    candidate = (directory / raw).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError as exc:
        raise ValueError(f"Unsafe file path: {name}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _source_code(value: str) -> int:
    return _SOURCE_TO_CODE.get(value, _SOURCE_TO_CODE["tag"])


def _insert_code(value: str) -> int:
    return _INSERT_TO_CODE.get(value, _INSERT_TO_CODE["tag"])


def _scheme_code(value: str) -> int:
    return _SCHEME_TO_CODE.get(value, _SCHEME_TO_CODE["danbooru"])


def _decode_code(values: tuple[str, ...], code: int, fallback: str) -> str:
    return values[code] if 0 <= code < len(values) else fallback


@dataclass
class SearchRequest:
    query: str
    tag_files: Sequence[str]
    translation_files: Sequence[str] = ()
    prompt_mode: str = "Tag"
    candidate_sort_mode: str = "Count"
    context_natural: bool = False
    search_aliases: bool = True
    search_translations: bool = True
    substring_only: bool = False
    limit: int = DEFAULT_RESULT_LIMIT
    include_sources: bool = False
    persistent_cache: bool = True
    memory_entries: int = 4
    disk_entries: int = 8


class _MutableRecord:
    __slots__ = (
        "tag",
        "category",
        "count",
        "aliases",
        "translations",
        "source_type",
        "insert_mode",
        "category_scheme",
        "source_mask",
    )

    def __init__(
        self,
        tag: str,
        category: int | None,
        count: int | None,
        aliases: Iterable[str],
        translations: Iterable[str],
        source_type: str,
        insert_mode: str,
        category_scheme: str,
        source_mask: int,
    ) -> None:
        self.tag = tag
        self.category = category
        self.count = count
        self.aliases = _dedupe_mapping(aliases)
        self.translations = _dedupe_mapping(translations)
        self.source_type = source_type
        self.insert_mode = insert_mode
        self.category_scheme = category_scheme
        self.source_mask = source_mask

    def merge(
        self,
        *,
        category: int | None,
        count: int | None,
        aliases: Iterable[str],
        translations: Iterable[str],
        source_type: str,
        insert_mode: str,
        category_scheme: str,
        source_mask: int,
    ) -> None:
        for key, value in _dedupe_mapping(aliases).items():
            self.aliases.setdefault(key, value)
        for key, value in _dedupe_mapping(translations).items():
            self.translations.setdefault(key, value)
        self.source_mask |= source_mask
        if self.count is None:
            self.count = count
        elif count is not None:
            self.count = max(self.count, count)
        if self.category is None and category is not None:
            self.category = category
            self.category_scheme = category_scheme
        if self.source_type == "natural_language" and source_type == "tag":
            self.source_type = "tag"
            self.insert_mode = insert_mode
            if category is not None:
                self.category = category
                self.category_scheme = category_scheme
