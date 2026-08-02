from __future__ import annotations

import concurrent.futures
import os
import pickle
import time
from pathlib import Path

import pytest

from scripts.jp_assist_core import DataStore
from scripts.tacjp_fast_search_common import (
    CACHE_VERSION,
    UINT32_MAX,
    build_compact_index,
    compact_index_get,
    is_compact_index,
)
from scripts.tacjp_fast_search import FastSearchStore, SearchRequest


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def create_six_file_fixture(tmp_path: Path) -> FastSearchStore:
    data = DataStore(tmp_path / "tags")
    write(
        data.tag_dir / "danbooru.csv",
        "tag,category,count,aliases\n"
        "long_hair,0,100,longhair\n"
        "blue_eyes,0,90,blueeyes\n"
        "score_8_up,5,80,\n",
    )
    write(
        data.tag_dir / "natural_language_tags.csv",
        "tag,count,aliases,source_type,insert_mode\n"
        "soft natural lighting,70,soft light,natural_language,phrase\n"
        "with,60,,natural_language,word\n",
    )
    write(
        data.tag_dir / "custom.csv",
        "tag,count,aliases,source_type\n"
        "portrait lighting,50,portrait light,custom\n",
    )
    write(
        data.translation_dir / "danbooru_ja.csv",
        "tag,ja,aliases\n"
        "long_hair,長髪,髪が長い\n"
        "blue_eyes,青い目,碧眼\n",
    )
    write(
        data.translation_dir / "natural_ja.csv",
        "tag,ja,aliases\n"
        "soft_natural_lighting,柔らかな自然光,自然光\n",
    )
    write(
        data.translation_dir / "custom_ja.csv",
        "tag,ja\nportrait lighting,ポートレート照明\n",
    )
    return FastSearchStore(data)


def request(query: str, **overrides) -> SearchRequest:
    values = dict(
        query=query,
        tag_files=[
            "danbooru.csv",
            "natural_language_tags.csv",
            "custom.csv",
        ],
        translation_files=[
            "danbooru_ja.csv",
            "natural_ja.csv",
            "custom_ja.csv",
        ],
        prompt_mode="Hybrid",
        limit=100,
        persistent_cache=True,
    )
    values.update(overrides)
    return SearchRequest(**values)


def test_compact_index_boundaries_and_reproducibility() -> None:
    first = build_compact_index(
        {
            "large": range(100_000),
            "empty": (),
            "small": (3, 7, 9),
        }
    )
    second = build_compact_index(
        {
            "small": (3, 7, 9),
            "empty": (),
            "large": range(100_000),
        }
    )

    assert CACHE_VERSION == 6
    assert is_compact_index(first)
    assert len(first["offsets"]) == len(first["keys"]) + 1
    assert first["offsets"][-1] == len(first["values"])
    assert list(compact_index_get(first, "empty")) == []
    assert list(compact_index_get(first, "small")) == [3, 7, 9]
    assert len(compact_index_get(first, "large")) == 100_000
    assert compact_index_get(first, "missing") is None
    assert pickle.dumps(first) == pickle.dumps(second)

    with pytest.raises(OverflowError):
        build_compact_index({"overflow": (UINT32_MAX + 1,)})


