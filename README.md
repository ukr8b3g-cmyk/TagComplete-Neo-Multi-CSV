<div align="center">

# TagComplete Neo Multi-CSV

**Forge / Forge Neo向け、複数CSV・翻訳検索・自然言語辞書対応のタグ補完拡張**

A Forge / Forge Neo fork of TagComplete Neo with multiple CSV sources,
separate translation files, Japanese/translated search, natural-language
vocabularies, presets, and safe prompt insertion.

</div>

> このプロジェクトは `sd-webui-tagcomplete-neo` を基盤としたフォークです。<br>
> 候補ポップアップ、キーボード操作、カテゴリ色、LoRA・Embedding・Wildcard・Chantなど、
> TagComplete Neoの操作感を維持しながら、Danbooru Tag JP Assistの辞書管理方式を統合しています。

---

## 日本語

### 対応環境

- Stable Diffusion WebUI Forge
- Stable Diffusion WebUI Forge Neo
- Gradio 3系・4系で異なる主要DOM構造を考慮

主な用途:

- SDXL、Illustrious XL、Ponyなどのタグ中心モデル
- Animaなどのタグ・自然言語ハイブリッドモデル
- Krea 2、Z-Image、FLUX、Qwen-Imageなどの自然言語中心モデル

モデルごとに辞書を強制固定しません。プリセットは推奨設定の呼び出しに使い、
最終的なCSV・モード・挿入形式はユーザーが変更できます。

### 主な機能

#### TagComplete Neoから維持する機能

- 入力中の候補ポップアップ
- 矢印キー、Tab、Enter、Escapeによる操作
- Danbooru / e621カテゴリ色と投稿数表示
- Alias・翻訳検索
- 使用頻度による候補順位調整
- 高速インデックス検索
- LoRA / LyCORIS / Embedding補完
- Extra Networkサムネイル
- LoRAトリガーワード挿入とCivitAI照会
- Dynamic Prompts形式のWildcard補完
- YAML Wildcard / UMI対応
- Chant補完
- モバイル向け入力負荷軽減

#### Multi-CSV版で追加した機能

- タグCSVと翻訳CSVを別フォルダで管理
- タグCSVを複数選択
- 翻訳CSVを複数選択
- Danbooru、自然言語、ユーザー辞書の同時利用
- 同一タグ、Alias、翻訳の統合
- 日本語・他言語翻訳による検索
- 日本語・翻訳表示のON/OFF
- `Tag` / `Hybrid` / `Natural Language` / `Custom`モード
- 標準プリセットとユーザープリセット
- プリセットの保存、上書き、複製、名前変更、削除
- プリセットJSONのバックアップ・読み込み
- プロンプト欄付近の折りたたみ式簡易設定
- アンダースコア保護パターンのワイルドカード指定
- 条件付きリモートCSV更新とオフライン継続利用

### インストール

1. ZIPを展開します。
2. フォルダ名が次の形になるように配置します。

```text
stable-diffusion-webui-forge/
└─ extensions/
   └─ sd-webui-tagcomplete-neo-multicsv/
      ├─ javascript/
      ├─ scripts/
      ├─ tags/
      └─ README.md
```

3. WebUIを起動または再起動します。
4. `Settings` → `Tag Autocomplete / Multi-CSV`を開きます。
5. 設定変更後は`Apply settings`を押します。`requires Reload UI`と表示される項目だけUI再読み込みが必要です。

既存のTagComplete系拡張と同時に有効化すると、同じ入力欄へ複数の補完処理が登録される場合があります。
動作確認時は、他のTagComplete系拡張を一時的に無効化してください。

### データフォルダ

この配布ZIPには容量の大きいタグCSV・翻訳CSVを同梱していません。利用前に、
用意した`tag_files`と`translation_files`の内容を次のフォルダへコピーしてください。
コピー後、設定欄横の更新ボタンまたはWebUI再起動で一覧を更新します。

```text
tags/
├─ tag_files/          # タグ・自然言語CSV
├─ translation_files/  # 翻訳・別名CSV
├─ chants/             # Chant JSON
├─ config/             # ユーザープリセット、更新メタデータ
├─ cache/              # 実行時キャッシュ
└─ temp/               # LoRA、Embedding、Wildcard等の一時一覧
```

CSVはサブフォルダにも配置できます。設定画面には相対パスで表示されます。

### タグCSV

推奨ヘッダー:

