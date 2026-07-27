# TagComplete Neo Multi-CSV 検証報告書

**文書状態:** 公開候補<br>
**対象実装:** `da4a361`<br>
**検証日:** 2026-07-28<br>
**確認環境:** Forge Neo `neo 2.27` / Python 3.13.12 / Gradio 4.40.0

[English version](VALIDATION_REPORT.md)

## 1. 目的

本書は、TagComplete Neo Multi-CSVの後半検証で確定した結果を、
公開可能な試験記録として整理したものです。

初期調査中の起動失敗、一時的な実装、採用しなかった試作値は結果表から除外し、
次の項目だけを記録します。

- 複数CSV検索と候補表示
- 永続ディスクキャッシュとメモリキャッシュ
- 入力応答とクライアント描画
- キャッシュ形式v6の性能
- 日本語／英語UI
- 詳細設定アコーディオンと更新ボタン
- 自動テストとオフライン検証

## 2. 証跡区分

| 区分 | 意味 |
|---|---|
| 実測 | Forge Neo実機でタイミング値を取得 |
| 実機確認 | Forge Neo上の表示・操作・DOM状態を確認 |
| 自動試験 | Python／JavaScriptテストで再現可能 |
| 未確認 | 現時点で対応を保証しない |

性能値は当該環境での参考値です。CPU、ストレージ、ブラウザー、
同時使用拡張、選択CSVによって変動するため、ハードウェア非依存の保証値ではありません。

## 3. 実機試験条件

### 3.1 Forge Neoソフトウェア環境

現在のForge Neo実行環境で表示されたソフトウェア構成です。

| 構成要素 | バージョン／設定 |
|---|---|
| Forge Neo version | `neo 2.27` |
| ホスト | Windows 64-bit（`AMD64`） |
| Python | `3.13.12` |
| Pythonコンパイラー | `MSC v.1944 64 bit (AMD64)` |
| PyTorch | `2.11.0+cu130` |
| CUDAアロケーター | `cudaMallocAsync` |
| 非同期weight offloading | 有効、`2`ストリーム |
| Flash Attention | 有効（`2.8.3+cu130torch2.11`） |
| Gradio | `4.40.0` |

性能に関係する起動フラグ:

```text
--pin-shared-memory --cuda-malloc --cuda-stream --disable-sage
```

ローカルのモデル保存パスと無関係な他拡張のエラーは、
Multi-CSV検証の再現に不要なため記載していません。

### 3.2 性能測定ハードウェア

本書の実測タイミング値を取得した環境です。

| 構成要素 | ハードウェア |
|---|---|
| CPU | AMD Ryzen 9 3900X |
| GPU | NVIDIA GeForce RTX 5060 Ti 16 GB |
| システムメモリ | 64 GB |

性能値の基準はこの環境です。

### 3.3 選択データ

![日本語の複数CSV選択とプロンプトモード設定](assets/validation/ja-multicsv-controls.png)

*タグCSV・翻訳CSVの複数選択、プロンプトモード、候補表示設定。*

タグCSV:

- `danbooru_2025.csv`
- `natural_language_tags.csv`

翻訳CSV:

- `merged_translations_dedup.csv`
- `natural_language_ja.csv`

`anima_artists.csv`、`anima_characters.csv`、`e621.csv`は同梱対象ですが、
この性能比較の選択セットには含めていません。

### 3.4 入力条件

- 通常入力: `school`
- 多候補入力: `bag`
- 文字削除後の候補復帰: Backspace
- キャッシュ状態: `build`、`disk`、`memory`
- 候補描画比較: 20件、50件、100件

### 3.5 採用設定

![日本語のサーバー検索とキャッシュ設定](assets/validation/ja-search-settings.png)

*CSV+詳細アコーディオンには、サーバー検索、候補数、キャッシュ、計測設定をまとめています。*

| 設定 | 採用値 |
|---|---|
| Multi-CSV search engine | `Server index — recommended` |
| Server search candidate pool | `250` |
| Persist compiled Multi-CSV search indexes | ON |
| Compiled search configurations kept in memory | `4` |
| Compiled search configurations kept on disk | `8` |
| Log Multi-CSV search timings | 通常OFF |
| 通常入力デバウンス | `50 ms` |