def test_six_csv_search_and_deduplication(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    result = store.search(request("髪"))
    assert result["count"] >= 1
    assert result["results"][0][0] == "long_hair"
    assert "長髪" in result["results"][0][4]
    assert result["total"] == 6


def test_natural_language_mode_ranking_and_insert_metadata(
    tmp_path: Path,
) -> None:
    store = create_six_file_fixture(tmp_path)
    result = store.search(
        request("soft", prompt_mode="Natural Language")
    )
    first = result["results"][0]
    assert first[0] == "soft natural lighting"
    assert first[5] == "natural_language"
    assert first[6] == "phrase"


def test_candidate_sort_modes_keep_csv_order_or_rank_relevance(
    tmp_path: Path,
) -> None:
    data = DataStore(tmp_path / "tags")
    write(
        data.tag_dir / "order.csv",
        "tag,category,count\n"
        "tag_z,0,1\n"
        "tag_a,0,100\n"
        "tag_b,0,10\n",
    )
    store = FastSearchStore(data)
    common = dict(
        query="tag",
        tag_files=["order.csv"],
        translation_files=[],
        prompt_mode="Custom",
        limit=10,
    )
    legacy = store.search(SearchRequest(**common, candidate_sort_mode="Legacy"))
    relevance = store.search(SearchRequest(**common, candidate_sort_mode="Relevance"))
    assert [row[0] for row in legacy["results"]] == ["tag_z", "tag_a", "tag_b"]
    assert [row[0] for row in relevance["results"]] == ["tag_a", "tag_b", "tag_z"]


def test_source_metadata_is_optional(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    without_sources = store.search(
        request("long", include_sources=False)
    )["results"][0]
    with_sources = store.search(
        request("long", include_sources=True)
    )["results"][0]
    assert without_sources[8] == []
    assert with_sources[8] == [
        "danbooru.csv",
        "danbooru_ja.csv",
    ]


def test_persistent_index_is_reused_after_restart(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    first = store.search(request("blue"))
    assert first["cache"] == "build"
    assert first["build_ms"] == first["original_build_ms"]
    assert first["restore_ms"] == 0.0
    assert 0.0 <= first["search_only_ms"] <= first["search_ms"]

    restarted = FastSearchStore(store.data_store)
    second = restarted.search(request("blue"))
    assert second["cache"] == "disk"
    assert second["results"][0][0] == "blue_eyes"
    assert second["build_ms"] == second["original_build_ms"]
    assert second["original_build_ms"] == first["original_build_ms"]
    assert second["restore_ms"] >= 0.0
    assert 0.0 <= second["search_only_ms"] <= second["search_ms"]

    third = restarted.search(request("blue"))
    assert third["cache"] == "memory"
    assert third["restore_ms"] == 0.0


def test_csv_change_invalidates_compiled_index(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    store.search(request("blue"))
    path = store.data_store.tag_dir / "custom.csv"
    time.sleep(0.002)
    write(
        path,
        path.read_text(encoding="utf-8")
        + "new_value,10,new alias,custom\n",
    )
    os.utime(path, None)
    result = store.search(
        request(
            "new",
            tag_files=["custom.csv"],
            translation_files=[],
        )
    )
    assert result["cache"] == "build"
    assert result["results"][0][0] == "new_value"


def test_single_flight_build_for_concurrent_first_queries(
    tmp_path: Path,
) -> None:
    store = create_six_file_fixture(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(store.search, request("long"))
            for _ in range(4)
        ]
        results = [
            future.result(timeout=10)
            for future in futures
        ]
    assert all(
        item["results"][0][0] == "long_hair"
        for item in results
    )
    assert store.build_count == 1


def test_result_limit_is_enforced(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    result = store.search(request("i", limit=2))
    assert result["count"] <= 2


def test_search_flags_exclude_aliases_and_translations(
    tmp_path: Path,
) -> None:
    store = create_six_file_fixture(tmp_path)
    translation_off = store.search(
        request(
            "長髪",
            search_translations=False,
            search_aliases=False,
        )
    )
    assert translation_off["results"] == []

    alias_off = store.search(
        request(
            "longhair",
            search_aliases=False,
            search_translations=False,
        )
    )
    assert alias_off["results"] == []

    alias_on = store.search(
        request(
            "longhair",
            search_aliases=True,
            search_translations=False,
        )
    )
    assert alias_on["results"][0][0] == "long_hair"


def test_substring_query_uses_blob_fallback(tmp_path: Path) -> None:
    store = create_six_file_fixture(tmp_path)
    result = store.search(
        request("trait", substring_only=True)
    )
    assert result["results"][0][0] == "portrait lighting"


def test_disk_cache_write_failure_falls_back_to_memory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = create_six_file_fixture(tmp_path)

    def fail_write(*_args, **_kwargs):
        raise OSError("read only")

    monkeypatch.setattr(store, "_atomic_pickle", fail_write)
    result = store.search(request("long"))
    assert result["results"][0][0] == "long_hair"
    assert store._disk_cache_available is False
    second = store.search(request("long"))
    assert second["cache"] == "memory"
