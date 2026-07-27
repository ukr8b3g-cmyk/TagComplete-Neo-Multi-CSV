"""Data, preset, and update helpers for TagComplete Neo Multi-CSV.

The module intentionally avoids WebUI imports so the merge and preset logic can be
unit-tested outside Forge. WebUI integration lives in tag_autocomplete_helper.py.
"""

from __future__ import annotations

import csv
import fnmatch
import json
import os
import re
import shutil
import tempfile
import threading
import unicodedata
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_UNDERSCORE_EXCLUSIONS = (
    "score_*",
    "rating_*",
    "source_*",
    "^_^",
    ">_<",
    "@_@",
    "=_=",
    "o_o",
    "o_x",
    "x_x",
    "t_t",
    "u_u",
    "|_|",
    "||_||",
    "0_0",
    "3_3",
    "6_9",
    "._.",
    "+_+",
    "+_-",
    "(o)_(o)",
    "<o>_<o>",
    "<|>_<|>",
    ">_o",
)

DEFAULT_REMOTE_URL = (
    "https://huggingface.co/datasets/SpadeA/danbooru-tag-csv/resolve/main/"
    "danbooru_tags.csv?download=true"
)

VALID_PROMPT_MODES = {"Tag", "Hybrid", "Natural Language", "Custom"}
VALID_INSERT_MODES = {"tag", "phrase", "word", "raw", "wildcard"}

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

_NATURAL_FILE_HINTS = (
    "natural_language",
    "natural-language",
    "naturallanguage",
    "englishdictionary",
    "english_dictionary",
    "prompt_words",
    "prompt_phrases",
    "phrases",
    "sentence",
    "krea",
    "flux",
    "qwen",
    "z-image",
    "zimage",
)

_CUSTOM_FILE_HINTS = ("custom", "user", "personal", "extra")


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
    # Commas and semicolons are the established CSV conventions. Newlines are
    # also accepted for hand-authored translation files.
    return [item.strip() for item in re.split(r"[,;\n\r]+", text) if item.strip()]


def _dedupe(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


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


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _clean(value).casefold()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", ""}:
        return False
    return default


def infer_source_type(filename: str, explicit: str = "") -> str:
    value = _clean(explicit).lower().replace("-", "_").replace(" ", "_")
    if value in {"natural", "natural_language", "nl", "word", "phrase"}:
        return "natural_language"
    if value in {"custom", "user", "extra"}:
        return "custom"
    if value in {"tag", "booru", "danbooru", "e621"}:
        return "tag"

    lower = filename.lower()
    if any(hint in lower for hint in _NATURAL_FILE_HINTS):
        return "natural_language"
    if any(hint in lower for hint in _CUSTOM_FILE_HINTS):
        return "custom"
    return "tag"


def infer_category_scheme(filename: str, explicit: str = "") -> str:
    value = _clean(explicit).lower()
    if value:
        return value
    lower = filename.lower()
    if any(hint in lower for hint in _NATURAL_FILE_HINTS):
        return "natural_language"
    if "danbooru_e621" in lower or ("danbooru" in lower and "e621" in lower):
        return "danbooru_e621_merged"
    if "e621" in lower:
        return "e621"
    if "derpibooru" in lower:
        return "derpibooru"
    if "danbooru" in lower or "illustrious" in lower or "pony" in lower:
        return "danbooru"
    return "danbooru"


def infer_insert_mode(tag: str, source_type: str, explicit: str = "") -> str:
    value = _clean(explicit).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "nl": "phrase",
        "natural_language": "phrase",
        "no_separator": "raw",
        "literal": "raw",
    }
    value = aliases.get(value, value)
    if value in VALID_INSERT_MODES:
        return value
    if tag.startswith("__") and tag.endswith("__"):
        return "wildcard"
    if source_type == "natural_language":
        normalised = tag.replace("_", " ").strip()
        return "phrase" if re.search(r"\s", normalised) else "word"
    return "tag"


