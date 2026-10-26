import csv
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.jp_assist_core import DataStore
from scripts.tacjp_fast_search import FastSearchStore, SearchRequest

class HitCountTest(unittest.TestCase):
    def test_count_before_pool_limit_and_field_switches(self):
        with tempfile.TemporaryDirectory() as folder:
            data = DataStore(Path(folder) / 'tags')
            data.tag_dir.mkdir(parents=True, exist_ok=True)
            data.translation_dir.mkdir(parents=True, exist_ok=True)
            with (data.tag_dir / 'fixture.csv').open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['tag', 'category', 'count', 'aliases'])
                writer.writerows((f'temple_{i}', 0, 100-i, 'temple,temple building') for i in range(50))
                writer.writerow(['alias_only', 0, 1, 'temple'])
                writer.writerow(['translated_only', 0, 1, ''])
            with (data.translation_dir / 'ja.csv').open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream);writer.writerow(['tag','ja']);writer.writerow(['translated_only','temple'])
            store = FastSearchStore(data)
            for mode in ['Count','Legacy','Relevance']:
                for aliases,translations,total in [(True,True,52),(False,True,51),(True,False,51),(False,False,50)]:
                    result = store.search(SearchRequest(query='temple', tag_files=['fixture.csv'], translation_files=['ja.csv'], limit=20, candidate_sort_mode=mode, search_aliases=aliases, search_translations=translations, persistent_cache=False))
                    self.assertEqual(result['matched_count'], total, (mode,aliases,translations))
                    self.assertEqual(len(result['results']),20)
            result = store.search(SearchRequest(query='no_match', tag_files=['fixture.csv'], translation_files=['ja.csv'], persistent_cache=False))
            self.assertEqual(result['matched_count'],0)

if __name__ == '__main__': unittest.main()
