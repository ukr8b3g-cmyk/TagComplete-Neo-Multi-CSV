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
    assert '"Show user preset controls near prompts"' in helper
    assert 'lambda: {"visible": False}' in helper

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


def test_unfinished_preset_controls_are_hidden() -> None:
    ui = (ROOT / "javascript/zz_jpAssistUI.js").read_text(encoding="utf-8")
    assert 'wrapper.className = "tacjp-manager-shell"' in ui
    assert "tacjp-advanced-panel tacjp-${kind}-advanced" in ui
    assert '"core", "coreAdvancedTitle"' in ui
    assert '"multicsv", "multiAdvancedTitle"' in ui
    assert 'tacJpCreateSectionMarker("shared")' not in ui
    assert 'sharedTitle:' not in ui
    assert '"（再起動が必要）"' in ui
    assert '"（試験的機能）"' in ui
    assert 'tacJpSetDirectLabelText(button, tacJpText("restoreExclusions"))' in ui
    assert '"tac_keymap"' in ui
    assert '"tac_colormap"' in ui
    assert '"tac_refreshTempFiles"' in ui
    assert "Preset controls are intentionally hidden in this release" in ui
    assert '#settings_restart_gradio' not in ui
    assert 'saveChangesButton' not in ui
    assert 'renameButton' not in ui
    for key in (
        "tacjp_tagFiles",
        "tacjp_translationFiles",
        "tacjp_promptMode",
            "tacjp_showTranslations",
            "tacjp_showSourceLabels",
            "tacjp_colorNaturalLanguage",
            "tac_animaArtistPrefix",
        "tacjp_searchEngine",
        "tacjp_serverResultPool",
        "tacjp_persistentSearchCache",
        "tacjp_searchMemoryEntries",
        "tacjp_searchDiskEntries",
        "tacjp_searchDebug",
        "tacjp_clearSearchCache",
    ):
        assert key in ui


def test_expected_csv_files_are_bundled() -> None:
    expected = {
        "tags/tag_files/danbooru_2025.csv",
        "tags/tag_files/e621.csv",
        "tags/tag_files/anima_artists.csv",
        "tags/tag_files/anima_characters.csv",
        "tags/tag_files/natural_language_tags.csv",
        "tags/translation_files/merged_translations_dedup.csv",
        "tags/translation_files/natural_language_ja.csv",
    }
    assert all((ROOT / name).is_file() for name in expected)
    assert not (ROOT / "tags/tag_files/danbooru_tags.csv").exists()


def test_default_multi_csv_selection_is_documented_in_code() -> None:
    helper = (ROOT / "scripts/tag_autocomplete_helper.py").read_text(encoding="utf-8")
    assert '("danbooru_2025.csv", "natural_language_tags.csv")' in helper
    assert '("merged_translations_dedup.csv", "natural_language_ja.csv")' in helper