```csv
tag,category,count,aliases,translation,source_type,insert_mode,category_scheme
long_hair,0,3608339,"longhair","長髪",tag,tag,danbooru
soft natural lighting,,100,"soft light","柔らかな自然光",natural_language,phrase,natural_language
with,,50,,,natural_language,word,natural_language
special_identifier_name,,1,,,custom,raw,custom
```

必須列は`tag`だけです。

対応する主な列:

- `tag`: 候補名・挿入テキスト
- `category`: Danbooru / e621互換カテゴリ番号
- `count`: 投稿数または優先度
- `aliases`: 検索用別名。カンマまたはセミコロン区切り
- `translation`: 表示・検索用翻訳
- `source_type`: `tag` / `natural_language` / `custom`
- `insert_mode`: `tag` / `phrase` / `word` / `raw` / `wildcard`
- `category_scheme`: `danbooru` / `e621` / `derpibooru` / `danbooru_e621_merged`など

従来のTagComplete形式も読み込めます。

```csv
long_hair,0,3608339,"longhair"
```

ヘッダーや種別列がない場合、ファイル名から可能な範囲で推定します。
`EnglishDictionary.csv`、`natural_language`、`krea`、`flux`、`qwen`などを含む名前は
自然言語辞書として扱われます。

### 翻訳CSV

推奨形式:

```csv
tag,ja,aliases
long_hair,"長髪,ロングヘア","髪が長い"
blue_eyes,"青い目,碧眼","ブルーアイ"
```

汎用形式も利用できます。

```csv
tag,translation,aliases
long_hair,"long hair","flowing hair"
```

従来の2列形式も利用できます。

```csv
long_hair,長髪
```

翻訳CSVを選択しなければ、翻訳機能なしで通常のTagCompleteとして動作します。
日本語専用の固定処理ではないため、他言語の翻訳CSVも利用できます。

### 複数CSV

`Tag files`と`Translation files`は複数選択ドロップダウンです。

例:

```text
Tag files:
- danbooru_2025.csv
- natural_language_tags.csv
- my_custom_tags.csv

Translation files:
- merged_translations_dedup.csv
- natural_language_ja.csv
```

統合時の動作:

- 同じタグは候補に1件だけ表示
- Aliasと翻訳は重複を除いて統合
- `count`は最大値を採用
- 有効なカテゴリ情報を維持
- 読み込み元ファイルと辞書種別を内部保持
- 選択順をソース優先順として扱う

これは候補データの重複統合です。入力済みプロンプト本文を自動削除・整形する機能ではありません。

大きなCSVを複数選択すると、初回読み込み時間とPython・ブラウザ双方のメモリ使用量が増えます。
通常は用途に必要な辞書だけを選び、`Use indexed search`をONのまま利用してください。

### プロンプトモード

#### Tag priority

Danbooruなどのタグ辞書を優先します。SDXL、Illustrious XL、Pony系などに向く初期設定です。

#### Auto (Hybrid)

タグ辞書と自然言語辞書を同時利用します。カンマ区切りのタグ入力ではタグを、
文章状の入力では自然言語候補をやや優先します。Animaなどを想定しています。

#### Natural language priority

自然言語辞書を優先します。Krea 2、Z-Image、FLUX、Qwen-Imageなどを想定しています。

#### Equal priority

選択CSVと設定をそのまま使用します。

モードは検索順位と挿入規則を調整します。CSV選択を強制的に固定するものではありません。

### プリセット

`Settings`内のMulti-CSVプリセットマネージャーでは次を実行できます。

- 適用
- 名前を付けて保存
- 上書き
- 名前変更
- 削除
- JSONバックアップ
- JSON読み込み

プリセットはユーザーが保存したものだけを表示・バックアップします。
バックアップJSONに含まれるのはプリセットと関連設定です。CSV本体は含みません。
CSV本体は通常のファイルバックアップで保管してください。

### プロンプト付近の簡易設定

`Show collapsed preset controls near prompts`を有効にすると、txt2img / img2imgのプロンプト付近に
折りたたみ式の操作欄を追加します。この機能の初期値はOFFで、TagComplete Neoの標準画面を変更しません。

- プリセット
- Prompt mode
- タグCSV
- 翻訳CSV
- 適用ボタン

有効化した場合も初期状態は閉じています。不要な場合は設定から無効化できます。

### 検索

- 英語タグ
- 英語Alias
- 日本語・他言語翻訳
- 翻訳Alias
- 自然言語の単語・フレーズ
- ユーザー辞書

