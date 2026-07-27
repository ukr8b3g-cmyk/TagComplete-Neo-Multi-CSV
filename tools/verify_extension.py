#!/usr/bin/env python3
"""Offline verification for a TagComplete Neo Multi-CSV checkout or ZIP extraction.

This does not launch Forge. It validates package layout, compiles Python files,
runs the pure merge/preset smoke test, and checks JavaScript syntax when Node.js
is available.
"""

from __future__ import annotations

import compileall
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.jp_assist_core import DataStore, PresetStore, is_underscore_protected  # noqa: E402

REQUIRED = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "install.py",
    "javascript/__globals.js",
    "javascript/tacjp_core.js",
    "javascript/tagAutocomplete.js",
    "javascript/zz_jpAssistUI.js",
    "scripts/jp_assist_core.py",
    "scripts/tag_autocomplete_helper.py",
    "tags/tag_files/danbooru_2025.csv",
    "tags/tag_files/e621.csv",
    "tags/tag_files/natural_language_tags.csv",
    "tags/tag_files/README.md",
    "tags/translation_files/merged_translations_dedup.csv",
    "tags/translation_files/natural_language_ja.csv",
    "tags/translation_files/README.md",
]


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def check_layout() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        fail("Missing required files: " + ", ".join(missing))


def check_python() -> None:
    if not compileall.compile_dir(ROOT / "scripts", quiet=1):
        fail("Python compilation failed")


def check_javascript() -> None:
    node = shutil.which("node")
    if not node:
        print("[SKIP] Node.js not installed; JavaScript syntax check skipped")
        return
    for path in sorted((ROOT / "javascript").glob("*.js")):
        subprocess.run([node, "--check", str(path)], check=True, stdout=subprocess.DEVNULL)
    test = ROOT / "tests" / "test_tacjp_core.js"
    if test.is_file():
        subprocess.run([node, str(test)], check=True)


def smoke_test() -> None:
    with tempfile.TemporaryDirectory(prefix="tacjp-verify-") as tmp:
        store = DataStore(Path(tmp) / "tags")
        with (store.tag_dir / "danbooru.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tag", "category", "count", "aliases"])
            writer.writerow(["long_hair", 0, 100, "longhair"])
            writer.writerow(["score_8_up", 5, 10, ""])
        with (store.tag_dir / "natural_language_tags.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tag", "source_type", "insert_mode"])
            writer.writerow(["soft natural lighting", "natural_language", "phrase"])
        with (store.translation_dir / "ja.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tag", "ja", "aliases"])
            writer.writerow(["long_hair", "長髪", "髪が長い"])

        rows = store.merge(
            ["danbooru.csv", "natural_language_tags.csv"],
            ["ja.csv"],
            prompt_mode="Hybrid",
        )
        by_name = {row[0]: row for row in rows}
        if "long_hair" not in by_name or "soft natural lighting" not in by_name:
            fail("Merge smoke test did not return expected rows")
        if "長髪" not in by_name["long_hair"][4]:
            fail("Translation merge smoke test failed")
        if not is_underscore_protected("score_8_up", ["score_*"]):
            fail("Underscore protection smoke test failed")
        if not is_underscore_protected("__wildcards/eye-color__", []):
            fail("Wildcard preservation smoke test failed")

        presets = PresetStore(store)
        if presets.list()["builtins"]:
            fail("Built-in presets must not be exposed")
        presets.save("Smoke Test", {"tag_files": ["danbooru.csv"], "prompt_mode": "Tag"})
        if "Smoke Test" not in presets.list()["users"]:
            fail("User preset smoke test failed")


def main() -> None:
    check_layout()
    check_python()
    check_javascript()
    smoke_test()
    print("[PASS] Offline package verification completed")
    print("[NOTE] Forge / Forge Neo runtime UI testing still requires a real WebUI installation")


if __name__ == "__main__":
    main()
