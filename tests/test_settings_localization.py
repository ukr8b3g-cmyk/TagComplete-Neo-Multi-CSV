import ast
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SettingsDescriptions(unittest.TestCase):
    def test_visible_setting_labels_have_translations(self):
        source = (ROOT / 'javascript/zz_jpAssistUI.js').read_text(encoding='utf-8-sig')
        table = source.split('const TACJP_CORE_LABELS = {', 1)[1].split('\n};', 1)[0]
        keys = {quoted or bare for quoted, bare in re.findall(r'^\s*(?:"([^"]+)"|(\w+)):\s*\[', table, re.M)}
        for path in (ROOT / 'scripts').glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            definitions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    definitions.extend((key.value, value) for key, value in zip(node.keys, node.values)
                                       if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value.startswith('tac'))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_option' and len(node.args) > 1 and isinstance(node.args[0], ast.Constant):
                    definitions.append((node.args[0].value, node.args[1]))
            for key, value in definitions:
                options = [node for node in ast.walk(value) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'OptionInfo']
                if not options or len(options[0].args) < 2 or not isinstance(options[0].args[1], ast.Constant):
                    continue
                hidden = any(isinstance(node, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == 'visible' and isinstance(v, ast.Constant) and v.value is False
                             for k, v in zip(node.keys, node.values)) for node in ast.walk(options[0]))
                if not hidden:
                    with self.subTest(file=path.name, option=key):
                        self.assertIn(key, keys)

    def test_every_backend_inline_description_has_a_japanese_translation(self):
        source = (ROOT / 'javascript/zz_jpAssistUI.js').read_text(encoding='utf-8-sig')
        table = source.split('const TACJP_INFO_LABELS = [', 1)[1].split('\n];', 1)[0]
        pairs = re.findall(r'\[\s*("(?:\\.|[^"\\])*")\s*,\s*("(?:\\.|[^"\\])*")\s*,?\s*\]', table)
        translations = {json.loads(en): json.loads(ja) for en, ja in pairs}
        descriptions = []
        for path in (ROOT / 'scripts').glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'info':
                    descriptions.append((path.name, node.lineno, ast.literal_eval(node.args[0])))
        self.assertTrue(descriptions, 'No backend descriptions were inspected')
        for path, line, description in descriptions:
            with self.subTest(file=path, line=line):
                key = f'({description})'
                self.assertIn(key, translations, f'Missing translation: {description}')
                self.assertRegex(translations[key], r'[ぁ-んァ-ン一-龯]')
        for notice in ['(requires restart)', '(requires Reload UI)']:
            self.assertIn(notice, translations)


if __name__ == '__main__':
    unittest.main()