検索順位:

1. 完全一致
2. 前方一致
3. 単語先頭一致
4. 部分一致

検索時は`_`と空白を同一視します。日本語・翻訳検索と翻訳表示は別々に切り替えられます。
そのため、日本語で検索しつつ候補表示を英語だけにすることも可能です。

### 候補表示

初期表示はTagComplete Neoを踏襲します。

- カテゴリ色
- 投稿数
- Alias / 翻訳
- 使用頻度マーカー
- 既出タグマーカー
- Extra Networkプレビュー

追加表示は任意です。

- `Show source labels`: `TAG` / `NL` / `CUSTOM`
- `Use a distinct color for natural-language suggestions`
- `Display translations in suggestions`

追加色とソースラベルは初期値OFFです。

### 挿入形式

設定可能な項目:

- アンダースコアを空白へ変換
- カンマを追加
- 区切り後にスペースを追加
- 文末にスペースを追加
- 括弧をエスケープ
- アンダースコア変換除外パターン

推奨初期値では通常タグを次のように挿入します。

```text
long hair, blue eyes, looking at viewer,
```

実際の初期設定では末尾にスペースも追加されます。

`insert_mode`の動作:

- `tag`: カンマ＋スペース
- `phrase`: カンマ＋スペース
- `word`: スペースのみ
- `raw`: 文字列を変換せず挿入
- `wildcard`: Wildcard構文を完全保持

自然言語CSVに`insert_mode`がない場合、単語1個は`word`、複数語は`phrase`として推定します。

### アンダースコア保護

除外欄はカンマ区切り・改行区切りに対応し、`*`と`?`を使えます。

初期値には次のような構文依存タグを含みます。

```text
score_*
^_^
>_<
@_@
=_=
o_o
x_x
u_u
|_|
||_||
0_0
3_3
6_9
._.
+_+
+_-
(o)_(o)
<o>_<o>
```

例:

```text
score_8_up  -> score_8_up
long_hair   -> long hair
```

旧式のDanbooru表記をすべて保護するのではなく、構文上アンダースコアが必要な項目だけを保護します。

### Dynamic Prompts / Wildcard

次のような構文は常にそのまま扱います。

```text
__wildcards/eye-color__
```

- 前後の`__`を維持
- 内部の`/`、`-`、`_`を維持
- 通常タグのアンダースコア変換を適用しない
- 通常タグ用のカンマを自動追加しない

Wildcard ManagerやDynamic Promptsの既存ファイル構成を変更しません。

### リモートCSV更新

任意のCSV URLとローカル保存名を設定できます。

- 起動時確認をON/OFF
- 設定画面から手動更新
- `ETag`、`Last-Modified`、`Content-Length`を比較
- 変更がある場合だけダウンロード
- 一時ファイルへ保存後、原子的に置換
- 更新失敗時は既存ローカルCSVを継続利用

既定URLはDanbooruタグCSVです。ネットワークアクセスを不要にしたい場合は自動更新をOFFのまま使用してください。

### 対象外

この拡張は候補の検索・表示・挿入に集中します。次は実装していません。

- プロンプト全体の自動整形
- 入力済みタグの自動重複削除
- クリップボード内容の自動整形
- ペースト時の自動変換
- Booru Structure処理
- JSONプロンプト生成
- TagComplete UIと別の第二候補UI

### オフライン検証

展開した拡張フォルダで次を実行すると、Python構文、JavaScript構文、
辞書統合、プリセット、Wildcard保護などをまとめて確認できます。

```bash
python tools/verify_extension.py
```

これはForge本体を起動しない検証です。最終確認ではForge / Forge Neoの実環境で、
CSV選択、候補表示、LoRA・Embedding・Wildcard補完、設定保存を確認してください。

### トラブルシューティング

#### CSVを追加しても表示されない

- 設定欄横の更新ボタンを押す
- `Apply settings`を押す
- 必要に応じて`Reload UI`
- CSVが`tags/tag_files`または`tags/translation_files`にあることを確認

#### 候補が二重に表示される

他のTagComplete系拡張が同時に有効になっていないか確認してください。

#### 補完が出ない

- `Enable Tag Autocompletion`を確認
- 対象タブの`Active in ...`を確認
- Tag filesが1件以上選択されているか確認
- ブラウザ開発者コンソールとWebUIコンソールを確認

#### 自然言語に不要なカンマが付く

