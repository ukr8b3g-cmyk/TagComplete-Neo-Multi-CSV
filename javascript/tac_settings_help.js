(() => {
    "use strict";

    const TAC_SETTING_HELP = {
        tacjp_candidateSortMode: {
            ja: "候補の並び順を選びます。Neo互換は選択したCSVと各CSV内の登録順を基本にし、関連度優先は一致度・件数・名前で並べます。投稿数優先は通常タグだけを投稿数順にします。プロンプトモードのタグ／自然言語優先とは別の設定です。",
            en: "Chooses how tag candidates are ordered. Neo compatible preserves selected CSV order and each CSV's entry order; Relevance first uses match quality, count, and name. Count first orders normal tag entries by count only. This is separate from prompt mode's tag versus natural-language priority.",
        },
        tacjp_showTranslations: {
            ja: "候補リストに翻訳を併記します。日本語で検索したい場合や、英語タグの意味を確認したい場合に有効です。",
            en: "Shows translations next to candidate tags. Useful for searching in Japanese or checking the meaning of English tags.",
        },
        tacjp_showSourceLabels: {
            ja: "候補がタグ、自然言語、ユーザーCSVなど、どの種類の辞書から来たかを表示します。",
            en: "Shows which type of source each candidate comes from, such as tags, natural language, or user CSV files.",
        },
        tacjp_colorNaturalLanguage: {
            ja: "自然言語プロンプト用の候補を色で識別します。通常のタグ候補と区別しやすくなります。",
            en: "Marks natural-language prompt candidates with a distinct color so they can be distinguished from regular tag candidates.",
        },
        tac_active: {
            ja: "タグ自動補完機能全体の有効・無効を切り替えます。",
            en: "Enables or disables tag autocompletion globally.",
        },
        "tac_activeIn.txt2img": {
            ja: "txt2imgのプロンプト入力欄でタグ補完を有効にします。変更後はWebUIの再起動が必要です。",
            en: "Enables tag completion in txt2img prompt fields. A WebUI restart is required after changing this setting.",
        },
        "tac_activeIn.img2img": {
            ja: "img2imgのプロンプト入力欄でタグ補完を有効にします。変更後はWebUIの再起動が必要です。",
            en: "Enables tag completion in img2img prompt fields. A WebUI restart is required after changing this setting.",
        },
        "tac_activeIn.negativePrompts": {
            ja: "ネガティブプロンプト入力欄でもタグ補完を有効にします。変更後はWebUIの再起動が必要です。",
            en: "Enables tag completion in negative prompt fields. A WebUI restart is required after changing this setting.",
        },
        "tac_activeIn.thirdParty": {
            ja: "対応する外部拡張のテキスト入力欄でもタグ補完を有効にします。変更後はWebUIの再起動が必要です。",
            en: "Enables tag completion in supported third-party extension text fields. A WebUI restart is required after changing this setting.",
        },
        "tac_activeIn.modelList": {
            ja: "タグ補完を有効または無効にするモデル名・拡張子付きファイル名・ハッシュを、カンマ区切りで指定します。",
            en: "Lists model names, filenames with extensions, or hashes separated by commas for the model filter.",
        },
        "tac_activeIn.modelListMode": {
            ja: "モデルリストをブラックリストとして使うか、ホワイトリストとして使うかを選択します。",
            en: "Selects whether the model list is used as a blacklist or a whitelist.",
        },
        tac_slidingPopup: {
            ja: "候補ポップアップを固定位置ではなく、プロンプト内の入力位置に合わせて移動します。",
            en: "Moves the completion popup with the text cursor instead of keeping it at a fixed position.",
        },
        tac_maxResults: {
            ja: "候補ポップアップに表示する最大件数です。多くすると探しやすくなりますが、描画が重くなる場合があります。",
            en: "Maximum number of candidates shown in the popup. Higher values show more results but may increase UI rendering cost.",
        },
        tac_showAllResults: {
            ja: "検索語に一致する候補を最大候補数で制限せず表示します。大きなCSVでは表示が重くなる場合があります。",
            en: "Shows matching candidates without limiting them to the maximum result count. This may be slower with large CSV files.",
        },
        tac_resultStepLength: {
            ja: "すべての候補を表示する場合に、一度に追加表示する候補数です。",
            en: "Number of additional candidates loaded at a time when all results are shown.",
        },
        tac_delayTime: {
            ja: "入力後に候補の再検索を開始するまでの待機時間です。現行のMulti-CSV実装では最大50msとして処理され、変更後は再起動が必要です。",
            en: "Delay before starting another candidate search after input. The current Multi-CSV implementation caps it at 50 ms, and changing it requires a restart.",
        },
        tac_useIndexedSearch: {
            ja: "大量のタグを高速に絞り込むためのインデックス検索を使用します。通常は有効のままを推奨します。",
            en: "Uses an index to narrow large tag sets more quickly. Keeping this enabled is recommended for normal use.",
        },
        tac_useWildcards: {
            ja: "対応するWildcardフォルダー内のファイル名を補完候補に含めます。",
            en: "Includes filenames from supported wildcard folders in completion results.",
        },
        tac_sortWildcardResults: {
            ja: "Wildcardファイル内の候補を、記載順ではなく名前順に並べます。",
            en: "Sorts entries inside wildcard files alphabetically instead of preserving their file order.",
        },
        tac_wildcardExclusionList: {
            ja: "Wildcard検索から除外するフォルダーを指定します。変更後はWebUIの再起動が必要です。",
            en: "Specifies wildcard folders to exclude from search. A WebUI restart is required after changing this setting.",
        },
        tac_skipWildcardRefresh: {
            ja: "追加ネットワーク更新時のWildcard再走査を省略します。更新は速くなりますが、新しいWildcardが反映されない場合があります。",
            en: "Skips rescanning wildcards during an extra-network refresh. Refreshing is faster, but newly added wildcards may not appear.",
        },
        tac_useEmbeddings: {
            ja: "Textual InversionのEmbedding名を補完候補に含めます。",
            en: "Includes Textual Inversion embedding names in completion results.",
        },
        tac_forceRefreshEmbeddings: {
            ja: "追加ネットワーク更新時にEmbedding一覧をキャッシュから再利用せず、強制的に作り直します。",
            en: "Forces the embedding list to be rebuilt instead of reused during an extra-network refresh.",
        },
        tac_includeEmbeddingsInNormalResults: {
            ja: "Embedding用の記号を入力していない通常検索にも、Embedding候補を混在させます。",
            en: "Includes embedding candidates in normal searches even when an embedding-specific prefix was not entered.",
        },
        tac_useLoras: {
            ja: "利用可能なLoRA名を補完候補に含めます。",
            en: "Includes available LoRA names in completion results.",
        },
        tac_useLycos: {
            ja: "利用可能なLyCORIS／LoHa名を補完候補に含めます。",
            en: "Includes available LyCORIS and LoHa names in completion results.",
        },
        tac_useLoraPrefixForLycos: {
            ja: "LyCORIS挿入時に「<lyco:」ではなく、Forge互換の「<lora:」接頭辞を使用します。",
            en: "Uses the Forge-compatible '<lora:' prefix instead of '<lyco:' when inserting LyCORIS models.",
        },
        tac_showWikiLinks: {
            ja: "対応するDanbooru／e621タグ候補に「?」リンクを追加し、Wikiページを開けるようにします。",
            en: "Adds a '?' link to supported Danbooru and e621 tag candidates for opening their wiki pages.",
        },
        tac_showExtraNetworkPreviews: {
            ja: "LoRA・LyCORIS・Embedding候補の選択時に、利用可能なプレビュー画像を表示します。",
            en: "Shows available preview images when selecting LoRA, LyCORIS, or embedding candidates.",
        },
        tac_modelSortOrder: {
            ja: "LoRA・LyCORIS・Embeddingなど、追加ネットワーク候補の並び順を指定します。通常タグ全体の並び順には影響しません。",
            en: "Controls the order of extra-network candidates such as LoRA, LyCORIS, and embeddings. It does not reorder the normal tag list.",
        },
        tac_useStyleVars: {
            ja: "WebUIに保存されているプロンプトスタイル名を補完候補に含めます。",
            en: "Includes prompt style names saved in the WebUI in completion results.",
        },
        tac_frequencySort: {
            ja: "タグの使用回数をローカルに記録し、よく使う候補を検索結果の上位へ移動します。",
            en: "Records tag usage locally and moves frequently used candidates higher in search results.",
        },
        tac_frequencyFunction: {
            ja: "使用回数を候補順位へ反映する計算方法と強さを選択します。",
            en: "Selects the calculation method and strength used to apply usage frequency to result ranking.",
        },
        tac_frequencyMinCount: {
            ja: "この回数以上使用した候補から、使用頻度による順位補正を開始します。",
            en: "Starts applying frequency-based ranking after a candidate has been used this many times.",
        },
        tac_frequencyMaxAge: {
            ja: "この日数より古い使用履歴を、頻度による順位補正の対象外にします。",
            en: "Excludes usage records older than this many days from frequency-based ranking.",
        },
        tac_frequencyRecommendCap: {
            ja: "入力前の使用頻度推薦などで表示する候補の最大件数です。",
            en: "Maximum number of candidates shown by frequency-based recommendations, including suggestions before typing.",
        },
        tac_frequencyIncludeAlias: {
            ja: "Alias名で選択した場合も、元タグの使用回数として記録します。",
            en: "Counts selections made through an alias toward the usage frequency of the underlying tag.",
        },
        tac_replaceUnderscores: {
            ja: "候補を挿入するとき、タグ内のアンダースコアを半角空白へ置き換えます。",
            en: "Replaces underscores in a tag with spaces when inserting a candidate.",
        },
        tac_undersocreReplacementExclusionList: {
            ja: "アンダースコアを空白へ変換しないタグのパターンを指定します。カンマまたは改行で区切り、* と ? が使用できます。",
            en: "Specifies tag patterns whose underscores must be preserved. Separate entries with commas or new lines; * and ? wildcards are supported.",
        },
        tac_escapeParentheses: {
            ja: "タグ挿入時に括弧をエスケープし、プロンプトの強調構文として解釈されにくくします。",
            en: "Escapes parentheses when inserting tags so they are less likely to be interpreted as prompt emphasis syntax.",
        },
        tac_appendComma: {
            ja: "タグまたはフレーズを補完した後に、自動でカンマを追加します。",
            en: "Automatically appends a comma after completing a tag or phrase.",
        },
        tac_appendSpace: {
            ja: "カンマなどの区切り文字を追加した後に、自動で空白を追加します。",
            en: "Automatically appends a space after an inserted separator such as a comma.",
        },
        tac_alwaysSpaceAtEnd: {
            ja: "プロンプト末尾で補完した場合も、次の入力用に空白を追加します。",
            en: "Adds a trailing space for the next entry even when completion occurs at the end of the prompt.",
        },
        tac_modelKeywordCompletion: {
            ja: "LoRA／LyCORIS候補を挿入するとき、登録済みのトリガーワードも自動追加する条件を選択します。",
            en: "Selects when known trigger words are automatically added while inserting a LoRA or LyCORIS candidate.",
        },
        tac_modelKeywordLocation: {
            ja: "自動追加するLoRA／LyCORISトリガーワードの挿入位置を選択します。",
            en: "Selects where automatically added LoRA or LyCORIS trigger words are inserted.",
        },
        tac_modelKeywordCivitai: {
            ja: "ローカルにトリガーワード情報がない場合、CivitAIから取得します。ネットワーク接続が必要です。",
            en: "Fetches trigger words from CivitAI when they are unavailable locally. A network connection is required.",
        },
        tac_civitaiApiKey: {
            ja: "CivitAIからトリガーワードを取得する場合に使用するAPIキーです。",
            en: "API key used when fetching trigger words from CivitAI.",
        },
        tac_animaArtistPrefix: {
            ja: "アーティストタグ挿入時に「@」を付ける条件を選択します。ANIMAでは@付きのアーティストタグが必要な場合があります。",
            en: "Selects when '@' is added to inserted artist tags. ANIMA models may require artist tags with this prefix.",
        },
        tac_wildcardCompletionMode: {
            ja: "入れ子になったWildcardパスを、次のフォルダーまで・差分まで・末尾までのどこまで補完するか選択します。",
            en: "Selects how far nested wildcard paths are completed: to the next folder, the first differing part, or the full path.",
        },
        "tac_alias.searchByAlias": {
            ja: "タグ本体だけでなく、登録されているAlias名でも検索できるようにします。",
            en: "Allows searching by registered aliases in addition to the original tag name.",
        },
        "tac_alias.onlyShowAlias": {
            ja: "Aliasで一致した候補について、元タグではなくAlias名だけを表示します。",
            en: "Shows only the alias name instead of the original tag for candidates matched through an alias.",
        },
        "tac_translation.oldFormat": {
            ja: "旧TagComplete向けの3列形式翻訳CSVを使用する場合に有効にします。",
            en: "Enable this when using the legacy three-column translation CSV format.",
        },
        "tac_translation.searchByTranslation": {
            ja: "英語タグ名だけでなく、読み込んだ翻訳文からも候補を検索できるようにします。",
            en: "Allows searching candidates by loaded translations as well as by their English tag names.",
        },
        "tac_translation.liveTranslation": {
            ja: "プロンプト入力欄の下にリアルタイム翻訳を表示する試験的機能です。",
            en: "Experimental feature that shows a live translation below the prompt field.",
        },
        "tac_extra.extraFile": {
            ja: "通常候補とは別に追加挿入するタグを収録したCSVファイルを選択します。",
            en: "Selects a CSV file containing tags that are inserted in addition to the normal completion result.",
        },
        "tac_extra.addMode": {
            ja: "追加タグを、選択した候補の前と後のどちらへ挿入するか選択します。",
            en: "Selects whether extra tags are inserted before or after the chosen completion result.",
        },
        tac_chantFile: {
            ja: "定型プロンプトのChant補完に使用するJSONファイルを選択します。",
            en: "Selects the JSON file used for chant-style preset prompt completion.",
        },
        tac_keymap: {
            ja: "候補移動・選択・閉じる操作に使用するキーボードショートカットをJSON形式で設定します。通常は変更不要です。",
            en: "Configures keyboard shortcuts for navigating, choosing, and closing candidates in JSON format. Normally this does not need to be changed.",
        },
        tac_colormap: {
            ja: "Danbooru・e621などのカテゴリ別候補色をJSON形式で設定します。通常は変更不要です。",
            en: "Configures candidate colors for Danbooru, e621, and other category schemes in JSON format. Normally this does not need to be changed.",
        },
    };

    const BOUND_ATTRIBUTE = "data-tac-settings-help-bound";
    const SHOW_DELAY_MS = 300;
    let tooltip = null;
    let activeRow = null;
    let observer = null;
    let showTimer = null;
    let lastPointer = {clientX: 0, clientY: 0};
    let suppressFocusUntil = 0;

    function tacSettingsHelpLanguage() {
        if (typeof tacJpLanguage === "function") {
            return tacJpLanguage();
        }
        const preference = String(
            window.opts?.tacjp_uiLanguage
            || window.TAC_CFG?.uiLanguage
            || "Auto"
        );
        if (preference === "Japanese") return "ja";
        if (preference === "English") return "en";
        return String(navigator.language || "en").toLowerCase().startsWith("ja") ? "ja" : "en";
    }

    function tacSettingsHelpRoot() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function tacSettingsHelpTooltip() {
        if (tooltip?.isConnected) return tooltip;
        tooltip = document.createElement("div");
        tooltip.className = "tac-settings-help-tooltip";
        Object.assign(tooltip.style, {
            position: "fixed",
            zIndex: "10000",
            display: "none",
            maxWidth: "360px",
            padding: "8px 10px",
            border: "1px solid rgba(255, 255, 255, 0.18)",
            borderRadius: "6px",
            background: "rgba(10, 13, 20, 0.96)",
            boxShadow: "0 4px 16px rgba(0, 0, 0, 0.35)",
            color: "#f2f4f8",
            fontSize: "12px",
            lineHeight: "1.45",
            pointerEvents: "none",
            whiteSpace: "normal",
        });
        document.body.appendChild(tooltip);
        return tooltip;
    }

    function tacSettingsHelpPosition(point) {
        const node = tacSettingsHelpTooltip();
        const gap = 14;
        const margin = 8;
        const rect = node.getBoundingClientRect();
        let left = point.clientX + gap;
        let top = point.clientY + gap;
        if (left + rect.width + margin > window.innerWidth) {
            left = Math.max(margin, point.clientX - rect.width - gap);
        }
        if (top + rect.height + margin > window.innerHeight) {
            top = Math.max(margin, point.clientY - rect.height - gap);
        }
        node.style.left = `${left}px`;
        node.style.top = `${top}px`;
    }

    function tacSettingsHelpShow(row, point) {
        const key = row.id.slice("setting_".length);
        const entry = TAC_SETTING_HELP[key];
        if (!entry) return;
        const language = tacSettingsHelpLanguage();
        const node = tacSettingsHelpTooltip();
        node.textContent = entry[language] || entry.en;
        node.style.display = "block";
        activeRow = row;
        tacSettingsHelpPosition(point);
    }

    function tacSettingsHelpCancelShow() {
        if (showTimer !== null) {
            clearTimeout(showTimer);
            showTimer = null;
        }
    }

    function tacSettingsHelpSchedule(row, point) {
        tacSettingsHelpCancelShow();
        lastPointer = {clientX: point.clientX, clientY: point.clientY};
        showTimer = setTimeout(() => {
            showTimer = null;
            if (row.isConnected) tacSettingsHelpShow(row, lastPointer);
        }, SHOW_DELAY_MS);
    }

    function tacSettingsHelpHide(row = null) {
        tacSettingsHelpCancelShow();
        if (row && row !== activeRow) return;
        if (tooltip) tooltip.style.display = "none";
        activeRow = null;
    }

    function tacSettingsHelpMarkLabel(row) {
        row.classList.add("tac-settings-help-row");
        const candidates = row.querySelectorAll("label span, .block-info");
        for (const candidate of candidates) {
            if (!candidate.textContent?.trim()) continue;
            candidate.style.cursor = "help";
            break;
        }
    }

    function tacSettingsHelpBind(row) {
        if (row.hasAttribute(BOUND_ATTRIBUTE)) return;
        row.setAttribute(BOUND_ATTRIBUTE, "true");
        tacSettingsHelpMarkLabel(row);
        row.addEventListener("pointerenter", event => {
            tacSettingsHelpSchedule(row, event);
        });
        row.addEventListener("pointermove", event => {
            lastPointer = {clientX: event.clientX, clientY: event.clientY};
            if (activeRow === row) tacSettingsHelpPosition(lastPointer);
        });
        row.addEventListener("pointerleave", () => tacSettingsHelpHide(row));
        row.addEventListener("pointerdown", () => {
            suppressFocusUntil = Date.now() + 500;
            tacSettingsHelpHide(row);
        });
        row.addEventListener("focusin", event => {
            if (Date.now() < suppressFocusUntil) return;
            const rect = event.target?.getBoundingClientRect?.() || row.getBoundingClientRect();
            tacSettingsHelpSchedule(row, {
                clientX: Math.min(rect.right, window.innerWidth - 20),
                clientY: Math.min(rect.bottom, window.innerHeight - 20),
            });
        });
        row.addEventListener("focusout", event => {
            if (!row.contains(event.relatedTarget)) tacSettingsHelpHide(row);
        });
    }

    function tacSettingsHelpApply(root = tacSettingsHelpRoot()) {
        if (!root?.querySelectorAll) return;
        root.querySelectorAll('[id^="setting_tac"]').forEach(row => {
            const key = row.id.slice("setting_".length);
            if (TAC_SETTING_HELP[key]) tacSettingsHelpBind(row);
        });
    }

    function tacSettingsHelpInitialize() {
        const root = tacSettingsHelpRoot();
        tacSettingsHelpApply(root);
        if (observer) observer.disconnect();
        observer = new MutationObserver(mutations => {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (!(node instanceof Element)) continue;
                    if (node.id?.startsWith("setting_tac")) {
                        const key = node.id.slice("setting_".length);
                        if (TAC_SETTING_HELP[key]) tacSettingsHelpBind(node);
                    }
                    tacSettingsHelpApply(node);
                }
            }
        });
        observer.observe(root, {childList: true, subtree: true});
        window.addEventListener("blur", () => tacSettingsHelpHide());
        window.addEventListener("scroll", () => tacSettingsHelpHide(), true);
    }

    if (typeof onUiLoaded === "function") {
        onUiLoaded(tacSettingsHelpInitialize);
    } else if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tacSettingsHelpInitialize, {once: true});
    } else {
        tacSettingsHelpInitialize();
    }
})();
