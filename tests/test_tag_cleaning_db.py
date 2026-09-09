from pathlib import Path

from scripts.tag_cleaning_db import TagCleaningStore, normalize_tag, sensitivity_settings


def test_normalize_tag_preserves_kind_and_danbooru_name():
    assert normalize_tag("gen:School Uniform") == ("gen", "school_uniform")
    assert normalize_tag("artist:Foo_Bar") == ("artist", "foo_bar")
    assert normalize_tag("Long Hair") == ("", "long_hair")


def test_sensitivity_fallback_is_balanced():
    assert sensitivity_settings("unknown") == sensitivity_settings("Balanced")


def test_lookup_warning_and_strong_related_add(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "cleaning")
    rows = []
    for index in range(20):
        rows.append(
            {
                "image_id": str(index),
                "add": ["gen:new_tag"] if index < 15 else [],
                "remove": ["gen:old_tag"],
            }
        )
    for index in range(3):
        rows.append(
            {
                "image_id": f"add-{index}",
                "add": ["gen:old_tag"],
                "remove": [],
            }
        )
    status = store.build_from_actions(rows, metadata={"source_repository": "test"})
    assert status["ready"] is True

    result = store.lookup(
        [{"tag": "old_tag", "category": 0}],
        show_warnings=True,
        show_suggestions=True,
        sensitivity="Balanced",
    )
    match = result["results"][0]["match"]
    assert match["warning"] is True
    assert match["remove_count"] == 20
    assert match["add_count"] == 3
    assert match["suggestions"][0]["tag"] == "new_tag"
    assert match["suggestions"][0]["support"] == 15
    assert match["suggestions"][0]["confidence"] == 0.75


def test_remove_does_not_mean_deprecated_and_can_be_hidden(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "cleaning")
    store.build_from_actions(
        [{"add": [], "remove": ["gen:common_tag"]} for _ in range(30)]
    )
    result = store.lookup(
        [{"tag": "common_tag", "category": 0}],
        show_warnings=False,
        show_suggestions=True,
        sensitivity="Balanced",
    )
    match = result["results"][0]["match"]
    assert match["warning"] is False
    assert match["suggestions"] == []


def test_category_avoids_cross_category_collision(tmp_path: Path):
    store = TagCleaningStore(tmp_path / "cleaning")
    rows = (
        [{"add": [], "remove": ["gen:same_name"]} for _ in range(20)]
        + [{"add": ["artist:same_name"], "remove": []} for _ in range(20)]
    )
    store.build_from_actions(rows)
    general = store.lookup([{"tag": "same_name", "category": 0}])["results"][0]["match"]
    artist = store.lookup([{"tag": "same_name", "category": 1}])["results"][0]["match"]
    assert general["remove_count"] == 20 and general["add_count"] == 0
    assert artist["add_count"] == 20 and artist["remove_count"] == 0