辞書の対象行に`insert_mode=word`または`insert_mode=raw`を指定してください。

#### 特殊タグのアンダースコアが消える

`Underscore replacement exclusion patterns`へ完全名またはパターンを追加してください。

---

## English

### Overview

TagComplete Neo Multi-CSV is a Forge / Forge Neo fork of TagComplete Neo. It keeps
the familiar autocomplete UI and existing completion providers while adding a
multi-source dictionary layer inspired by Danbooru Tag JP Assist.

Key additions:

- Separate `tag_files` and `translation_files` directories
- Multi-select tag and translation CSV settings
- Deduplicated merging of tags, aliases, translations, counts, and categories
- Optional translated search and translated display
- Natural-language dictionaries and Tag / Hybrid / Natural Language modes
- User-created presets
- Preset export/import backup
- Optional collapsed quick controls near txt2img/img2img prompts (disabled by default)
- Glob-style underscore exclusion patterns
- Lazy loading of bundled CSV data on first prompt interaction

### Installation

Extract the folder into the WebUI `extensions` directory:

```text
extensions/sd-webui-tagcomplete-neo-multicsv/
```

Restart the WebUI, then open:

```text
Settings -> Tag Autocomplete / Multi-CSV
```

Disable other TagComplete forks while testing to avoid duplicate listeners.

### Data layout

The extension bundles `danbooru_2025.csv`, the optional Anima artist/character
files, a natural-language tag file, and the matching translation files.
Only `danbooru_2025.csv` is selected by default.

```text
tags/
├─ tag_files/
├─ translation_files/
├─ chants/
├─ config/
├─ cache/
└─ temp/
```

Subfolders are supported.

### Tag CSV

Recommended header:

```csv
tag,category,count,aliases,translation,source_type,insert_mode,category_scheme
```

Only `tag` is required. Headerless TagComplete-compatible CSV files remain
supported.

`source_type` values:

- `tag`
- `natural_language`
- `custom`

`insert_mode` values:

- `tag`: comma and space
- `phrase`: comma and space
- `word`: space only
- `raw`: preserve the text
- `wildcard`: preserve wildcard syntax

### Translation CSV

Recommended format:

```csv
tag,translation,aliases
long_hair,"long hair","flowing hair"
```

JP Assist format is also supported:

```csv
tag,ja,aliases
long_hair,"長髪,ロングヘア","髪が長い"
```

Translations are optional and not limited to Japanese.

### Multiple sources and merge rules

- A tag is displayed once even if it appears in multiple files.
- Aliases and translations are unioned and deduplicated.
- The maximum valid count is retained.
- Booru category information is preserved.
- Source files and source types are retained internally.
- Selection order is treated as source priority.

Selecting several very large CSV files increases first-load time and memory use
in both Python and the browser. Keep indexed search enabled and select only the
sources needed for the current workflow.

### Presets

Only user-created presets are shown in the Multi-CSV preset manager. Users can
save new presets, overwrite, rename, delete, export, and import them. Backup
JSON contains preset settings, not the CSV data files.

### Wildcards and underscore protection

Dynamic Prompts syntax such as:

```text
__wildcards/eye-color__
```

is always preserved. Underscore exclusions accept comma/newline-separated glob
patterns such as `score_*`.

### Offline verification

Run the packaged verification script from the extracted extension directory:

```bash
python tools/verify_extension.py
```

This validates Python/JavaScript syntax and the WebUI-independent merge, preset,
and wildcard-protection logic. A real Forge / Forge Neo installation is still
required for final UI and integration testing.

### Compatibility notes

The extension uses feature detection for Forge Neo and classic Forge paths and
embedding APIs. Runtime compatibility can still depend on WebUI changes, other
extensions, browser versions, and local model directory settings.

---

## Credits

- [a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) by DominikDoom — original project
- [sd-webui-tagcomplete-neo](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo) by Eduardo Abreu — Forge Neo fork and performance/compatibility work
- [Danbooru-Tag-JP-Assist](https://github.com/ukr8b3g-cmyk/Danbooru-Tag-JP-Assist) by ukr8b3g-cmyk — multiple CSV, separated translations, translated search, and data-update design
- [sd-dynamic-prompts](https://github.com/adieyal/sd-dynamic-prompts) — supported wildcard syntax

## License

Source code is released under the MIT License. See [LICENSE](LICENSE).

CSV and translation data can have separate terms. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), the source page for each data
file, and any notice distributed with user-provided files.
