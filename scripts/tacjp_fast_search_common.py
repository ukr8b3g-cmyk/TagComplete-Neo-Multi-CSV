"""Fast persistent server-side search for TagComplete Neo Multi-CSV.

The legacy Multi-CSV path serialises the complete merged dataset to the browser and
builds a JavaScript index on first input.  This module keeps the merged index on the
server, persists compiled caches across WebUI restarts, and returns only the best
candidate pool for the current query.

The module intentionally has no Forge imports so it can be unit-tested directly.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from scripts.jp_assist_core import (
        DataStore,
        infer_category_scheme,
        infer_insert_mode,
        infer_source_type,
        DEFAULT_UNDERSCORE_EXCLUSIONS,
    )
except (ImportError, ModuleNotFoundError):
    from jp_assist_core import (  # type: ignore
        DataStore,
        infer_category_scheme,
        infer_insert_mode,
        infer_source_type,
        DEFAULT_UNDERSCORE_EXCLUSIONS,
    )

CACHE_VERSION = 5
FILE_CACHE_VERSION = 2
PREFIX_MAX_LENGTH = 3
DEFAULT_RESULT_LIMIT = 250
MAX_RESULT_LIMIT = 2000

_TAG_KEYS = ("tag", "name", "english", "token", "value")
_CATEGORY_KEYS = ("category", "cat", "type_id")
_COUNT_KEYS = ("count", "post_count", "posts", "priority", "weight", "score")
_ALIAS_KEYS = ("aliases", "alias", "alternate_names", "synonyms")
_TRANSLATION_KEYS = (
    "ja",
    "jp",
    "japanese",
    "translation",
    "translations",
    "translated",
    "label",
    "display",
)
_SOURCE_TYPE_KEYS = ("source_type", "source", "kind", "vocabulary_type")
_INSERT_MODE_KEYS = ("insert_mode", "insertion", "separator_mode", "mode")
_CATEGORY_SCHEME_KEYS = ("category_scheme", "scheme", "booru")

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

_CANONICAL_PROTECTED_PREFIXES = ("score_", "rating_", "source_")
_CANONICAL_PROTECTED_EXACT = frozenset(
    str(value).casefold()
    for value in DEFAULT_UNDERSCORE_EXCLUSIONS
    if "*" not in str(value) and "?" not in str(value)
)


def _canonical_underscore_protected(text: str) -> bool:
    if text.startswith("__") and text.endswith("__"):
        return True
    return text in _CANONICAL_PROTECTED_EXACT or text.startswith(
        _CANONICAL_PROTECTED_PREFIXES
    )


def _clean(value: Any) -> str:
    return str(value or "").strip().lstrip("\ufeff")


def _normalise_header(value: Any) -> str:
    return re.sub(r"[\s\-]+", "_", _clean(value).lower())


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _split_values(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,;\n\r]+", text) if item.strip()]


def _to_int(value: Any, default: int = 0) -> int:
    text = _clean(value).replace(",", "")
    if not text:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _to_category(value: Any) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def normalize_search(value: Any) -> str:
    """Normalise search text while keeping output text untouched."""

    text = unicodedata.normalize("NFKC", _clean(value)).casefold()
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def canonical_tag(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean(value)).casefold()
    if not text:
        return ""
    if not _canonical_underscore_protected(text):
        text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_mapping(values: Iterable[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        item = _clean(value)
        if item:
            output.setdefault(item.casefold(), item)
    return output


def _iter_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        first_row: list[str] | None = None
        for row in reader:
            if row and any(_clean(value) for value in row):
                first_row = row
                break
        if first_row is None:
            return
        candidate_header = [_normalise_header(value) for value in first_row]
        header = (
            candidate_header
            if candidate_header and candidate_header[0] in _TAG_KEYS
            else None
        )
        if header is None:
            yield None, first_row
        for row in reader:
            if row and any(_clean(value) for value in row):
                yield header, row


def _as_mapping(header: Sequence[str], row: Sequence[str]) -> dict[str, str]:
    return {
        header[index]: row[index] if index < len(row) else ""
        for index in range(len(header))
    }


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


@dataclass(slots=True)
class SearchRequest:
    query: str
    tag_files: Sequence[str]
    translation_files: Sequence[str] = ()
    prompt_mode: str = "Tag"
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
        count: int,
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
        count: int,
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
        if count > self.count:
            self.count = count
        if self.category is None and category is not None:
            self.category = category
            self.category_scheme = category_scheme
        if self.source_type == "natural_language" and source_type == "tag":
            self.source_type = "tag"
            self.insert_mode = insert_mode
            if category is not None:
                self.category = category
                self.category_scheme = category_scheme
