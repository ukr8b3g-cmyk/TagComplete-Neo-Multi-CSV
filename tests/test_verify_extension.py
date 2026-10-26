"""The README verifier must accept the current distribution, not retired CSVs."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verify_extension', ROOT / 'tools/verify_extension.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

class VerifyLayoutTests(unittest.TestCase):
    def test_current_checkout_without_retired_csv_passes(self):
        self.assertFalse((ROOT / 'tags/tag_files/danbooru_2025.csv').exists())
        verifier.check_layout()

    def test_missing_merged_csv_is_rejected_even_if_retired_csv_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in verifier.REQUIRED:
                if name == 'tags/tag_files/tags_merged_dedup.csv':
                    continue
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (root / 'tags/tag_files/danbooru_2025.csv').touch()
            with patch.object(verifier, 'ROOT', root):
                with self.assertRaisesRegex(SystemExit, 'Missing required files: tags/tag_files/tags_merged_dedup.csv'):
                    verifier.check_layout()

if __name__ == '__main__':
    unittest.main()