## 4. 性能結果

### 4.1 キャッシュ形式v6

`prefix_index`と`unicode_gram_index`を
`keys + offsets + values`の連続配列形式へ変更した結果です。

| 試験ID | 項目 | 変更前 | v6 | 結果 |
|---|---|---:|---:|---|
| PERF-01 | ディスクキャッシュ復元 | 873.55 ms | 380.54 ms | 56.4%短縮 |
| PERF-02 | 再起動後の初回候補UI | 1.052 s | 609 ms | 合格 |
| PERF-03 | メモリキャッシュAPI | — | 9.03 ms | 合格 |
| PERF-04 | メモリキャッシュ時の候補UI | — | 176.4 ms | 実用上合格 |
| PERF-05 | 検索本体 | — | 約7～10 ms | ボトルネックではない |
| PERF-06 | キャッシュサイズ | 基準 | 約9.3%削減 | 合格 |
| PERF-07 | 初回インデックス構築 | — | 約10.24 s | 条件付き合格 |

PERF-07は選択CSV構成ごとの初回だけ発生します。
同じCSV構成ではディスクキャッシュを再利用するため、
起動時の全CSVプリロードは採用していません。

### 4.2 クライアント応答

- メモリキャッシュ時の検索APIは約9 msであり、検索本体は主因ではありませんでした。
- 通常入力では50 msのデバウンスを維持しています。
- Forge Neoのメインスレッド混雑により、タイマー発火が約30～40 ms遅れる場合がありました。
- 25 msデバウンスは短縮効果が小さく、Abort増加との釣り合いが悪いため不採用としました。
- 20／50／100件の比較では、TagComplete候補DOM生成は主な遅延原因ではありませんでした。
- Backspace時は候補復帰を優先し、即時検索動作を維持しています。

判定: 入力応答は実用上合格。デバウンスは50 msを正式採用。

## 5. 機能試験

### 5.1 挿入・除外設定

![日本語の挿入・除外設定](assets/validation/ja-insertion-controls.png)

*標準の除外設定を復元する操作をCSV+として示し、TagCompleteの既存挿入設定を維持しています。*

### 5.2 アーティスト接頭辞設定

![日本語のアーティスト接頭辞設定](assets/validation/ja-artist-prefix.png)

*アーティストタグを変更しない、常に`@`を付ける、Animaモデル検出時だけ付ける設定を選択できます。*

### 5.3 機能試験結果

| 試験ID | 試験内容 | 期待結果 | 結果 |
|---|---|---|---|
| FUNC-01 | 複数タグCSV選択 | 選択順をソース優先順位として統合 | 合格 |
| FUNC-02 | 複数翻訳CSV選択 | タグへ翻訳・Aliasを統合 | 合格 |
| FUNC-03 | 重複タグ統合 | 同一タグを1候補として表示 | 合格 |
| FUNC-04 | `cache=build` | 初回検索でインデックスを構築 | 合格 |
| FUNC-05 | `cache=memory` | 同一セッションで構築済み索引を再利用 | 合格 |
| FUNC-06 | `cache=disk` | Forge Neo再起動後に永続索引を復元 | 合格 |
| FUNC-07 | CSV変更 | ファイル署名変更時にキャッシュを自動無効化 | 合格 |
| FUNC-08 | 同時初回要求 | 同一構成のインデックス構築を共有 | 合格 |
| FUNC-09 | `school`検索 | 候補を正常表示 | 合格 |
| FUNC-10 | `bag`検索 | 多候補条件でも検索を継続 | 合格 |
| FUNC-11 | Backspace復帰 | 削除後の候補を即時更新 | 合格 |
| FUNC-12 | Legacy fallback | Server API利用不可時に互換モードへ移行 | 合格 |
| FUNC-13 | Extra Provider | LoRA等の従来候補経路を維持 | 自動試験合格 |
| FUNC-14 | Wildcard保護 | `__folder/name__`形式を変換しない | 合格 |
| FUNC-15 | アンダースコア除外 | glob形式の除外パターンを適用 | 合格 |

