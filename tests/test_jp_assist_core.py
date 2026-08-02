from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from scripts.jp_assist_core import (
    DEFAULT_UNDERSCORE_EXCLUSIONS,
    DataStore,
    PresetStore,
    RemoteUpdater,
    is_underscore_protected,
    migrate_legacy_files,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_jp_assist_core_supports_forge_style_loader() -> None:
    """Forge executes script modules without first adding them to sys.modules."""

    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "jp_assist_core.py"
    name = "_test_jp_assist_core_unregistered"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    assert name not in sys.modules
    spec.loader.exec_module(module)
    assert module.TagRecord(tag="school").tag == "school"


def test_merge_multiple_tag_and_translation_files(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(
        store.tag_dir / "danbooru.csv",
        "tag,category,count,aliases\nlong_hair,0,100,longhair\nscore_8_up,5,20,\n",
    )
    write(
        store.tag_dir / "natural_language_tags.csv",
        "tag,category,count,aliases,source_type,insert_mode\n"
        "long_hair,,5,flowing hair,natural_language,phrase\n"
        "with,,3,,natural_language,word\n",
    )
    write(
        store.translation_dir / "merged_translations.csv",
        'tag,ja,aliases\nlong_hair,"長髪,ロングヘア","髪が長い"\n',
    )

    rows = store.merge(
        ["danbooru.csv", "natural_language_tags.csv"],
        ["merged_translations.csv"],
        prompt_mode="Hybrid",
    )
    by_name = {row[0]: row for row in rows}

    long_hair = by_name["long_hair"]
    assert long_hair[1] == 0
    assert long_hair[2] == 100
    assert set(long_hair[3].split(",")) == {"longhair", "flowing hair", "髪が長い"}
    assert set(part.strip() for part in long_hair[4].split(",")) == {"長髪", "ロングヘア"}
    assert long_hair[5] == "tag"
    assert long_hair[6] == "tag"
    assert long_hair[7] == "danbooru"
    assert long_hair[8] == [
        "danbooru.csv",
        "natural_language_tags.csv",
        "merged_translations.csv",
    ]

    assert by_name["with"][5] == "natural_language"
    assert by_name["with"][6] == "word"
    assert by_name["score_8_up"][6] == "tag"


def test_headerless_tagcomplete_and_translation_files(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(store.tag_dir / "custom.csv", 'blue_eyes,0,99,"blueeyes"\n')
    write(store.translation_dir / "ja.csv", "blue_eyes,青い目\n")
    rows = store.merge(["custom.csv"], ["ja.csv"])
    assert rows == [["blue_eyes", 0, 99, "blueeyes", "青い目", "custom", "tag", "danbooru", ["custom.csv", "ja.csv"], ["custom"]]]


def test_underscore_protection_patterns() -> None:
    assert is_underscore_protected("score_8_up", DEFAULT_UNDERSCORE_EXCLUSIONS)
    assert is_underscore_protected("^_^", DEFAULT_UNDERSCORE_EXCLUSIONS)
    assert is_underscore_protected("__wildcards/eye-color__", [])
    assert not is_underscore_protected("long_hair", DEFAULT_UNDERSCORE_EXCLUSIONS)
    assert is_underscore_protected("abc_123", ["abc_*"])


def test_user_presets_save_export_and_import(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(store.tag_dir / "danbooru.csv", "1girl,0,10,\n")
    write(store.tag_dir / "natural_language_tags.csv", "soft light,0,5,\n")
    presets = PresetStore(store)

    defaults = presets.list()
    assert defaults["builtins"] == {}
    assert defaults["users"] == {}

    saved = presets.save(
        "My Hybrid",
        {
            "tag_files": ["danbooru.csv", "natural_language_tags.csv"],
            "translation_files": [],
            "prompt_mode": "Hybrid",
        },
    )
    assert saved["prompt_mode"] == "Hybrid"
    assert saved["anima_artist_prefix"] == "Off"
    exported = presets.export()
    assert "My Hybrid" in exported["users"]
    assert "builtins" not in exported

    other = PresetStore(DataStore(tmp_path / "other"))
    imported = other.import_data(exported)
    assert imported["users"]["My Hybrid"]["tag_files"] == [
        "danbooru.csv",
        "natural_language_tags.csv",
    ]

    presets.save("Danbooru", {"tag_files": [], "prompt_mode": "Custom"}, builtin_override=True)
    assert presets.list()["users"]["Danbooru"]["prompt_mode"] == "Custom"
    presets.restore_builtins()
    assert presets.list()["users"]["Danbooru"]["prompt_mode"] == "Custom"


def test_anima_artist_prefix_preset_validation(tmp_path: Path) -> None:
    presets = PresetStore(DataStore(tmp_path / "tags"))
    assert presets.validate_settings({"anima_artist_prefix": "On"})["anima_artist_prefix"] == "On"
    assert presets.validate_settings({"anima_artist_prefix": "Auto"})["anima_artist_prefix"] == "Auto"
    assert presets.validate_settings({"anima_artist_prefix": "invalid"})["anima_artist_prefix"] == "Off"


def test_candidate_sort_mode_preset_validation_defaults_to_legacy(tmp_path: Path) -> None:
    presets = PresetStore(DataStore(tmp_path / "tags"))
    assert presets.validate_settings({})["candidate_sort_mode"] == "Legacy"
    assert presets.validate_settings({"candidate_sort_mode": "Relevance"})["candidate_sort_mode"] == "Relevance"
    assert presets.validate_settings({"candidate_sort_mode": "invalid"})["candidate_sort_mode"] == "Legacy"


class FakeResponse:
    def __init__(self, data=b"", headers=None):
        self.data = data
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024):
        yield self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self):
        self.version = 1
        self.get_calls = 0

    def head(self, url, allow_redirects=True, timeout=10):
        return FakeResponse(headers={"ETag": f'"v{self.version}"', "Content-Length": "10"})

    def get(self, url, allow_redirects=True, stream=True, timeout=(10, 90)):
        self.get_calls += 1
        return FakeResponse(data=f"tag,category,count\nvalue_{self.version},0,1\n".encode())


def test_remote_update_is_conditional_and_atomic(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    updater = RemoteUpdater(store)
    session = FakeSession()

    first = updater.update(session, "https://example.invalid/tags.csv", "remote.csv")
    assert first["updated"] is True
    assert (store.tag_dir / "remote.csv").is_file()
    assert session.get_calls == 1

    second = updater.update(session, "https://example.invalid/tags.csv", "remote.csv")
    assert second["updated"] is False
    assert session.get_calls == 1

    session.version = 2
    third = updater.update(session, "https://example.invalid/tags.csv", "remote.csv")
    assert third["updated"] is True
    assert session.get_calls == 2
    assert "value_2" in (store.tag_dir / "remote.csv").read_text()


def test_translation_matches_underscore_and_space_equivalents(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(store.tag_dir / "natural_language_tags.csv", "tag,source_type\nsoft natural lighting,natural_language\n")
    write(store.translation_dir / "natural_ja.csv", "tag,ja\nsoft_natural_lighting,柔らかな自然光\n")
    rows = store.merge(["natural_language_tags.csv"], ["natural_ja.csv"])
    assert rows[0][0] == "soft natural lighting"
    assert rows[0][4] == "柔らかな自然光"


def test_multiple_translation_files_are_merged_once_in_selection_order(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(store.tag_dir / "danbooru.csv", "long_hair,0,100,longhair\n")
    write(store.translation_dir / "first.csv", "tag,ja,aliases\nlong_hair,長髪,髪が長い\n")
    write(store.translation_dir / "second.csv", "tag,ja,aliases\nlong hair,ロングヘア,長い髪\n")

    rows = store.merge(["danbooru.csv"], ["first.csv", "second.csv"])
    assert rows[0][4] == "長髪, ロングヘア"
    assert rows[0][3] == "longhair,髪が長い,長い髪"
    assert rows[0][8] == ["danbooru.csv", "first.csv", "second.csv"]


def test_large_csv_is_read_without_changing_order(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    body = ["tag,category,count"] + [f"tag_{index},0,{index}" for index in range(5000)]
    write(store.tag_dir / "large.csv", "\n".join(body))
    rows = store.merge(["large.csv"])
    assert len(rows) == 5000
    assert rows[0][0] == "tag_0"
    assert rows[-1][0] == "tag_4999"
    # Prompt mode changes ranking in the browser and must not rebuild server data.
    cached = store.merge(["large.csv"], prompt_mode="Natural Language")
    assert cached is rows


def test_file_scan_supports_nested_and_uppercase_extensions(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    write(store.tag_dir / "nested" / "CUSTOM.CSV", "tag,category,count\nvalue,0,1\n")
    write(store.translation_dir / "nested" / "JA.CSV", "tag,ja\nvalue,値\n")
    assert [item.name for item in store.list_tag_files()] == ["nested/CUSTOM.CSV"]
    assert [item.name for item in store.list_translation_files()] == ["nested/JA.CSV"]


def test_legacy_migration_separates_translation_and_tag_files(tmp_path: Path) -> None:
    root = tmp_path / "tags"
    root.mkdir()
    write(root / "danbooru.csv", "1girl,0,10,\n")
    write(root / "merged_translations_ja.csv", "tag,ja,aliases\n1girl,少女,女の子\n")
    write(root / "two_column.csv", "1girl,少女\n")
    write(root / "demo.json", "[]\n")

    migrate_legacy_files(root)

    assert (root / "tag_files" / "danbooru.csv").is_file()
    assert (root / "translation_files" / "merged_translations_ja.csv").is_file()
    assert (root / "translation_files" / "two_column.csv").is_file()
    assert (root / "chants" / "demo.json").is_file()


def test_invalid_preset_names_are_rejected(tmp_path: Path) -> None:
    presets = PresetStore(DataStore(tmp_path / "tags"))
    for name in ("", "../escape", "folder/name", "bad\\name"):
        try:
            presets.save(name, {})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid preset name: {name!r}")


def test_remote_update_rejects_non_text_payload(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "tags")
    updater = RemoteUpdater(store)

    class BadSession(FakeSession):
        def get(self, url, allow_redirects=True, stream=True, timeout=(10, 90)):
            return FakeResponse(data=b"bad\x00payload")

    result = updater.update(BadSession(), "https://example.invalid/bad.csv", "bad.csv")
    assert result["updated"] is False
    assert not (store.tag_dir / "bad.csv").exists()
