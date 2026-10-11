"""Exercise real embedding discovery without importing Forge or model tensors."""
# SPDX-License-Identifier: MIT
import ast
from contextlib import redirect_stdout
import csv
from io import StringIO
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class EmbeddingCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.model = None
        self.rows = []
        modules = ModuleType("modules")
        self.classic = SimpleNamespace(embedding_db=None)
        modules.sd_hijack = SimpleNamespace(model_hijack=self.classic)
        self.module_patch = patch.dict(sys.modules, {"modules": modules})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.scope = {
            "Path": Path,
            "sd_models": SimpleNamespace(model_data=SimpleNamespace(get_sd_model=lambda: self.model)),
            "shared": SimpleNamespace(sd_model=None, opts=SimpleNamespace(tac_modelSortOrder="Name")),
            "EMB_PATH": self.root,
            "load_textual_inversion_embeddings": lambda: None,
            "write_to_temp_file": lambda name, rows: self.rows.extend(rows),
        }
        tree = ast.parse((ROOT / "scripts/tag_autocomplete_helper.py").read_text(encoding="utf-8-sig"))
        names = {"get_embed_db", "sort_models", "get_embeddings", "get_embeddings_from_folder"}
        constants = {"EMBED_ENGINE_ATTRS", "EMB_FILE_EXTENSIONS", "sort_criteria"}
        nodes = [node for node in tree.body if
                 (isinstance(node, ast.FunctionDef) and node.name in names)
                 or (isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id in constants for target in node.targets))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "<embedding discovery>", "exec"), self.scope)

    def file(self, name, contents=b"synthetic"):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
        return target

    def database(self, loaded=None, skipped=None):
        return SimpleNamespace(word_embeddings=loaded or {}, skipped_embeddings=skipped or {},
                               load_textual_inversion_embeddings=lambda: None)

    def export(self, model=None):
        output = StringIO()
        with redirect_stdout(output):
            self.scope["get_embeddings"](model)
        return list(csv.reader(self.rows)), output.getvalue()

    def test_refiner_uses_g_engine_registry(self):
        registry = self.database()
        model = SimpleNamespace(text_processing_engine_g=SimpleNamespace(embeddings=registry))
        self.assertIs(self.scope["get_embed_db"](model), registry)

    def test_refiner_export_retains_registry_metadata(self):
        embedding = SimpleNamespace(filename=self.file("nested/refiner.pt"), shape=1280)
        registry = self.database({"refiner": embedding})
        model = SimpleNamespace(text_processing_engine_g=SimpleNamespace(embeddings=registry))
        rows, warning = self.export(model)
        self.assertEqual(rows, [["nested/refiner.pt", "refiner", ""]])
        self.assertEqual(warning, "")

    def test_missing_plain_engine_does_not_shadow_l_registry(self):
        registry = self.database()
        model = SimpleNamespace(text_processing_engine=None,
                                text_processing_engine_l=SimpleNamespace(embeddings=registry))
        self.assertIs(self.scope["get_embed_db"](model), registry)

    def test_plain_engine_priority_is_preserved(self):
        registry = self.database()
        model = SimpleNamespace(text_processing_engine=SimpleNamespace(embeddings=registry),
                                text_processing_engine_l=SimpleNamespace(embeddings=self.database()))
        self.assertIs(self.scope["get_embed_db"](model), registry)

    def test_no_model_argument_uses_the_current_neo_model(self):
        registry = self.database()
        self.model = SimpleNamespace(text_processing_engine_g=SimpleNamespace(embeddings=registry))
        self.assertIs(self.scope["get_embed_db"](), registry)

    def test_classic_hijack_registry_fallback_is_preserved(self):
        self.classic.embedding_db = self.database()
        self.assertIs(self.scope["get_embed_db"](SimpleNamespace()), self.classic.embedding_db)

    def test_no_embedding_support_is_silent(self):
        rows, warning = self.export(SimpleNamespace(text_processing_engine=SimpleNamespace()))
        self.assertEqual(rows, [])
        self.assertEqual(warning, "")

    def test_folder_fallback_accepts_safetensors_and_case_insensitive_extensions(self):
        for name in ("nested/safe.v1.safetensors", "upper.SAFETENSORS", "legacy.PT", "normal.pt",
                     "image.png", "binary.bin", "picture_webp.webp", "picture_jxl.jxl", "picture_avif.avif"):
            self.file(name)
        self.file("empty.safetensors", b"")
        self.file("unrelated.txt")
        (self.root / "directory.safetensors").mkdir()
        rows, warning = self.export()
        self.assertEqual({row[0] for row in rows}, {
            "nested/safe.v1", "upper", "legacy", "normal", "image", "binary",
            "picture_webp", "picture_jxl", "picture_avif"})
        self.assertTrue(all(len(row) == 2 and row[1] == "" for row in rows))
        self.assertEqual(warning, "")

    def test_folder_scan_error_warns_and_exports_an_empty_fallback(self):
        with patch.object(Path, "rglob", side_effect=OSError("synthetic scan failure")):
            rows, warning = self.export()
        self.assertEqual(rows, [])
        self.assertIn("Error scanning embeddings folder", warning)
        self.assertIn("synthetic scan failure", warning)

    def test_known_registry_versions_and_loaded_precedence_are_preserved(self):
        make = lambda shape: SimpleNamespace(filename=None, shape=shape)
        registry = self.database({"v1": make(768), "v2": make(1024), "vxl": make(2048)},
                                 {"v1": make(1024), "unknown": make(None)})
        self.model = SimpleNamespace(text_processing_engine=SimpleNamespace(embeddings=registry))
        rows, warning = self.export()
        self.assertEqual({row[0]: row[2] for row in rows},
                         {"v1": "v1", "v2": "v2", "vxl": "vXL", "unknown": ""})
        self.assertEqual(warning, "")

    def test_unexpected_registry_structure_keeps_a_specific_warning(self):
        self.file("recovered.safetensors")
        broken = SimpleNamespace(load_textual_inversion_embeddings=lambda: None)
        self.model = SimpleNamespace(text_processing_engine=SimpleNamespace(embeddings=broken))
        rows, warning = self.export()
        self.assertEqual(rows, [["recovered", ""]])
        self.assertIn("Unexpected embedding database structure", warning)
        self.assertNotIn("Old webui version", warning)


if __name__ == "__main__":
    unittest.main()