## 6. UI実機確認

| 試験ID | 確認内容 | 結果 |
|---|---|---|
| UI-01 | 日本語選択時にMulti-CSV項目を日本語表示 | 合格 |
| UI-02 | 日本語選択時にTagComplete Neo標準項目を日本語表示 | 合格 |
| UI-03 | 英語へ切替後、標準項目と補足文を英語へ復元 | 合格 |
| UI-04 | 除外設定復元ボタンを日英で切替 | 合格 |
| UI-05 | CSV+バッジを項目名の直後に表示 | 合格 |
| UI-06 | 不要なSHARED説明帯を表示しない | 合格 |
| UI-07 | CORE詳細設定を独立した閉じたアコーディオンに格納 | 合格 |
| UI-08 | CSV+検索設定を独立した閉じたアコーディオンに格納 | 合格 |
| UI-09 | CORE内にHotkeys、Colors、内部更新だけを配置 | 合格 |
| UI-10 | CSV+内に検索、候補数、キャッシュ、計測だけを配置 | 合格 |
| UI-11 | Extra／Chant更新ボタンを各フィールド横に維持 | 合格 |
| UI-12 | 言語切替後も詳細設定アコーディオン状態を維持 | 合格 |

## 7. 自動試験

2026-07-28の公開前確認:

| 試験 | 件数／結果 |
|---|---|
| JavaScript Node test runner | 3件成功 |
| Python pytest | 32件成功 |
| Python構文確認 | 成功 |
| JavaScript構文確認 | 成功 |
| `tools/verify_extension.py` | PASS |
| `git diff --check` | 問題なし |

実行例:

```powershell
node --check javascript/zz_jpAssistUI.js
node --check javascript/zzzz_tacjp_fast_search.js
node --test tests/*.js
pytest tests -q -p no:cacheprovider
python tools/verify_extension.py
git diff --check
```

主な自動試験範囲:

- CSV解析と重複統合
- 翻訳・Alias統合
- キャッシュv6の保存／復元
- 空索引、該当キーなし、大きな候補集合
- キャッシュ署名と自動無効化
- Forge Neo固有ローダー互換
- Server API登録とLegacy fallback
- AbortControllerと最新リクエスト優先
- クライアント計測ログ
- Wildcard・アンダースコア保護
- 配布ファイル構成

## 8. 採用仕様

検証結果から、次を現行仕様とします。

1. 大容量CSVは起動時に全件解析せず、最初の通常タグ検索時に遅延構築する。
2. 完全な検索索引はPython側へ保持し、ブラウザーには候補プールだけを返す。
3. 永続キャッシュ形式はv6とし、旧形式は削除せず自動的に無効化する。
4. 選択CSVの構成またはファイル署名が変わった場合だけ再構築する。
5. 通常入力デバウンスは50 msとし、Backspace時の即時更新を維持する。
6. 計測ログは通常OFFとし、診断時だけ有効化する。
7. TagComplete Neoの既存Providerは従来経路を維持する。
8. 詳細設定はCOREとCSV+の2区分に分離し、初期状態を閉じる。
9. 表示言語が日本語の場合は、Multi-CSV項目と標準TagComplete Neo項目を日本語化する。
10. 未完成のユーザープリセットUIは現行版に表示しない。

## 9. 未確認・対象外

| 項目 | 状態 |
|---|---|
| Forge Neo | 実機確認済み |
| Stable Diffusion WebUI Forge | 未確認 |
| reForge | 未確認 |
| 他拡張をすべて無効化した純粋比較 | 未実施 |
| ハードウェア別性能比較 | 未実施 |
| ユーザープリセットUI | 次バージョン予定 |
| 生成画像品質 | 本拡張の試験対象外 |

本書の「合格」は記載した環境と試験範囲に対する判定であり、
未確認環境の互換性を保証するものではありません。
