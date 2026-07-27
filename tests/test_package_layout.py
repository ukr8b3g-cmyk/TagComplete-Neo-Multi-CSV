from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_files_and_load_order_exist() -> None:
    required = [
        "javascript/tacjp_core.js",
        "javascript/tacjp_fast_search_core.js",
        "javascript/tagAutocomplete.js",
        "javascript/zz_jpAssistUI.js",
        "javascript/zzzz_tacjp_fast_search.js",
        "scripts/jp_assist_core.py",
        "scripts/tag_autocomplete_helper.py",
        "scripts/tacjp_fast_search.py",
        "scripts/tacjp_fast_search_common.py",
        "scripts/tacjp_fast_search_files.py",
        "scripts/tacjp_fast_search_index.py",
        "scripts/tacjp_fast_search_query.py",
        "scripts/zz_tacjp_fast_search.py",
    ]
    for name in required:
        assert (ROOT / name).is_file(), name
    assert (
        "tacjp_core.js"
        < "tacjp_fast_search_core.js"
        < "tagAutocomplete.js"
        < "zz_jpAssistUI.js"
        < "zzzz_tacjp_fast_search.js"
    )
    assert "tag_autocomplete_helper.py" < "zz_tacjp_fast_search.py"


def test_expected_settings_are_registered() -> None:
    helper = (
        ROOT / "scripts/tag_autocomplete_helper.py"
    ).read_text(encoding="utf-8")
    for key in (
        "tacjp_tagFiles",
        "tacjp_translationFiles",
        "tacjp_promptMode",
        "tacjp_showTranslations",
        "tacjp_quickControls",
        "tac_undersocreReplacementExclusionList",
        "tac_animaArtistPrefix",
    ):
        assert key in helper
    assert (
        'shared.OptionInfo(False, "Show user preset controls near prompts'
        in helper
    )

    fast_helper = (
        ROOT / "scripts/zz_tacjp_fast_search.py"
    ).read_text(encoding="utf-8")
    for key in (
        "tacjp_searchEngine",
        "tacjp_serverResultPool",
        "tacjp_persistentSearchCache",
        "tacjp_searchMemoryEntries",
        "tacjp_searchDiskEntries",
        "tacjp_searchDebug",
        "tacjp_clearSearchCache",
    ):
        assert key in fast_helper


def test_expected_csv_files_are_bundled() -> None:
    expected = {
        "tags/tag_files/danbooru_2025.csv",
        "tags/tag_files/anima_artists.csv",
        "tags/tag_files/anima_characters.csv",
        "tags/tag_files/natural_language_tags.csv",
        "tags/translation_files/merged_translations_dedup.csv",
        "tags/translation_files/natural_language_ja.csv",
    }
    assert all((ROOT / name).is_file() for name in expected)
    assert not (ROOT / "tags/tag_files/danbooru_tags.csv").exists()
