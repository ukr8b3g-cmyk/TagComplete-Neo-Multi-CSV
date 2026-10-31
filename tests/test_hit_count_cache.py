import concurrent.futures
import csv
import itertools
import pickle
from dataclasses import replace
from pathlib import Path

from scripts.jp_assist_core import DataStore
from scripts.tacjp_fast_search import FastSearchStore, SearchRequest
from scripts.tacjp_fast_search_common import normalize_search


def fixture(tmp_path):
    data = DataStore(tmp_path / "tags")
    data.tag_dir.mkdir(parents=True, exist_ok=True)
    data.translation_dir.mkdir(parents=True, exist_ok=True)
    with (data.tag_dir / "a.csv").open("w", encoding="utf8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tag", "category", "count", "aliases"])
        writer.writerows((f"a_temple_{i}", 0, 1000-i, "temple,building") for i in range(300))
        writer.writerows((f"unrelated_{i}", 0, i, "") for i in range(1700))
        writer.writerow(["alias_only", 0, 1, "temple,blue eyes"])
        writer.writerow(["translated_only", 0, 1, ""])
        writer.writerow(["長髪", 0, 2, ""])
        writer.writerow(["abcbcd", 0, 3, "abc,bcd"])
    with (data.translation_dir / "ja.csv").open("w", encoding="utf8", newline="") as stream:
        writer = csv.writer(stream);writer.writerow(["tag", "ja"])
        writer.writerow(["translated_only", "temple,青い目"])
        writer.writerow(["a_temple_0", "temple,寺院"])
    store = FastSearchStore(data)
    request = SearchRequest(query="temple", tag_files=["a.csv"], translation_files=["ja.csv"], limit=20)
    store.warmup(request.tag_files, request.translation_files, persistent=True, memory_entries=4, disk_entries=8)
    return store, request, next(iter(store._memory.values()))


def oracle(index, query, aliases, translations):
    return sum(query in tag or (aliases and query in alias) or (translations and query in translation)
               for tag, alias, translation in index["search_blobs"])


def test_counts_match_full_scan_across_modes_flags_and_limits(tmp_path):
    store, base, index = fixture(tmp_path)
    cases = itertools.product(["temple", "a", "_", "a_", "ab", "abcd", "長", "髪", "青い", "BLUE_EYES", "absent", "寺 院"],
                              [True, False], [True, False], ["Legacy", "Count", "Relevance"], [1, 20, 250])
    for query, aliases, translations, mode, limit in cases:
        request = replace(base, query=query, search_aliases=aliases, search_translations=translations, candidate_sort_mode=mode, limit=limit)
        result = store.search(request)
        normalized = normalize_search(query, preserve_trailing_separator=True)
        expected = oracle(index, normalized, aliases, translations) if normalized else 0
        assert result["matched_count"] == expected, (query, aliases, translations, mode, limit)
        assert result["count_ms"] >= 0


class CountedBlobs(list):
    def __init__(self, values):
        super().__init__(values)
        self.iterations = 0
        self.accesses = []

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()

    def __getitem__(self, key):
        self.accesses.append(key)
        return super().__getitem__(key)


def test_complete_candidates_count_only_prefiltered_rows(tmp_path):
    store, request, index = fixture(tmp_path)
    blobs = index["search_blobs"] = CountedBlobs(index["search_blobs"])
    ids, complete = store._candidate_ids(index, request.query, False)
    assert complete and len(ids) < len(index["rows"])
    assert store.search(request)["matched_count"] == 302
    assert blobs.iterations == 0
    assert len(blobs.accesses) <= len(ids) + 1
    assert store.search(replace(request, query="abcd"))["matched_count"] == 0, "gram intersections can contain false positives"


def test_short_query_reuses_count_across_rank_mode_and_pool(tmp_path):
    store, request, index = fixture(tmp_path)
    blobs = index["search_blobs"] = CountedBlobs(index["search_blobs"])
    request = replace(request, query="a")
    first = store.search(request)
    assert blobs.iterations == 1, "an incomplete short-query prefilter still needs an exact full count"
    store.search(replace(request, limit=1, substring_only=True))
    assert blobs.iterations == 1
    for mode in ["Legacy", "Count", "Relevance"]:
        assert store.search(replace(request, candidate_sort_mode=mode, limit=250))["matched_count"] == first["matched_count"]
    # Legacy/relevance may iterate blobs to rank, but the count itself is cached.
    cached = index["_matched_counts"][("a", True, True)]
    assert cached == first["matched_count"]


def test_flags_revision_clear_and_disk_restore_do_not_reuse_stale_counts(tmp_path):
    store, request, old_index = fixture(tmp_path)
    assert store.search(request)["matched_count"] == 302
    assert store.search(replace(request, search_aliases=False, search_translations=False))["matched_count"] == 300
    payload = pickle.loads(next(store.index_cache_dir.glob("*.pkl")).read_bytes())
    assert "_matched_counts" not in payload
    store.clear(disk=False)
    restored = store.search(request)
    assert restored["cache"] == "disk" and restored["matched_count"] == 302
    assert next(iter(store._memory.values())) is not old_index
    path = store.data_store.tag_dir / "a.csv"
    with path.open("a", encoding="utf8", newline="") as stream:
        csv.writer(stream).writerow(["new_temple", 0, 1, ""])
    assert store.search(request)["matched_count"] == 303


def test_count_cache_is_bounded_and_thread_safe(tmp_path):
    store, request, index = fixture(tmp_path)
    requests = [replace(request, query=f"absent_{i}") for i in range(160)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(store.search, requests + [request] * 8))
    assert all(result["matched_count"] == 0 for result in results[:160])
    assert all(result["matched_count"] == 302 for result in results[160:])
    assert len(index["_matched_counts"]) <= 128


def test_legacy_field_count_and_missing_field_fallback(tmp_path):
    store, request, index = fixture(tmp_path)
    grouped = {**index, "search_blobs": []}
    assert store._matched_count(grouped, "temple", True, True, None, 0) == 302
    legacy = {"search_blobs": [], "fields": [("temple", "temple"), ("different",)]}
    assert store._matched_count(legacy, "temple", True, True, None, 0) == 1
    assert store._matched_count({"search_blobs": []}, "x", True, True, None, 7) == 7
    assert store._matched_count({"search_blobs": []}, "x", True, True, None, 2) == 2
