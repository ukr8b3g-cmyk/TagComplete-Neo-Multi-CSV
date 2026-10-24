"""Exercise the real route without importing Forge or starting its services."""

import ast
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class _Response:
    def __init__(self, content=None, status_code=200):
        self.content = content
        self.status_code = status_code


class _FileResponse(_Response):
    def __init__(self, path):
        super().__init__()
        self.path = Path(path)


def load_handler(file_dir, roots):
    source = ROOT / "scripts" / "tag_autocomplete_helper.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    route = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "get_wildcard_contents")
    route.decorator_list = []
    namespace = {
        "Path": Path,
        "sys": sys,
        "FILE_DIR": file_dir,
        "WILDCARD_PATH": roots[0],
        "WILDCARD_EXT_PATHS": roots[1:],
        "Response": _Response,
        "JSONResponse": _Response,
        "FileResponse": _FileResponse,
    }
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["get_wildcard_contents"]


class WildcardApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tagcomplete-wildcard-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.webui = self.root / "webui"
        self.normal = self.webui / "scripts" / "wildcards"
        self.external = self.root / "external wildcards"
        self.private = self.root / "private"
        for directory in (self.normal, self.external, self.private):
            directory.mkdir(parents=True)
        for directory in (self.normal, self.external):
            (directory / "nested").mkdir()
            (directory / "nested" / "colors.txt").write_text("red\nblue\n", encoding="utf-8")
            (directory / "marker.json").write_text('{"private":true}', encoding="utf-8")
        (self.private / "marker.txt").write_text("outside marker", encoding="utf-8")
        self.handler = load_handler(self.webui, [self.normal, self.external])

    def request(self, base, filename):
        return asyncio.run(self.handler(str(base), str(filename)))

    def test_legitimate_roots_and_nested_files(self):
        for base in (self.normal, self.external, "scripts/wildcards", "scripts/wildcards/."):
            with self.subTest(base=base):
                result = self.request(base, "nested/colors.txt")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.path.read_text(encoding="utf-8"), "red\nblue\n")

    def test_arbitrary_base_and_subdirectory_base_are_forbidden(self):
        for base in (self.private, self.normal / "nested", self.root / "missing"):
            with self.subTest(base=base):
                self.assertEqual(self.request(base, "marker.txt").status_code, 403)

    def test_traversal_and_sibling_prefix_are_forbidden(self):
        sibling = self.normal.with_name("wildcards-private")
        sibling.mkdir()
        (sibling / "marker.txt").write_text("sibling marker", encoding="utf-8")
        for filename in ("../wildcards-private/marker.txt", "../../../private/marker.txt"):
            with self.subTest(filename=filename):
                self.assertEqual(self.request(self.normal, filename).status_code, 403)

    def test_absolute_and_anchored_filenames_are_forbidden(self):
        filenames = [self.normal / "nested" / "colors.txt", self.private / "marker.txt"]
        if os.name == "nt":
            filenames += [r"\nested\colors.txt", r"C:colors.txt"]
        for filename in filenames:
            with self.subTest(filename=filename):
                self.assertEqual(self.request(self.normal, filename).status_code, 403)

    def test_only_text_wildcards_are_served(self):
        for filename in ("marker.json", "nested/colors.txt.json"):
            with self.subTest(filename=filename):
                self.assertEqual(self.request(self.normal, filename).status_code, 403)

    @unittest.skipUnless(os.name == "nt", "Windows alternate data streams")
    def test_alternate_stream_cannot_disguise_non_text_file(self):
        filename = "marker.json:stream.txt"
        (self.normal / filename).write_text("stream marker", encoding="utf-8")
        self.assertEqual(self.request(self.normal, filename).status_code, 403)

    @unittest.skipIf(os.name == "nt", "POSIX filenames permit colons")
    def test_posix_colon_filename_remains_supported(self):
        filename = "artist:name.txt"
        (self.normal / filename).write_text("artist marker", encoding="utf-8")
        result = self.request(self.normal, filename)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path.read_text(encoding="utf-8"), "artist marker")

    def test_missing_and_empty_requests_keep_not_found_response(self):
        self.assertEqual(self.request(self.normal, "missing.txt").status_code, 404)
        self.assertEqual(self.request("", "colors.txt").status_code, 404)
        self.assertEqual(self.request(self.normal, "").status_code, 404)

    def test_directory_link_cannot_escape_root(self):
        link = self.normal / "linked"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.private)],
                           check=True, capture_output=True)
        else:
            link.symlink_to(self.private, target_is_directory=True)
        self.assertEqual(self.request(self.normal, "linked/marker.txt").status_code, 403)


if __name__ == "__main__":
    unittest.main()
