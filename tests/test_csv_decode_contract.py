"""Shared CSV semantics without replacing the compact server representation."""
import csv
from pathlib import Path

import pytest

from scripts.jp_assist_core import DataStore, DEFAULT_UNDERSCORE_EXCLUSIONS, _tag_key
from scripts.tacjp_fast_search import FastSearchStore
from scripts.tacjp_fast_search_common import canonical_tag


@pytest.mark.parametrize("header", [True, False])
@pytest.mark.parametrize("name", ["danbooru.csv", "natural_language_tags.csv"])
def test_bom_blanks_and_row_fields_agree(tmp_path: Path, header: bool, name: str):
    store = DataStore(tmp_path / "tags")
    path = store.tag_dir / name
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([])
        if header:
            writer.writerow(["tag", "category", "post count", "aliases", "ja"])
        writer.writerows([["blue_hair", "0", "1,234", "longhair;hair", "青髪"],
                          ["score_8_up", "", "unknown", "", ""], ["# comment"], []])
    legacy = list(store._read_tag_file(path, name, 0))
    server = FastSearchStore(store)._load_parsed_tag_file(name, path, persistent=False)
    fields = [(v.tag, v.category, v.count, tuple(v.aliases), tuple(v.translations),
               v.source_type, v.insert_mode, v.category_scheme) for v in legacy]
    assert fields == server
    assert [v.tag for v in legacy] == ["blue_hair", "score_8_up"]
    assert legacy[0].aliases == ["longhair", "hair"]
    assert legacy[0].translations == ["青髪"]
    assert legacy[0].category == 0
    assert legacy[0].count == (None if name.startswith("natural") else 1234)
    assert legacy[1].count is None
    assert all(isinstance(v, tuple) for v in server)


@pytest.mark.parametrize("header", [True, False])
def test_translation_rows_merge_with_first_spelling_and_protected_keys(tmp_path: Path, header: bool):
    store = DataStore(tmp_path / "tags")
    path = store.translation_dir / "ja.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if header:
            writer.writerow(["english", "translation", "synonyms"])
        writer.writerows([["blue_hair", "青髪;青い髪", "LongHair"],
                          ["BLUE HAIR", "青髪", "longhair;Hair"],
                          ["score_8_up", "高品質", ""], ["# comment"], []])
    legacy = store._read_translation_file(path)
    server = FastSearchStore(store)._load_parsed_translation_file("ja.csv", path, persistent=False)
    assert legacy == {key: {"translations": list(v[0]), "aliases": list(v[1])} for key, v in server.items()}
    assert legacy["blue hair"] == {"translations": ["青髪", "青い髪"], "aliases": ["LongHair", "Hair"]}
    assert "score_8_up" in legacy


@pytest.mark.parametrize("raw,expected", [
    ("", ""), (None, ""), (" ＢＬＵＥ＿ＨＡＩＲ ", "blue hair"),
    ("blue\thair", "blue hair"), ("score_8_up", "score_8_up"),
    ("rating_safe", "rating_safe"), ("source_test", "source_test"),
    ("__wildcards/eye_color__", "__wildcards/eye_color__"), ("^_^", "^_^"),
    ("Blue  Hair", "blue hair"), ("e\u0301clair", "éclair"),
    ("少女　長髪", "少女 長髪"), ("foo-bar", "foo-bar"),
    ("a,b", "a,b"), ("＠＿＠", "@_@"), ("<lora:test_1:0.8>", "<lora:test 1:0.8>"),
])
def test_canonical_keys_keep_existing_meaning(raw, expected):
    assert _tag_key(raw) == canonical_tag(raw) == expected


def test_all_literal_default_underscore_protections_remain_intact():
    for value in DEFAULT_UNDERSCORE_EXCLUSIONS:
        if "*" not in value and "?" not in value:
            assert canonical_tag(value) == value.casefold()