def _tag_key(value: Any) -> str:
    """Canonical key for tag/translation matching without changing output text."""
    text = unicodedata.normalize("NFKC", _clean(value)).casefold()
    if not text:
        return ""
    if not is_underscore_protected(text, DEFAULT_UNDERSCORE_EXCLUSIONS):
        text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _string_list(value: Any) -> list[str]:
    """Coerce preset/API list values without splitting a filename into characters."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "None":
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return _dedupe(str(item) for item in parsed)
        return [text]
    if isinstance(value, Sequence):
        return _dedupe(str(item) for item in value)
    return [_clean(value)] if _clean(value) else []


def parse_patterns(value: str | Sequence[str]) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[,\n\r]+", value)
    else:
        parts = [str(item) for item in value]
    return _dedupe(item.strip() for item in parts if item and item.strip())


def is_underscore_protected(tag: str, patterns: str | Sequence[str]) -> bool:
    text = _clean(tag)
    if text.startswith("__") and text.endswith("__"):
        return True
    return any(fnmatch.fnmatchcase(text.casefold(), pattern.casefold()) for pattern in parse_patterns(patterns))


@dataclass(slots=True)
class TagRecord:
    tag: str
    category: int | None = None
    count: int = 0
    aliases: list[str] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    source_type: str = "tag"
    insert_mode: str = "tag"
    category_scheme: str = "danbooru"
    source_files: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    priority: int = 0

    def compact(self) -> list[Any]:
        return [
            self.tag,
            self.category,
            self.count,
            ",".join(self.aliases),
            ", ".join(self.translations),
            self.source_type,
            self.insert_mode,
            self.category_scheme,
            self.source_files,
            self.source_types,
        ]


@dataclass(slots=True)
class FileInfo:
    name: str
    size: int
    modified: float
    source_type: str = "tag"
    category_scheme: str = "danbooru"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataStore:
    """Reads and merges tag/translation CSV files with mtime-aware caching."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.tag_dir = self.root / "tag_files"
        self.translation_dir = self.root / "translation_files"
        self.chant_dir = self.root / "chants"
        self.config_dir = self.root / "config"
        self.cache_dir = self.root / "cache"
        for directory in (
            self.tag_dir,
            self.translation_dir,
            self.chant_dir,
            self.config_dir,
            self.cache_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[list[Any]]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _safe_relative(directory: Path, name: str) -> Path:
        raw = _clean(name).replace("\\", "/")
        if not raw or raw.lower() in {"none", "all"}:
            raise ValueError("A concrete file name is required")
        candidate = (directory / raw).resolve()
        try:
            candidate.relative_to(directory.resolve())
        except ValueError as exc:
            raise ValueError(f"Unsafe file path: {name}") from exc
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    @staticmethod
    def _scan(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
        allowed = {suffix.casefold() for suffix in suffixes}
        files = (
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in allowed
        )
        return sorted(files, key=lambda path: path.as_posix().casefold())

    def list_tag_files(self) -> list[FileInfo]:
        output: list[FileInfo] = []
        for path in self._scan(self.tag_dir, (".csv",)):
            stat = path.stat()
            name = path.relative_to(self.tag_dir).as_posix()
            output.append(
                FileInfo(
                    name=name,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    source_type=infer_source_type(name),
                    category_scheme=infer_category_scheme(name),
                )
            )
        return output

    def list_translation_files(self) -> list[FileInfo]:
        output: list[FileInfo] = []
        for path in self._scan(self.translation_dir, (".csv",)):
            stat = path.stat()
            name = path.relative_to(self.translation_dir).as_posix()
            output.append(FileInfo(name=name, size=stat.st_size, modified=stat.st_mtime))
        return output

    def list_chant_files(self) -> list[str]:
        return [path.relative_to(self.chant_dir).as_posix() for path in self._scan(self.chant_dir, (".json",))]

    def _signature(self, paths: Sequence[Path], options: Mapping[str, Any]) -> str:
        parts = [json.dumps(options, sort_keys=True, ensure_ascii=False)]
        for path in paths:
            stat = path.stat()
            parts.append(f"{path.as_posix()}|{stat.st_size}|{stat.st_mtime_ns}")
        return "\n".join(parts)

    @staticmethod
    def _iter_rows(path: Path):
        """Yield ``(header, row)`` pairs without loading a large CSV into memory."""
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
            header = candidate_header if candidate_header and candidate_header[0] in _TAG_KEYS else None
            if header is None:
                yield None, first_row
            for row in reader:
                if row and any(_clean(value) for value in row):
                    yield header, row

    @staticmethod
    def _as_mapping(header: Sequence[str], row: Sequence[str]) -> dict[str, str]:
        return {header[index]: row[index] if index < len(row) else "" for index in range(len(header))}

    def _read_tag_file(self, path: Path, display_name: str, priority: int) -> Iterable[TagRecord]:
        """Yield one file's records without retaining a second full CSV copy."""

        file_source_type = infer_source_type(display_name)
        file_scheme = infer_category_scheme(display_name)

        for header, row in self._iter_rows(path):
            if header:
                mapping = self._as_mapping(header, row)
                tag = _first(mapping, _TAG_KEYS)
                category = _to_category(_first(mapping, _CATEGORY_KEYS))
                count = _to_int(_first(mapping, _COUNT_KEYS))
                aliases = _split_values(_first(mapping, _ALIAS_KEYS))
                translations = _split_values(_first(mapping, _TRANSLATION_KEYS))
                source_type = infer_source_type(display_name, _first(mapping, _SOURCE_TYPE_KEYS))
                scheme = infer_category_scheme(display_name, _first(mapping, _CATEGORY_SCHEME_KEYS))
                insert_mode = infer_insert_mode(tag, source_type, _first(mapping, _INSERT_MODE_KEYS))
            else:
                tag = _clean(row[0] if row else "")
                category = _to_category(row[1] if len(row) > 1 else "")
                count = _to_int(row[2] if len(row) > 2 else "")
                aliases = _split_values(row[3] if len(row) > 3 else "")
                translations = _split_values(row[4] if len(row) > 4 else "")
                source_type = file_source_type
                scheme = file_scheme
                insert_mode = infer_insert_mode(tag, source_type)
            if not tag or tag.startswith("#"):
                continue
            yield TagRecord(
                tag=tag,
                category=category,
                count=count,
                aliases=_dedupe(aliases),
                translations=_dedupe(translations),
                source_type=source_type,
                insert_mode=insert_mode,
                category_scheme=scheme,
                source_files=[display_name],
                source_types=[source_type],
                priority=priority,
            )

    def _read_translation_file(self, path: Path) -> dict[str, dict[str, list[str]]]:
        output: dict[str, dict[str, list[str]]] = {}
        for header, row in self._iter_rows(path):
            if header:
                mapping = self._as_mapping(header, row)
                tag = _first(mapping, _TAG_KEYS)
                translations = _split_values(_first(mapping, _TRANSLATION_KEYS))
                aliases = _split_values(_first(mapping, _ALIAS_KEYS))
                # JP Assist commonly stores visible Japanese in ``ja`` and all
                # searchable forms in ``aliases``. A generic ``translation``
                # column follows the same path.
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
            key = _tag_key(tag)
            entry = output.setdefault(key, {"translations": [], "aliases": []})
            entry["translations"] = _dedupe([*entry["translations"], *translations])
            entry["aliases"] = _dedupe([*entry["aliases"], *aliases])
        return output

    @staticmethod
    def _merge_record(existing: TagRecord, incoming: TagRecord) -> None:
        existing.aliases = _dedupe([*existing.aliases, *incoming.aliases])
        existing.translations = _dedupe([*existing.translations, *incoming.translations])
        existing.source_files = _dedupe([*existing.source_files, *incoming.source_files])
        existing.source_types = _dedupe([*existing.source_types, *incoming.source_types])
        existing.count = max(existing.count, incoming.count)

        # Selection order is priority order. Preserve the first meaningful
        # category/scheme, while always preferring a Booru category over an
        # uncategorised natural-language duplicate.
        if existing.category is None and incoming.category is not None:
            existing.category = incoming.category
            existing.category_scheme = incoming.category_scheme
        if existing.source_type == "natural_language" and incoming.source_type == "tag":
            existing.source_type = "tag"
            existing.insert_mode = incoming.insert_mode
            if incoming.category is not None:
                existing.category = incoming.category
                existing.category_scheme = incoming.category_scheme

    def merge(
        self,
        tag_files: Sequence[str],
        translation_files: Sequence[str] = (),
        *,
        prompt_mode: str = "Tag",
    ) -> list[list[Any]]:
        prompt_mode = prompt_mode if prompt_mode in VALID_PROMPT_MODES else "Tag"
        selected_tag_paths: list[tuple[str, Path]] = []
        selected_translation_paths: list[tuple[str, Path]] = []
        requested_tags = _dedupe(tag_files)
        for name in requested_tags:
            try:
                selected_tag_paths.append((name, self._safe_relative(self.tag_dir, name)))
            except FileNotFoundError:
                continue
        # A replaced data folder can invalidate a saved filename. Recover to the
        # first available file only when the user had a non-empty selection.
        if requested_tags and not selected_tag_paths:
            available = self.list_tag_files()
            if available:
                fallback = available[0].name
                selected_tag_paths.append((fallback, self._safe_relative(self.tag_dir, fallback)))
        for name in _dedupe(translation_files):
            try:
                selected_translation_paths.append((name, self._safe_relative(self.translation_dir, name)))
            except FileNotFoundError:
                continue

        all_paths = [path for _, path in selected_tag_paths] + [path for _, path in selected_translation_paths]
        signature = self._signature(
            all_paths,
            {
                "tag_files": [name for name, _ in selected_tag_paths],
                "translation_files": [name for name, _ in selected_translation_paths],
            },
        )
        with self._lock:
            cached = self._cache.get(signature)
            if cached is not None:
                return cached

        merged: dict[str, TagRecord] = {}
        order: list[str] = []
        for priority, (name, path) in enumerate(selected_tag_paths):
            for record in self._read_tag_file(path, name, priority):
                key = _tag_key(record.tag)
                if key not in merged:
                    merged[key] = record
                    order.append(key)
                else:
                    self._merge_record(merged[key], record)

        translation_map: dict[str, dict[str, list[str]]] = {}
        for name, path in selected_translation_paths:
            for key, values in self._read_translation_file(path).items():
                entry = translation_map.setdefault(
                    key,
                    {"translations": [], "aliases": [], "source_files": []},
                )
                entry["translations"] = _dedupe([*entry["translations"], *values["translations"]])
                entry["aliases"] = _dedupe([*entry["aliases"], *values["aliases"]])
                entry["source_files"] = _dedupe([*entry["source_files"], name])

        for key, record in merged.items():
            values = translation_map.get(key)
            if not values:
                continue
            record.translations = _dedupe([*record.translations, *values["translations"]])
            record.aliases = _dedupe([*record.aliases, *values["aliases"]])
            record.source_files = _dedupe([*record.source_files, *values["source_files"]])

        # Keep source-file order by default. The client applies mode/context
        # ranking so the same merged cache can serve all prompt styles.
        compact = [merged[key].compact() for key in order]
        with self._lock:
            self._cache = {signature: compact}
        return compact

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


class PresetStore:
    """Built-in and user-editable preset storage."""

    VERSION = 1

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.path = data_store.config_dir / "presets.json"
        self._lock = threading.RLock()

    @staticmethod
    def _pick(names: Sequence[str], *needles: str) -> str | None:
        lowered = [(name, name.lower()) for name in names]
        for needle in needles:
            for name, lower in lowered:
                if needle in lower:
                    return name
        return None

    def default_presets(self) -> dict[str, dict[str, Any]]:
        tags = [info.name for info in self.data_store.list_tag_files()]
        translations = [info.name for info in self.data_store.list_translation_files()]
        danbooru = self._pick(tags, "danbooru_2025", "danbooru.csv", "danbooru")
        illustrious = self._pick(tags, "illustrious", "danbooru_2025", "danbooru_e621", "danbooru")
        natural = self._pick(tags, "natural_language", "englishdictionary", "english_dictionary", "natural")
        danbooru_tr = self._pick(translations, "merged_translations", "danbooru", "translation")
        natural_tr = self._pick(translations, "natural_language", "natural")

        def files(*values: str | None) -> list[str]:
            return _dedupe(value for value in values if value)

        tag_defaults = files(danbooru or (tags[0] if tags else None))
        nl_defaults = files(natural)
        hybrid_tags = files(danbooru, natural)
        tag_translations = files(danbooru_tr)
        hybrid_translations = files(danbooru_tr, natural_tr)
        common = {
            "search_translations": True,
            "show_translations": True,
            "show_source_labels": False,
            "color_natural_language": False,
            "replace_underscores": True,
            "append_comma": True,
            "append_space": True,
            "always_space_at_end": True,
            "underscore_exclusions": ",".join(DEFAULT_UNDERSCORE_EXCLUSIONS),
        }

        return {
            "Danbooru": {**common, "tag_files": tag_defaults, "translation_files": tag_translations, "prompt_mode": "Tag"},
            "SDXL": {**common, "tag_files": tag_defaults, "translation_files": tag_translations, "prompt_mode": "Tag"},
            "Illustrious": {**common, "tag_files": files(illustrious or danbooru), "translation_files": tag_translations, "prompt_mode": "Tag"},
            "Pony": {**common, "tag_files": files(self._pick(tags, "pony", "danbooru_e621", "danbooru") or danbooru), "translation_files": tag_translations, "prompt_mode": "Tag"},
            "Hybrid": {**common, "tag_files": hybrid_tags or tag_defaults, "translation_files": hybrid_translations, "prompt_mode": "Hybrid"},
            "Natural Language": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "Anima": {**common, "tag_files": hybrid_tags or tag_defaults, "translation_files": hybrid_translations, "prompt_mode": "Hybrid"},
            "Krea 2": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "Z-Image": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "FLUX": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "Qwen-Image": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "Qwen-Image 2.0": {**common, "tag_files": nl_defaults or tag_defaults, "translation_files": files(natural_tr), "prompt_mode": "Natural Language"},
            "Custom": {**common, "tag_files": tag_defaults, "translation_files": tag_translations, "prompt_mode": "Custom"},
        }

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Preset file must contain an object")
            return data
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {"version": self.VERSION, "builtin_overrides": {}, "user_presets": {}}

    def _write(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="presets-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _validate_name(name: Any) -> str:
        clean_name = _clean(name)
        if (
            not clean_name
            or len(clean_name) > 120
            or any(ch in clean_name for ch in "\r\n\0/\\")
            or clean_name in {".", ".."}
        ):
            raise ValueError("Invalid preset name")
        return clean_name

    @staticmethod
    def validate_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
        mode = _clean(settings.get("prompt_mode")) or "Tag"
        if mode not in VALID_PROMPT_MODES:
            mode = "Tag"
        anima_artist_prefix = _clean(settings.get("anima_artist_prefix")) or "Off"
        if anima_artist_prefix not in {"Off", "On", "Auto"}:
            anima_artist_prefix = "Off"
        return {
            "tag_files": _string_list(settings.get("tag_files")),
            "translation_files": _string_list(settings.get("translation_files")),
            "prompt_mode": mode,
            "search_translations": _to_bool(settings.get("search_translations"), True),
            "show_translations": _to_bool(settings.get("show_translations"), True),
            "show_source_labels": _to_bool(settings.get("show_source_labels"), False),
            "color_natural_language": _to_bool(settings.get("color_natural_language"), False),
            "replace_underscores": _to_bool(settings.get("replace_underscores"), True),
            "append_comma": _to_bool(settings.get("append_comma"), True),
            "append_space": _to_bool(settings.get("append_space"), True),
            "always_space_at_end": _to_bool(settings.get("always_space_at_end"), True),
            "underscore_exclusions": ",".join(parse_patterns(settings.get("underscore_exclusions") or DEFAULT_UNDERSCORE_EXCLUSIONS)),
            "anima_artist_prefix": anima_artist_prefix,
        }

    # Kept for compatibility with early JP Assist builds.
    _validate_settings = validate_settings

    def list(self) -> dict[str, Any]:
        with self._lock:
            stored = self._read()
            builtins = self.default_presets()
            overrides = stored.get("builtin_overrides") or {}
            for name, settings in overrides.items():
                if name in builtins and isinstance(settings, Mapping):
                    builtins[name] = self.validate_settings(settings)
            users = {
                name: self.validate_settings(settings)
                for name, settings in (stored.get("user_presets") or {}).items()
                if isinstance(name, str) and isinstance(settings, Mapping)
            }
            return {"version": self.VERSION, "builtins": builtins, "users": users}

    def get(self, name: str) -> dict[str, Any] | None:
        data = self.list()
        return data["users"].get(name) or data["builtins"].get(name)

    def save(self, name: str, settings: Mapping[str, Any], *, builtin_override: bool = False) -> dict[str, Any]:
        clean_name = self._validate_name(name)
        validated = self.validate_settings(settings)
        with self._lock:
            stored = self._read()
            key = "builtin_overrides" if builtin_override and clean_name in self.default_presets() else "user_presets"
            stored.setdefault(key, {})[clean_name] = validated
            self._write(stored)
        return validated

    def delete(self, name: str) -> bool:
        try:
            clean_name = self._validate_name(name)
        except ValueError:
            return False
        with self._lock:
            stored = self._read()
            changed = False
            for key in ("user_presets", "builtin_overrides"):
                if clean_name in (stored.get(key) or {}):
                    del stored[key][clean_name]
                    changed = True
            if changed:
                self._write(stored)
            return changed

    def restore_builtins(self) -> None:
        with self._lock:
            stored = self._read()
            stored["builtin_overrides"] = {}
            self._write(stored)

    def export(self) -> dict[str, Any]:
        data = self.list()
        return {"version": self.VERSION, "users": data["users"]}

    def import_data(self, payload: Mapping[str, Any], *, replace: bool = False) -> dict[str, Any]:
        builtins = payload.get("builtins") or payload.get("builtin_overrides") or {}
        users = payload.get("users") or payload.get("user_presets") or {}
        with self._lock:
            stored = {"version": self.VERSION, "builtin_overrides": {}, "user_presets": {}} if replace else self._read()
            known_builtins = self.default_presets()
            for name, settings in builtins.items():
                if name in known_builtins and isinstance(settings, Mapping):
                    stored.setdefault("builtin_overrides", {})[name] = self.validate_settings(settings)
            for name, settings in users.items():
                if isinstance(name, str) and isinstance(settings, Mapping):
                    try:
                        clean_name = self._validate_name(name)
                    except ValueError:
                        continue
                    stored.setdefault("user_presets", {})[clean_name] = self.validate_settings(settings)
            self._write(stored)
        return self.list()


class RemoteUpdater:
    """Conditional, atomic HTTP updater for a single tag CSV."""

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.meta_path = data_store.config_dir / "remote_update.json"
        self._lock = threading.RLock()

    def load_meta(self) -> dict[str, Any]:
        try:
            data = json.loads(self.meta_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_meta(self, data: Mapping[str, Any]) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.meta_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.meta_path)

    @staticmethod
    def _headers(response: Any) -> dict[str, str]:
        return {
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "content_length": response.headers.get("Content-Length", ""),
        }

    @staticmethod
    def _validate_download(path: Path) -> None:
        if path.stat().st_size == 0:
            raise ValueError("Downloaded file is empty")
        with path.open("rb") as handle:
            sample = handle.read(65536)
        if b"\0" in sample:
            raise ValueError("Downloaded file is not a text CSV")
        try:
            text = sample.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Downloaded CSV is not UTF-8") from exc
        prefix = text.lstrip().lower()
        if prefix.startswith(("<!doctype html", "<html", "<?xml")):
            raise ValueError("Downloaded content is not a CSV")
        first = next((row for row in csv.reader(text.splitlines()) if row and any(_clean(value) for value in row)), None)
        if not first or not _clean(first[0]):
            raise ValueError("Downloaded CSV contains no usable rows")

    def update(self, session: Any, url: str, target_name: str, *, timeout: tuple[int, int] = (10, 90)) -> dict[str, Any]:
        url = _clean(url)
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Remote URL must use http:// or https://")
        target_name = _clean(target_name) or "danbooru_tags.csv"
        if Path(target_name).name != target_name or not target_name.lower().endswith(".csv"):
            raise ValueError("Remote target must be a CSV filename without folders")
        target = self.data_store.tag_dir / target_name
        with self._lock:
            old_meta = self.load_meta()
            head_error = None
            try:
                head = session.head(url, allow_redirects=True, timeout=timeout[0])
                head.raise_for_status()
                remote = {**self._headers(head), "url": url, "target": target_name}
            except Exception as exc:
                # Some file hosts reject HEAD while allowing GET. Continue with
                # an unconditional streamed GET rather than disabling updates.
                head_error = str(exc)
                remote = {"etag": "", "last_modified": "", "content_length": "", "url": url, "target": target_name}

            changed = not target.is_file() or old_meta.get("url") != url or old_meta.get("target") != target_name
            validators_present = any(remote.get(key) for key in ("etag", "last_modified", "content_length"))
            for key in ("etag", "last_modified", "content_length"):
                if remote.get(key) and remote.get(key) != old_meta.get(key):
                    changed = True
                    break
            if not validators_present:
                changed = True
            if not changed:
                return {"updated": False, "using_existing": True, "meta": old_meta, "target": target_name}

            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + ".download")
            try:
                with session.get(url, allow_redirects=True, stream=True, timeout=timeout) as response:
                    response.raise_for_status()
                    with temp.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                handle.write(chunk)
                self._validate_download(temp)
                os.replace(temp, target)
                remote["local_size"] = target.stat().st_size
                if head_error:
                    remote["head_warning"] = head_error
                self.save_meta(remote)
                self.data_store.clear_cache()
                return {"updated": True, "using_existing": True, "meta": remote, "target": target_name}
            except Exception as exc:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
                return {
                    "updated": False,
                    "using_existing": target.is_file(),
                    "error": str(exc),
                    "target": target_name,
                }


def _looks_like_translation_csv(path: Path) -> bool:
    """Best-effort classification for legacy root-level CSV files."""

    lower_name = path.stem.casefold()
    name_hints = (
        "translation",
        "translations",
        "translated",
        "japanese",
        "_ja",
        "-ja",
        "_jp",
        "-jp",
        "alias_ja",
    )
    if any(hint in lower_name for hint in name_hints):
        return True

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            first = next(
                (row for row in csv.reader(handle) if row and any(_clean(value) for value in row)),
                None,
            )
    except (OSError, UnicodeError, csv.Error):
        return False
    if not first:
        return False

    header = {_normalise_header(value) for value in first}
    if (
        header & set(_SOURCE_TYPE_KEYS)
        or header & set(_INSERT_MODE_KEYS)
        or header & set(_CATEGORY_KEYS)
        or header & set(_COUNT_KEYS)
    ):
        return False
    if header & set(_TRANSLATION_KEYS):
        return True

    # Headerless TagComplete lists normally have numeric category/count columns.
    # A two/three-column row with a non-numeric second value is usually a
    # translation file (tag, translation[, aliases]).
    if len(first) >= 2 and _to_category(first[1]) is None:
        return True
    return False


def migrate_legacy_files(root: Path) -> None:
    """Move root-level data files into the separated folders once.

    The operation is deliberately conservative: existing destinations win and
    files in ``temp``/``cache`` are untouched.
    """

    store = DataStore(root)
    for path in root.glob("*.csv"):
        destination_dir = store.translation_dir if _looks_like_translation_csv(path) else store.tag_dir
        destination = destination_dir / path.name
        if not destination.exists():
            shutil.move(str(path), str(destination))
    for path in root.glob("*.json"):
        destination = store.chant_dir / path.name
        if not destination.exists():
            shutil.move(str(path), str(destination))
