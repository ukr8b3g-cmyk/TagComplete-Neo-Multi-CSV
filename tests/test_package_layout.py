from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_files_and_load_order_exist() -> None:
    required = [
        "javascript/tacjp_core.js",
        "javascript/tagAutocomplete.js",
        "javascript/zz_jpAssistUI.js",
        "scripts/jp_assist_core.py",
        "scripts/tag_autocomplete_helper.py",
    ]
    for name in required:
        assert (ROOT / name).is_file(), name
    assert "tacjp_core.js" < "tagAutocomplete.js" < "zz_jpAssistUI.js"


def test_expected_settings_are_registered() -> None:
    helper = (ROOT / "scripts/tag_autocomplete_helper.py").read_text(encoding="utf-8")
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
    assert 'shared.OptionInfo(False, "Show user preset controls near prompts' in helper


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
