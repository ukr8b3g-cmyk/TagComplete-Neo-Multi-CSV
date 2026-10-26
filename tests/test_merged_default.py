import ast,unittest,tempfile,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.jp_assist_core import DataStore, PresetStore

class DefaultsTest(unittest.TestCase):
    def test_merged_initial_and_presets(self):
        with tempfile.TemporaryDirectory() as folder:
            data=DataStore(Path(folder));data.tag_dir.mkdir(parents=True,exist_ok=True)
            for name in ['e621.csv','natural_language_tags.csv','tags_merged_dedup.csv']:(data.tag_dir/name).write_text('tag,category,count\nblue,0,1\n',encoding='utf-8')
            source=Path(__file__).resolve().parents[1]/'scripts/tag_autocomplete_helper.py'
            tree=ast.parse(source.read_text(encoding='utf-8-sig'))
            names=['_default_tag_selection','_migrate_legacy_danbooru_selection']
            subset=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
            writes=[];opts=SimpleNamespace(data={},save=lambda p:writes.append(p));shared=SimpleNamespace(opts=opts,config_filename='fixture')
            scope={'JP_DATA':data,'shared':shared};exec(compile(subset,str(source),'exec'),scope)
            self.assertEqual(scope['_default_tag_selection'](),['tags_merged_dedup.csv'])
            presets=PresetStore(data).default_presets()
            for key in ['Danbooru','SDXL','Illustrious','Custom']:self.assertEqual(presets[key]['tag_files'],['tags_merged_dedup.csv'])
            opts.data['tacjp_tagFiles']=['danbooru_2025.csv','natural_language_tags.csv','tags_merged_dedup.csv'];scope[names[1]]()
            self.assertEqual(opts.data['tacjp_tagFiles'],['tags_merged_dedup.csv','natural_language_tags.csv']);self.assertEqual(len(writes),1)
            opts.data['tacjp_tagFiles']=[];scope[names[1]]();self.assertEqual(opts.data['tacjp_tagFiles'],[]);self.assertEqual(len(writes),1)

if __name__=='__main__':unittest.main()
