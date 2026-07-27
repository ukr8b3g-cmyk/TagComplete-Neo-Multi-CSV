# Multi-CSV Performance

## 日本語

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

### Recommended settings

Use the following values under `Settings` → `Tag Autocomplete / Multi-CSV`:

- **Multi-CSV search engine:** `Server index — recommended`
- **Server search candidate pool:** `250`
- **Persist compiled Multi-CSV search indexes:** enabled
- **Compiled search configurations kept in memory:** `4`
- **Compiled search configurations kept on disk:** `8`
- **Log Multi-CSV search timings:** normally disabled

The server index preserves lazy loading. It compiles the selected CSV combination on the first normal tag query, keeps the complete index on the server, and returns only a limited candidate pool to the browser. Compiled indexes are reused across WebUI restarts and invalidated when a selected file changes.

Use `Legacy browser index — compatibility` when diagnosing compatibility issues or when the experimental full-prompt live translation feature is required. Existing LoRA, Embedding, Wildcard and Chant providers continue to use their original client-side paths.
