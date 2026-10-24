"""Focused P2 contracts, using temporary CSVs/SQLite and the actual JS consumer."""

import ast
import asyncio
from contextlib import redirect_stdout
from datetime import datetime
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from scripts.jp_assist_core import DataStore
from scripts.tacjp_fast_search import FastSearchStore, SearchRequest

ROOT = Path(__file__).resolve().parents[1]


def node_json(code, payload):
    result = subprocess.run(["node", "-e", code, str(ROOT)],
                            input=json.dumps(payload), text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def map_api_response(response, both=False):
    return node_json(r"""
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(process.argv[1],'javascript/_utils.js'),'utf8');
const start=source.indexOf('function mapUseCountArray(');
const context={};vm.runInNewContext(source.slice(start,source.indexOf('\n}',start)+2),context);
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(context.mapUseCountArray(payload.response.result,payload.both)));
""", {"response": response, "both": both})


class FrequencyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tagcomplete-frequency-")
        self.addCleanup(self.temp.cleanup)
        tree = ast.parse((ROOT / "scripts/tag_frequency_db.py").read_text(encoding="utf-8"))
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.ImportFrom) and node.module == "scripts.shared_paths")]
        namespace = {"TAGS_PATH": Path(self.temp.name)}
        exec(compile(tree, "tag_frequency_db.py", "exec"), namespace)
        with redirect_stdout(io.StringIO()):
            self.db = namespace["TagFrequencyDb"]()
        helper = ROOT / "scripts/tag_autocomplete_helper.py"
        tree = ast.parse(helper.read_text(encoding="utf-8"))
        names = {"db_request", "get_use_count", "get_use_count_list",
                 "get_all_tag_counts", "reset_use_count"}
        nodes = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in names]
        for node in nodes:
            node.decorator_list = []
        def response(content, **_kwargs):
            return json.loads(json.dumps(content))
        self.api = {
            "db": self.db, "sqlite3": sqlite3, "JSONResponse": response,
            "UseCountListRequest": SimpleNamespace,
            "shared": SimpleNamespace(opts=SimpleNamespace(
                tac_frequencyMaxAge=30, tac_frequencyRecommendCap=10)),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(helper), "exec"), self.api)

    def call(self, name, *args):
        return asyncio.run(self.api[name](*args))

    def seed(self):
        for negative, count in ((False, 2), (True, 3)):
            for _ in range(count):
                self.db.increase_tag_count("long_hair", 1, negative)

    def test_positive_negative_lists_reach_the_real_js_mapper(self):
        self.seed()
        for negative, count in ((False, 2), (True, 3)):
            with self.subTest(negative=negative):
                result = self.call("get_use_count_list", SimpleNamespace(
                    tagNames=["long_hair"], tagTypes=[1], neg=negative))
                mapped = map_api_response(result)[0]
                self.assertEqual((mapped.get("name"), mapped.get("type"), mapped.get("count")),
                                 ("long_hair", 1, count))
                datetime.fromisoformat(mapped["lastUseDate"])

    def test_all_counts_keep_both_counts_date_and_reset_identity(self):
        self.seed()
        mapped = map_api_response(self.call("get_all_tag_counts"), both=True)[0]
        self.assertEqual((mapped.get("name"), mapped.get("type"), mapped.get("count"),
                          mapped.get("negCount")), ("long_hair", 1, 2, 3))
        datetime.fromisoformat(mapped["lastUseDate"])
        self.call("reset_use_count", mapped["name"], mapped["type"], True, False)
        after = map_api_response(self.call("get_all_tag_counts"), both=True)[0]
        self.assertEqual((after["count"], after["negCount"]), (0, 3))
        self.call("reset_use_count", mapped["name"], mapped["type"], False, True)
        self.assertEqual(map_api_response(self.call("get_all_tag_counts"), both=True), [])

    def test_single_count_and_missing_tags_keep_their_contract(self):
        self.assertEqual(self.call("get_use_count", "missing", 1, False)["result"], [0, None])
        response = self.call("get_use_count_list", SimpleNamespace(
            tagNames=["missing"], tagTypes=[1], neg=False))
        self.assertEqual(map_api_response(response), [
            {"name": "missing", "type": 1, "count": 0, "lastUseDate": None}])


class SearchRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tagcomplete-search-")
        self.addCleanup(self.temp.cleanup)
        self.data = DataStore(Path(self.temp.name) / "tags")

    def write(self, name, rows, *, translation=False):
        directory = self.data.translation_dir if translation else self.data.tag_dir
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(rows, encoding="utf-8")

    def search(self, query, **options):
        values = dict(query=query, tag_files=["tags.csv"], prompt_mode="Custom",
                      candidate_sort_mode="Legacy", limit=20, persistent_cache=False)
        values.update(options)
        return FastSearchStore(self.data).search(SearchRequest(**values))["results"]

    def browser(self, query, files, **config):
        payload = {"query": query, "rows": self.data.merge(files), "config": config}
        result = subprocess.run(["node", str(ROOT / "tests/test_p2_regressions.js"),
                                 "--browser-search"], input=json.dumps(payload),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_legacy_keeps_leading_and_middle_infix_at_limit(self):
        for query in ("b", "ba", "ban"):
            for prefix_count in (20, 23):
                with self.subTest(query=query, prefix_count=prefix_count):
                    tags = [f"z{query}"] + [f"{query}_{i:02}" for i in range(prefix_count)]
                    tags.insert(10, f"x{query}x")
                    self.write("tags.csv", "tag,category,count\n" + "\n".join(
                        f"{tag},0,{i}" for i, tag in enumerate(tags)) + "\n")
                    expected = tags[:20]
                    self.assertEqual([row[0] for row in self.search(query)], expected)
                    self.assertEqual(self.browser(query, ["tags.csv"]), expected)

    def test_legacy_keeps_selected_file_and_prompt_source_priority(self):
        self.write("tags.csv", "tag,category,count\nzba,0,1\n" + "\n".join(
            f"ba_{i},0,1" for i in range(25)) + "\n")
        self.write("natural_language.csv", "tag,source_type\nsoft ba,natural_language\n")
        files = ["tags.csv", "natural_language.csv"]
        for mode in ("Custom", "Tag", "Natural Language", "Hybrid"):
            with self.subTest(mode=mode):
                rows = self.search("ba", tag_files=files, prompt_mode=mode)
                expected = ["soft ba", "zba"] if mode == "Natural Language" else ["zba", "ba_0"]
                self.assertEqual([row[0] for row in rows[:2]], expected)
                self.assertEqual(self.browser("ba", files, promptMode=mode), [row[0] for row in rows])

    def test_count_and_relevance_still_use_their_own_ranking(self):
        self.write("tags.csv", "tag,category,count\nzba,0,999\nba,0,1\nba_tail,0,20\n")
        for mode, expected in (("Count", ["zba", "ba_tail", "ba"]),
                               ("Relevance", ["ba", "ba_tail", "zba"])):
            with self.subTest(mode=mode):
                rows = self.search("ba", candidate_sort_mode=mode)
                self.assertEqual([row[0] for row in rows], expected)

    def test_translation_display_survives_search_flags(self):
        self.write("tags.csv", "tag,category,count,aliases\nlong_hair,0,9,longhair\n")
        self.write("ja.csv", "tag,ja\nlong_hair,長髪\n", translation=True)
        for translations in (False, True):
            for aliases in (False, True):
                with self.subTest(translations=translations, aliases=aliases):
                    options = dict(translation_files=["ja.csv"], search_translations=translations,
                                   search_aliases=aliases)
                    self.assertEqual(self.search("long_hair", **options)[0][4], "長髪")
                    self.assertEqual(bool(self.search("長髪", **options)), translations)
                    self.assertEqual(bool(self.search("longhair", **options)), aliases)


if __name__ == "__main__":
    unittest.main()
