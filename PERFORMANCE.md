# Multi-CSV Performance

## 日本語

### 実機検証記録

2026年7月、Forge Neo上で
`danbooru_2025.csv`、`natural_language_tags.csv`、翻訳CSV 2個を選択し、
`school`、`bag`、Backspace復帰を使って計測しました。数値は当該環境での
実測値であり、PC、ブラウザ、同時使用拡張によって変動します。

| 項目 | 変更前 | v6連続配列キャッシュ | 結果 |
|---|---:|---:|---|
| ディスクキャッシュ復元 | 873.55 ms | 380.54 ms | 56.4%短縮 |
| 再起動後の初回UI表示 | 1.052 s | 609 ms | 合格 |
| メモリキャッシュAPI | — | 9.03 ms | 合格 |
| メモリキャッシュ時UI | — | 176.4 ms | 実用範囲 |
| 検索本体 | — | 約7～10 ms | ボトルネックではない |
| キャッシュサイズ | 基準 | 約9.3%削減 | 合格 |

検証内容:

- 初回構築後、同一セッションで`cache=memory`になること
- Forge Neo再起動後に`cache=disk`になること
- 選択CSV変更時にキャッシュが自動無効化されること
- 複数CSV・翻訳CSVの重複統合と候補順位が維持されること
- 候補20・50・100件でDOM描画が主な遅延原因ではないこと
- デバウンス25msはAbort増加に対して改善が小さいため不採用
- デバウンス50msを維持し、Forge Neo全体のメインスレッド遅延と分離したこと

このv6測定は当時の記録です。現在のv8では、起動後のアイドル時間に選択CSV構成を
ウォームアップし、最初の入力前に構築または復元を完了させます。v8ではASCII trigram
インデックスと投稿数順インデックスも追加され、Count優先の検索順位を保ちます。

判定:

- 複数CSV検索: 合格
- ディスク／メモリキャッシュ: 合格
- 入力応答: 実用上合格
- 通常設定: 計測ログOFF、デバウンス50msを維持

### 推奨設定

`Settings` → `Tag Autocomplete / Multi-CSV`で、次の設定を使用します。

- **Multi-CSV search engine:** `Server index — recommended`
- **Server search candidate pool:** `250`
- **Persist compiled Multi-CSV search indexes:** ON
- **Compiled search configurations kept in memory:** `4`
- **Compiled search configurations kept on disk:** `8`
- **Log Multi-CSV search timings:** 通常はOFF

候補数を非常に多く表示する場合や、使用頻度ソートで多数の候補を再評価したい場合は、`Server search candidate pool`を500～1000へ増やせます。値を増やすほどレスポンスとクライアント側の並び替え負荷も増えます。

### 動作

- WebUI起動時には大容量CSVを解析しません。
- 最初に通常タグを検索した時点で、選択中のタグCSV・翻訳CSVを統合し、サーバー側検索インデックスを作成します。
- ブラウザへ全タグを送らず、入力文字列に一致した候補プールだけを返します。
- 作成済みインデックスは`tags/cache/fast-search-v*/`へ保存され、WebUI再起動後も再利用されます。
- 選択CSVのファイル名、サイズ、更新日時が変わると、新しい署名で自動的に再構築します。
- 同じ構成への複数の初回リクエストは、1回のインデックス構築を共有します。
- 日本語などの非ASCII検索には1～3文字の部分文字列インデックスを使用します。
- 英語タグ・Alias・自然言語にはコンパクトな前方一致インデックスを使用し、必要な場合だけ正規化済み文字列を追加走査します。

### 互換モード

`Legacy browser index — compatibility`を選ぶと、従来どおり統合済み全タグをブラウザへ読み込みます。

次の場合は自動的にLegacy browser方式を使用します。

- 実験的な`Show live translation below prompt`を有効にした場合
- Server index APIが利用できず、そのセッションで自動フォールバックした場合

LoRA、LyCORIS、Embedding、Wildcard、YAML Wildcard、UMI、Chantなどの既存Providerは、Server index選択時も従来の処理を維持します。

### キャッシュ管理

- CSVを差し替えた場合、通常は自動無効化されるため手動削除は不要です。
- 動作確認やキャッシュ形式の問題が疑われる場合は、`Clear compiled Multi-CSV search cache`を使用します。
- キャッシュ保存先へ書き込めない場合も、検索はメモリキャッシュへ自動的にフォールバックします。
- キャッシュには選択したCSVから生成した検索データが含まれます。配布ZIPやGitへ`tags/cache`を含めないでください。

### タイミング確認

`Log Multi-CSV search timings`をONにすると、コンソールへ次を表示します。

- `cache=build`: CSVから新規構築
- `cache=disk`: 永続キャッシュから復元
- `cache=memory`: 同一セッションのメモリキャッシュ
- 統合後の総タグ数
- 返却候補数
- 初回構築時間と検索リクエスト時間

## English

### Test record

The Forge Neo test used `danbooru_2025.csv`, `natural_language_tags.csv`, and
two translation CSV files. The historical v6 contiguous-array cache reduced measured disk
restore time from 873.55 ms to 380.54 ms (56.4%) and the first post-restart UI
result from 1.052 s to 609 ms. A memory-cached request measured 9.03 ms at the
API and 176.4 ms end to end in the UI. These are reference measurements from
one test system, not hardware-independent guarantees.

Functional checks covered build, disk and memory cache paths, automatic cache
invalidation, duplicate merging, result ordering, Backspace behavior, and
20/50/100-result rendering comparisons. A 25 ms debounce experiment was
rejected because it increased aborts without enough latency improvement; the
50 ms behavior was retained.

### Recommended settings

Use the following values under `Settings` → `Tag Autocomplete / Multi-CSV`:

- **Multi-CSV search engine:** `Server index — recommended`
- **Server search candidate pool:** `250`
- **Persist compiled Multi-CSV search indexes:** enabled
- **Compiled search configurations kept in memory:** `4`
- **Compiled search configurations kept on disk:** `8`
- **Log Multi-CSV search timings:** normally disabled

The current v8 server index warms up the selected CSV combination during idle
time after startup, keeps the complete index on the server, and returns only a
limited candidate pool to the browser. Compiled indexes are reused across WebUI
restarts and invalidated when a selected file changes.

Use `Legacy browser index — compatibility` when diagnosing compatibility issues or when the experimental full-prompt live translation feature is required. Existing LoRA, Embedding, Wildcard and Chant providers continue to use their original client-side paths.
