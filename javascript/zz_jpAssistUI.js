// TagComplete Neo Multi-CSV settings decorations and planned preset controls.

const TACJP_DEFAULT_EXCLUSIONS = "score_*,rating_*,source_*,^_^,>_<,@_@,=_=,o_o,o_x,x_x,t_t,u_u,|_|,||_||,0_0,3_3,6_9,._.,+_+,+_-,(o)_(o),<o>_<o>,<|>_<|>,>_o";
const TACJP_OPTION_MAP = {
    tag_files: "tacjp_tagFiles",
    translation_files: "tacjp_translationFiles",
    prompt_mode: "tacjp_promptMode",
    search_translations: "tac_translation.searchByTranslation",
    show_translations: "tacjp_showTranslations",
    show_source_labels: "tacjp_showSourceLabels",
    color_natural_language: "tacjp_colorNaturalLanguage",
    replace_underscores: "tac_replaceUnderscores",
    append_comma: "tac_appendComma",
    append_space: "tac_appendSpace",
    always_space_at_end: "tac_alwaysSpaceAtEnd",
    underscore_exclusions: "tac_undersocreReplacementExclusionList",
    anima_artist_prefix: "tac_animaArtistPrefix",
};

let tacJpPresetData = null;
let tacJpFileData = null;
let tacJpUiBusy = false;
let tacJpInitPromise = null;
let tacJpLastDataLoad = 0;

const TACJP_UI_TEXT = {
    en: {
        title: "Multi-CSV options",
        subtitle: "User presets and additional controls",
        coreTitle: "TagComplete Neo core settings",
        coreSubtitle: "Original autocomplete, providers and insertion controls",
        preset: "User preset",
        newPreset: "New preset",
        language: "Interface language",
        mode: "Mode",
        tagFilesShort: "Tag files",
        translationsShort: "Translations",
        applySelection: "Apply selection",
        apply: "Load",
        noPresets: "No saved presets",
        namePlaceholder: "Preset name",
        saveAsNew: "Save",
        delete: "Delete",
        backup: "Backup",
        downloadBackup: "Download backup",
        saveBackupAs: "Save backup as…",
        importBackup: "Import backup",
        note: "Saved in tags/config/presets.json. Presets apply to autocomplete immediately without reloading Forge Neo.",
        enterName: "Enter a new preset name",
        noPresetSelected: "Select a saved user preset first.",
        confirmDelete: 'Delete preset "{name}"?',
        confirmOverwrite: 'Preset "{name}" already exists. Overwrite it?',
        saved: "Saved: {name}",
        deleted: "Deleted: {name}",
        restoredExclusions: "Underscore exclusions restored",
        imported: "Imported: {name}",
        backupSaved: "Backup saved",
        applied: "Applied: {name}",
        tagMode: "Tag priority",
        hybridMode: "Auto (Hybrid)",
        naturalMode: "Natural language priority",
        neutralMode: "Equal priority",
        tagFilesLabel: "Tag files (multiple selection)",
        translationFilesLabel: "Translation files (multiple selection)",
        promptModeLabel: "Prompt mode",
        showTranslationsLabel: "Display translations in suggestions",
        showSourceLabelsLabel: "Show source labels (TAG / NL / CUSTOM)",
        colorNaturalLabel: "Mark natural-language suggestions",
        quickControlsLabel: "Show user preset controls near prompts",
        animaPrefixLabel: "Add '@' to artist tags",
        restoreExclusions: "Restore default exclusions",
        coreAdvancedTitle: "TagComplete Neo interface settings",
        coreAdvancedSubtitle: "Hotkeys and suggestion colors",
        coreAdvancedNote: "Keep the defaults unless you need to customize keyboard controls or category colors.",
        multiAdvancedTitle: "Multi-CSV search settings",
        multiAdvancedSubtitle: "Server search, cache, and timing diagnostics",
        multiAdvancedNote: "Keep the recommended defaults. Change these only when troubleshooting Multi-CSV search.",
        maintenanceLabel: "Internal list maintenance",
        quickSummary: "TagComplete Neo Multi-CSV — preset / CSV / mode",
    },
    ja: {
        title: "Multi-CSV設定",
        subtitle: "ユーザープリセットと追加機能",
        coreTitle: "TagComplete Neo基本設定",
        coreSubtitle: "従来の補完・プロバイダー・挿入設定",
        preset: "ユーザープリセット",
        newPreset: "新規プリセット",
        language: "表示言語",
        mode: "モード",
        tagFilesShort: "タグファイル",
        translationsShort: "翻訳",
        applySelection: "選択を適用",
        apply: "ロード",
        noPresets: "保存済みプリセットなし",
        namePlaceholder: "プリセット名",
        saveAsNew: "保存",
        delete: "削除",
        backup: "バックアップ",
        downloadBackup: "バックアップを保存",
        saveBackupAs: "名前を付けて保存…",
        importBackup: "バックアップを読込",
        note: "保存先: tags/config/presets.json。Forge Neoをリロードせず、補完動作へ即時適用します。",
        enterName: "新しいプリセット名を入力してください",
        noPresetSelected: "保存済みユーザープリセットを選択してください。",
        confirmDelete: 'プリセット「{name}」を削除しますか？',
        confirmOverwrite: 'プリセット「{name}」は既に存在します。上書きしますか？',
        saved: "保存しました: {name}",
        deleted: "削除しました: {name}",
        restoredExclusions: "アンダースコア除外設定を復元しました",
        imported: "読み込みました: {name}",
        backupSaved: "バックアップを保存しました",
        applied: "適用しました: {name}",
        tagMode: "タグ優先",
        hybridMode: "自動判定（Hybrid）",
        naturalMode: "自然言語優先",
        neutralMode: "同等（優先なし）",
        tagFilesLabel: "タグファイル（複数選択）",
        translationFilesLabel: "翻訳ファイル（複数選択）",
        promptModeLabel: "プロンプトモード",
        showTranslationsLabel: "候補に翻訳を表示",
        showSourceLabelsLabel: "辞書種別を表示（TAG / NL / CUSTOM）",
        colorNaturalLabel: "自然言語候補を識別表示",
        quickControlsLabel: "プロンプト付近にユーザープリセットを表示",
        animaPrefixLabel: "アーティストタグに「@」を付ける",
        restoreExclusions: "標準の除外設定を復元",
        coreAdvancedTitle: "TagComplete Neoインターフェース設定",
        coreAdvancedSubtitle: "ホットキーと候補色",
        coreAdvancedNote: "通常は初期値のまま使用し、操作キーやカテゴリ色を変更するときだけ開きます。",
        multiAdvancedTitle: "Multi-CSV検索設定",
        multiAdvancedSubtitle: "サーバー検索・キャッシュ・計測",
        multiAdvancedNote: "通常は推奨初期値のまま使用し、Multi-CSV検索の不具合調査時だけ変更します。",
        maintenanceLabel: "内部一覧のメンテナンス",
        quickSummary: "TagComplete Neo Multi-CSV — プリセット / CSV / モード",
    },
};

const TACJP_CORE_LABELS = {
    tacjp_promptMode: ["Prompt mode", "プロンプトモード"],
    tac_animaArtistPrefix: ["Add '@' to artist tags", "アーティストタグに「@」を付ける"],
    tac_active: ["Enable Tag Autocompletion", "タグ自動補完を有効化"],
    "tac_activeIn.txt2img": ["Active in txt2img", "txt2imgで有効"],
    "tac_activeIn.img2img": ["Active in img2img", "img2imgで有効"],
    "tac_activeIn.negativePrompts": ["Active in negative prompts", "ネガティブプロンプトで有効"],
    "tac_activeIn.thirdParty": ["Active in third party textboxes", "外部拡張の入力欄で有効"],
    "tac_activeIn.modelList": ["Black/Whitelist models", "モデルのブラック／ホワイトリスト"],
    "tac_activeIn.modelListMode": ["Mode to use for model list", "モデルリストの動作"],
    tac_slidingPopup: ["Move completion popup together with text cursor", "入力位置に合わせて候補を移動"],
    tac_maxResults: ["Maximum results", "最大候補数"],
    tac_showAllResults: ["Show all results", "すべての候補を表示"],
    tac_resultStepLength: ["How many results to load at once", "一度に読み込む候補数"],
    tac_delayTime: ["Time in ms to wait before triggering completion again", "再検索までの待機時間（ms）"],
    tac_useIndexedSearch: ["Use indexed search (faster, recommended for slower PCs / mobile)", "インデックス検索を使用"],
    tac_useWildcards: ["Search for wildcards", "ワイルドカードを検索"],
    tac_sortWildcardResults: ["Sort wildcard file contents alphabetically", "ワイルドカード候補を名前順に並べる"],
    tac_wildcardExclusionList: ["Wildcard folder exclusion list", "ワイルドカード除外フォルダー"],
    tac_skipWildcardRefresh: ["Don't re-scan wildcard files when refreshing extra networks", "追加ネットワーク更新時にワイルドカードを再走査しない"],
    tac_useEmbeddings: ["Search for embeddings", "Embeddingを検索"],
    tac_forceRefreshEmbeddings: ["Force refresh embeddings with extra networks refresh", "追加ネットワーク更新時にEmbeddingを強制更新"],
    tac_includeEmbeddingsInNormalResults: ["Include embeddings in normal tag results", "通常候補にEmbeddingを含める"],
    tac_useLoras: ["Search for Loras", "LoRAを検索"],
    tac_useLycos: ["Search for LyCORIS/LoHa", "LyCORIS／LoHaを検索"],
    tac_useLoraPrefixForLycos: ["Use the '<lora:' prefix instead of '<lyco:' for LyCORIS", "LyCORISに「<lora:」接頭辞を使用"],
    tac_showWikiLinks: ["Show '?' links to Danbooru/e621 wiki pages", "Danbooru／e621 Wikiリンクを表示"],
    tac_showExtraNetworkPreviews: ["Show preview thumbnails for extra networks", "追加ネットワークのプレビューを表示"],
    tac_modelSortOrder: ["Model sort order", "モデルの並び順"],
    tac_useStyleVars: ["Search for WebUI style names", "WebUIスタイル名を検索"],
    tac_frequencySort: ["Locally record tag usage and sort frequent tags higher", "使用頻度を記録して候補順へ反映"],
    tac_frequencyFunction: ["Frequency sorting function", "使用頻度の並べ替え方式"],
    tac_frequencyMinCount: ["Minimum uses before frequency bias", "頻度補正を開始する最小使用回数"],
    tac_frequencyMaxAge: ["Maximum age in days for frequency bias", "頻度補正の最大経過日数"],
    tac_frequencyRecommendCap: ["Maximum number of frequency recommendations", "頻度推薦の最大件数"],
    tac_frequencyIncludeAlias: ["Frequency sorting matches aliases", "Aliasの使用も頻度へ反映"],
    tac_replaceUnderscores: ["Replace underscores with spaces on insertion", "挿入時にアンダースコアを空白へ変換"],
    tac_undersocreReplacementExclusionList: ["Underscore replacement exclusion patterns", "アンダースコア変換の除外パターン"],
    tac_escapeParentheses: ["Escape parentheses on insertion", "挿入時に括弧をエスケープ"],
    tac_appendComma: ["Append comma on tag/phrase completion", "タグ／フレーズ補完時にカンマを追加"],
    tac_appendSpace: ["Append space after separator", "区切り文字の後に空白を追加"],
    tac_alwaysSpaceAtEnd: ["Always append space at the end of the prompt", "プロンプト末尾に常に空白を追加"],
    tac_modelKeywordCompletion: ["Try to add known trigger words for LORA/LyCO models", "LoRA／LyCOの既知トリガーワードを追加"],
    tac_modelKeywordLocation: ["Where to insert LoRA/LyCO trigger words", "LoRA／LyCOトリガーワードの挿入位置"],
    tac_modelKeywordCivitai: ["Fetch trigger words from CivitAI when absent locally", "ローカルにないトリガーワードをCivitAIから取得"],
    tac_civitaiApiKey: ["CivitAI API key for trigger word lookups", "トリガーワード検索用CivitAI APIキー"],
    tac_wildcardCompletionMode: ["How to complete nested wildcard paths", "入れ子ワイルドカードパスの補完方法"],
    "tac_alias.searchByAlias": ["Search by alias", "Aliasで検索"],
    "tac_alias.onlyShowAlias": ["Only show alias", "Aliasだけを表示"],
    "tac_translation.oldFormat": ["Legacy translation file uses old 3-column format", "旧3列形式の翻訳ファイルを使用"],
    "tac_translation.searchByTranslation": ["Search by translation", "翻訳で検索"],
    "tac_translation.liveTranslation": ["Show live translation below prompt", "プロンプト下にリアルタイム翻訳を表示"],
    "tac_extra.extraFile": ["Extra filename", "追加タグファイル"],
    "tac_extra.addMode": ["Mode to add extra tags", "追加タグの挿入位置"],
    tac_chantFile: ["Chant filename", "Chantファイル"],
    tac_keymap: ["Configure hotkeys (JSON)", "ホットキー設定（JSON）"],
    tac_colormap: ["Configure suggestion colors (JSON)", "候補色設定（JSON）"],
};

const TACJP_INFO_LABELS = [
    [
        "(Files under tags/tag_files. Selection order is source priority.)",
        "（tags/tag_files内のファイル。選択順がソース優先順位です。）",
    ],
    [
        "(Optional files under tags/translation_files. Leave empty when translations are not needed.)",
        "（tags/translation_files内の任意ファイル。翻訳が不要な場合は空欄にします。）",
    ],
    ["(requires restart)", "（再起動が必要）"],
    [
        "(Model names [with file extension] or hashes, separated by commas)",
        "（モデル名［拡張子付き］またはハッシュをカンマ区切りで指定）",
    ],
    [
        "(Comma/newline separated. Supports * and ?. Wildcard syntax such as __folder/name__ is always preserved.)",
        "（カンマ／改行区切り。* と ? に対応。__folder/name__形式は常に維持されます。）",
    ],
    ["(Experimental)", "（試験的機能）"],
    [
        "(Candidates returned before local frequency sorting. 200–300 is recommended.)",
        "（ローカル頻度順の適用前に返す候補数。200～300を推奨。）",
    ],
    [
        "(Reuses indexes after WebUI restart and rebuilds only when a selected CSV changes.)",
        "（WebUI再起動後もインデックスを再利用し、選択CSV変更時だけ再構築します。）",
    ],
];

function tacJpLanguage() {
    const preference = String(opts["tacjp_uiLanguage"] || TAC_CFG?.uiLanguage || "Auto");
    if (preference === "Japanese") return "ja";
    if (preference === "English") return "en";
    const webuiLocale = String(opts.localization || "").trim();
    if (webuiLocale && webuiLocale.toLowerCase() !== "none") {
        return webuiLocale.toLowerCase().startsWith("ja") ? "ja" : "en";
    }
    const detected = String(
        document.documentElement.lang
        || navigator.language
        || "en"
    ).toLowerCase();
    return detected.startsWith("ja") ? "ja" : "en";
}

function tacJpText(key, values = {}) {
    let text = TACJP_UI_TEXT[tacJpLanguage()]?.[key] || TACJP_UI_TEXT.en[key] || key;
    Object.entries(values).forEach(([name, value]) => {
        text = text.replaceAll(`{${name}}`, String(value));
    });
    return text;
}

async function tacJpFetch(url, options = {}) {
    const response = await fetch(url, {
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
        ...options,
    });
    let data = {};
    try { data = await response.json(); } catch { /* no body */ }
    if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data;
}

function tacJpLiveTokens(option, fallback) {
    const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
    if (!root) return optionList(fallback);
    const values = [...root.querySelectorAll(".token > span")]
        .map(node => node.textContent.trim())
        .filter(Boolean);
    return values.length || root.querySelector(".token") ? values : optionList(fallback);
}

function tacJpLiveValue(option, fallback) {
    const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
    const input = root?.querySelector("textarea, input:not([type='checkbox'])");
    return input && input.value !== "" ? input.value : fallback;
}

function tacJpLiveChecked(option, fallback) {
    const input = gradioApp().querySelector(
        `#${CSS.escape(`setting_${option}`)} input[type='checkbox']`
    );
    return input ? input.checked : fallback;
}

function tacJpDispatchInput(input, value) {
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", {bubbles: true}));
    input.dispatchEvent(new Event("change", {bubbles: true}));
}

async function tacJpChooseGradioOption(option, label) {
    const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
    const input = root?.querySelector("input");
    if (!input) return false;
    input.focus();
    tacJpDispatchInput(input, label);
    for (let attempt = 0; attempt < 12; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 25));
        const candidate = [...gradioApp().querySelectorAll("[role='option']")]
            .find(node => node.textContent.trim() === label && node.getClientRects().length);
        if (candidate) {
            candidate.click();
            return true;
        }
    }
    return false;
}

async function tacJpSyncGradioMultiselect(option, values) {
    const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
    if (!root) return;
    const expected = optionList(values);
    const current = [...root.querySelectorAll(".token > span")].map(node => node.textContent.trim());
    if (JSON.stringify(current) === JSON.stringify(expected)) return;
    root.querySelector(".remove-all")?.click();
    for (const value of expected) {
        if (!await tacJpChooseGradioOption(option, value)) {
            console.warn(`[TagComplete Neo Multi-CSV] Could not reflect ${value} in ${option}.`);
        }
    }
}

async function tacJpSyncSettingsUi(settings) {
    await tacJpSyncGradioMultiselect("tacjp_tagFiles", settings.tag_files);
    await tacJpSyncGradioMultiselect("tacjp_translationFiles", settings.translation_files);

    const promptLabels = {
        Tag: "Tag priority",
        Hybrid: "Auto (Hybrid)",
        "Natural Language": "Natural language priority",
        Custom: "Equal priority",
    };
    const prefixLabels = {
        Off: "Off — never add '@'",
        On: "On — always add '@'",
        Auto: "Auto — only for detected ANIMA models",
    };
    const promptInput = gradioApp().querySelector("#setting_tacjp_promptMode input");
    if (promptInput && tacJpPromptMode(promptInput.value) !== settings.prompt_mode) {
        await tacJpChooseGradioOption("tacjp_promptMode", promptLabels[settings.prompt_mode] || settings.prompt_mode);
    }
    const prefixInput = gradioApp().querySelector("#setting_tac_animaArtistPrefix input");
    if (prefixInput && tacJpArtistPrefix(prefixInput.value) !== settings.anima_artist_prefix) {
        await tacJpChooseGradioOption("tac_animaArtistPrefix", prefixLabels[settings.anima_artist_prefix] || prefixLabels.Off);
    }

    [
        ["tac_translation.searchByTranslation", "search_translations"],
        ["tacjp_showTranslations", "show_translations"],
        ["tacjp_showSourceLabels", "show_source_labels"],
        ["tacjp_colorNaturalLanguage", "color_natural_language"],
        ["tac_replaceUnderscores", "replace_underscores"],
        ["tac_appendComma", "append_comma"],
        ["tac_appendSpace", "append_space"],
        ["tac_alwaysSpaceAtEnd", "always_space_at_end"],
    ].forEach(([option, key]) => {
        const input = gradioApp().querySelector(
            `#${CSS.escape(`setting_${option}`)} input[type='checkbox']`
        );
        if (!input || input.checked === !!settings[key]) return;
        input.checked = !!settings[key];
        input.dispatchEvent(new Event("input", {bubbles: true}));
        input.dispatchEvent(new Event("change", {bubbles: true}));
    });

    const exclusions = gradioApp().querySelector(
        `#${CSS.escape("setting_tac_undersocreReplacementExclusionList")} textarea`
    );
    if (exclusions && exclusions.value !== settings.underscore_exclusions) {
        tacJpDispatchInput(exclusions, settings.underscore_exclusions);
    }
}

function tacJpPromptMode(value) {
    const modes = {
        "Tag priority": "Tag",
        "タグ優先": "Tag",
        "Auto (Hybrid)": "Hybrid",
        "自動判定（Hybrid）": "Hybrid",
        "Natural language priority": "Natural Language",
        "自然言語優先": "Natural Language",
        "Equal priority": "Custom",
        "同等（優先なし）": "Custom",
    };
    return modes[value] || value || "Tag";
}

function tacJpArtistPrefix(value) {
    const text = String(value || "");
    if (text.startsWith("On") || text.startsWith("常時")) return "On";
    if (text.startsWith("Auto") || text.startsWith("自動")) return "Auto";
    return "Off";
}

function tacJpCurrentSettings() {
    const cfg = TAC_CFG || {};
    return {
        tag_files: tacJpLiveTokens("tacjp_tagFiles", cfg.tagFiles || opts["tacjp_tagFiles"] || []),
        translation_files: tacJpLiveTokens("tacjp_translationFiles", cfg.translation?.translationFiles || opts["tacjp_translationFiles"] || []),
        prompt_mode: tacJpPromptMode(tacJpLiveValue("tacjp_promptMode", cfg.promptMode || opts["tacjp_promptMode"] || "Tag")),
        search_translations: tacJpLiveChecked("tac_translation.searchByTranslation", cfg.translation?.searchByTranslation ?? opts["tac_translation.searchByTranslation"] ?? true),
        show_translations: tacJpLiveChecked("tacjp_showTranslations", cfg.showTranslations ?? opts["tacjp_showTranslations"] ?? true),
        show_source_labels: tacJpLiveChecked("tacjp_showSourceLabels", cfg.showSourceLabels ?? opts["tacjp_showSourceLabels"] ?? false),
        color_natural_language: tacJpLiveChecked("tacjp_colorNaturalLanguage", cfg.colorNaturalLanguage ?? opts["tacjp_colorNaturalLanguage"] ?? false),
        replace_underscores: tacJpLiveChecked("tac_replaceUnderscores", cfg.replaceUnderscores ?? opts["tac_replaceUnderscores"] ?? true),
        append_comma: tacJpLiveChecked("tac_appendComma", cfg.appendComma ?? opts["tac_appendComma"] ?? true),
        append_space: tacJpLiveChecked("tac_appendSpace", cfg.appendSpace ?? opts["tac_appendSpace"] ?? true),
        always_space_at_end: tacJpLiveChecked("tac_alwaysSpaceAtEnd", cfg.alwaysSpaceAtEnd ?? opts["tac_alwaysSpaceAtEnd"] ?? true),
        underscore_exclusions: tacJpLiveValue("tac_undersocreReplacementExclusionList", cfg.replaceUnderscoresExclusionList || opts["tac_undersocreReplacementExclusionList"] || TACJP_DEFAULT_EXCLUSIONS),
        anima_artist_prefix: tacJpArtistPrefix(tacJpLiveValue("tac_animaArtistPrefix", cfg.animaArtistPrefix || opts["tac_animaArtistPrefix"] || "Off")),
    };
}

function tacJpSetLocalSettings(settings, activePreset = null) {
    Object.entries(TACJP_OPTION_MAP).forEach(([source, option]) => {
        if (Object.prototype.hasOwnProperty.call(settings, source)) opts[option] = settings[source];
    });
    if (activePreset) opts["tacjp_activePreset"] = activePreset;
}

async function tacJpApplySettings(settings, activePreset = "", persist = true) {
    if (tacJpUiBusy) return;
    tacJpUiBusy = true;
    try {
        let validated = settings;
        if (persist) {
            const response = await tacJpFetch("tacjp/v1/options/apply", {
                method: "POST",
                body: JSON.stringify({settings, active_preset: activePreset}),
            });
            validated = response.settings || settings;
        }
        tacJpSetLocalSettings(validated, activePreset);
        if (TAC_CFG) await syncOptions();
        refreshTacJpControls();
        tacJpSetStatus(tacJpText("applied", {name: activePreset}));
    } finally {
        tacJpUiBusy = false;
    }
}

async function tacJpApplyPreset(name) {
    if (!name) return;
    if (tacJpUiBusy) return;
    tacJpUiBusy = true;
    try {
        const response = await tacJpFetch("tacjp/v1/presets/apply", {
            method: "POST",
            body: JSON.stringify({name}),
        });
        const settings = response.settings || {};
        const current = await tacJpFetch("tacjp/v1/current-settings");
        const expected = JSON.stringify(settings);
        const actual = JSON.stringify(current);
        if (expected !== actual) {
            throw new Error(`Preset "${name}" was saved but could not be loaded.`);
        }
        tacJpSetLocalSettings(settings, name);
        if (TAC_CFG) await syncOptions();
        await tacJpSyncSettingsUi(settings);
        refreshTacJpControls();
        tacJpSetStatus(tacJpText("applied", {name}));
    } finally {
        tacJpUiBusy = false;
    }
}

async function tacJpLoadData() {
    const [presets, files] = await Promise.all([
        tacJpFetch("tacjp/v1/presets"),
        tacJpFetch("tacjp/v1/files"),
    ]);
    tacJpPresetData = presets;
    tacJpFileData = files;
    return {presets, files};
}

function tacJpSetStatus(message, error = false) {
    gradioApp().querySelectorAll(".tacjp-status").forEach(node => {
        node.textContent = message;
        node.style.color = error ? "#ef4444" : "var(--body-text-color, inherit)";
    });
}

function tacJpCreateBadge(text, className) {
    const badge = document.createElement("span");
    badge.className = `tacjp-badge ${className}`.trim();
    badge.textContent = text;
    return badge;
}

function tacJpCreateSectionMarker() {
    const marker = document.createElement("div");
    marker.className = "tacjp-section-marker tacjp-section-core";
    const copy = document.createElement("span");
    copy.className = "tacjp-section-copy";
    const title = document.createElement("strong");
    const subtitle = document.createElement("small");
    title.textContent = tacJpText("coreTitle");
    subtitle.textContent = tacJpText("coreSubtitle");
    marker.append(tacJpCreateBadge("CORE", "tacjp-badge-core"));
    copy.append(title, subtitle);
    marker.append(copy);
    return marker;
}

function tacJpSetDirectLabelText(node, text) {
    if (!node) return;
    const directText = [...node.childNodes].find(child => child.nodeType === Node.TEXT_NODE && child.nodeValue.trim());
    if (directText) {
        if (directText.nodeValue !== text) directText.nodeValue = text;
    }
}

function tacJpFindStableLabel(root) {
    if (!root) return null;
    const candidates = root.querySelectorAll(
        ".block-info, [data-testid='block-info'], label .ml-2, [data-testid='block-label']"
    );
    return [...candidates].find(node =>
        [...node.childNodes].some(child =>
            child.nodeType === Node.TEXT_NODE && child.nodeValue.trim()
        )
    ) || null;
}

function tacJpDecorateAddedSettings() {
    const settings = [
        ["tacjp_tagFiles", "tagFilesLabel"],
        ["tacjp_translationFiles", "translationFilesLabel"],
        ["tacjp_promptMode", "promptModeLabel"],
        ["tacjp_showTranslations", "showTranslationsLabel"],
        ["tacjp_showSourceLabels", "showSourceLabelsLabel"],
        ["tacjp_colorNaturalLanguage", "colorNaturalLabel"],
        ["tac_animaArtistPrefix", "animaPrefixLabel"],
    ];
    settings.forEach(([option, textKey]) => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        if (!root) return;
        const label = tacJpFindStableLabel(root);
        if (!label) return;
        const svelteOwnedLabel = label.matches("[data-testid='block-info']") && !label.closest("label");
        if (!svelteOwnedLabel) tacJpSetDirectLabelText(label, tacJpText(textKey));
        if (svelteOwnedLabel) {
            root.classList.add("tacjp-label-badge-after");
        } else if (!label.querySelector(".tacjp-badge-jpplus")) {
            const badge = tacJpCreateBadge("CSV+", "tacjp-badge-jpplus");
            label.appendChild(badge);
        }
    });

    [
        "tacjp_searchEngine",
        "tacjp_serverResultPool",
        "tacjp_persistentSearchCache",
        "tacjp_searchMemoryEntries",
        "tacjp_searchDiskEntries",
        "tacjp_searchDebug",
        "tacjp_clearSearchCache",
    ].forEach(option => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        const label = tacJpFindStableLabel(root);
        if (!root || !label) return;
        const svelteOwnedLabel = label.matches("[data-testid='block-info']") && !label.closest("label");
        if (svelteOwnedLabel) {
            root.classList.add("tacjp-label-badge-after");
        } else if (!label.querySelector(".tacjp-badge-jpplus")) {
            const badge = tacJpCreateBadge("CSV+", "tacjp-badge-jpplus");
            label.appendChild(badge);
        }
    });

    const exclusionRoot = gradioApp().querySelector(
        `#${CSS.escape("setting_tac_undersocreReplacementExclusionList")}`
    );
    if (exclusionRoot) {
        let button = exclusionRoot.querySelector(".tacjp-restore-exclusions");
        if (!button) {
            button = tacJpButton(tacJpText("restoreExclusions"), async () => {
                const settings = {...tacJpCurrentSettings(), underscore_exclusions: TACJP_DEFAULT_EXCLUSIONS};
                await tacJpApplySettings(settings, opts["tacjp_activePreset"] || "", true);
                tacJpSetStatus(tacJpText("restoredExclusions"));
            }, "tacjp-action-restore tacjp-restore-exclusions");
            button.appendChild(tacJpCreateBadge("CSV+", "tacjp-badge-jpplus"));
            exclusionRoot.appendChild(button);
        }
        tacJpSetDirectLabelText(button, tacJpText("restoreExclusions"));
    }

    ["tac_extra.extraFile", "tac_chantFile"].forEach(option => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        root?.parentElement?.parentElement?.classList.add("tacjp-inline-refresh-row");
    });
}

function tacJpCreateAdvancedPanel(kind, titleKey, subtitleKey, noteKey) {
    const details = document.createElement("details");
    details.className = `tacjp-advanced-panel tacjp-${kind}-advanced`;
    const summary = document.createElement("summary");
    summary.className = "tacjp-advanced-summary";
    const copy = document.createElement("span");
    copy.className = "tacjp-advanced-copy";
    const title = document.createElement("strong");
    title.className = "tacjp-advanced-title";
    const subtitle = document.createElement("small");
    subtitle.className = "tacjp-advanced-subtitle";
    copy.append(title, subtitle);
    const badge = kind === "core"
        ? tacJpCreateBadge("CORE", "tacjp-badge-core")
        : tacJpCreateBadge("CSV+", "tacjp-badge-jpplus");
    summary.append(badge, copy);
    const note = document.createElement("div");
    note.className = "tacjp-advanced-note";
    const body = document.createElement("div");
    body.className = "tacjp-advanced-body";
    details.append(summary, note, body);
    details.dataset.titleKey = titleKey;
    details.dataset.subtitleKey = subtitleKey;
    details.dataset.noteKey = noteKey;
    return details;
}

function tacJpUpdateAdvancedPanelText(details) {
    details.querySelector(".tacjp-advanced-title").textContent = tacJpText(details.dataset.titleKey);
    details.querySelector(".tacjp-advanced-subtitle").textContent = tacJpText(details.dataset.subtitleKey);
    details.querySelector(".tacjp-advanced-note").textContent = tacJpText(details.dataset.noteKey);
}

function tacJpMoveSettingRows(target, options) {
    options.forEach(option => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        if (!root) return;
        const row = root.closest(".gradio-row") || root;
        if (row.parentElement !== target) target.appendChild(row);
    });
}

function tacJpGroupAdvancedSettings(settingsContainer) {
    if (!settingsContainer) return;
    let corePanel = settingsContainer.querySelector(".tacjp-core-advanced");
    if (!corePanel) {
        corePanel = tacJpCreateAdvancedPanel(
            "core", "coreAdvancedTitle", "coreAdvancedSubtitle", "coreAdvancedNote"
        );
        settingsContainer.appendChild(corePanel);
    }
    let multiPanel = settingsContainer.querySelector(".tacjp-multicsv-advanced");
    if (!multiPanel) {
        multiPanel = tacJpCreateAdvancedPanel(
            "multicsv", "multiAdvancedTitle", "multiAdvancedSubtitle", "multiAdvancedNote"
        );
        settingsContainer.appendChild(multiPanel);
    }

    tacJpUpdateAdvancedPanelText(corePanel);
    tacJpUpdateAdvancedPanelText(multiPanel);
    const coreBody = corePanel.querySelector(".tacjp-advanced-body");
    const multiBody = multiPanel.querySelector(".tacjp-advanced-body");
    tacJpMoveSettingRows(coreBody, ["tac_keymap", "tac_colormap"]);

    let maintenance = coreBody.querySelector(".tacjp-maintenance-label");
    if (!maintenance) {
        maintenance = document.createElement("div");
        maintenance.className = "tacjp-maintenance-label";
        coreBody.appendChild(maintenance);
    }
    maintenance.textContent = tacJpText("maintenanceLabel");
    tacJpMoveSettingRows(coreBody, ["tac_refreshTempFiles"]);

    tacJpMoveSettingRows(multiBody, [
        "tacjp_searchEngine",
        "tacjp_serverResultPool",
        "tacjp_persistentSearchCache",
        "tacjp_searchMemoryEntries",
        "tacjp_searchDiskEntries",
        "tacjp_searchDebug",
        "tacjp_clearSearchCache",
    ]);

    const oldPanel = settingsContainer.querySelector(".tacjp-advanced-settings");
    if (oldPanel && !oldPanel.querySelector("[id^='setting_']")) oldPanel.remove();
}

function tacJpDecorateCoreSettings() {
    const languageIndex = tacJpLanguage() === "ja" ? 1 : 0;
    Object.entries(TACJP_CORE_LABELS).forEach(([option, labels]) => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        if (!root) return;
        root.querySelectorAll(".tacjp-setting-label-text").forEach(node => node.remove());
        const label = tacJpFindStableLabel(root);
        if (label) tacJpSetDirectLabelText(label, labels[languageIndex]);
    });
    gradioApp().querySelectorAll("#settings_tac .settings-comment .info").forEach(node => {
        const current = node.textContent.trim();
        const labels = TACJP_INFO_LABELS.find(pair => pair.includes(current));
        if (labels) node.textContent = labels[languageIndex];
    });
}

function tacJpFillSelect(select, entries, selectedValues = []) {
    if (!select) return;
    const selected = new Set(selectedValues || []);
    select.innerHTML = "";
    entries.forEach(entry => {
        const option = document.createElement("option");
        option.value = entry;
        option.textContent = entry;
        option.selected = selected.has(entry);
        select.appendChild(option);
    });
}

function tacJpFillPresetSelect(select, current = null) {
    if (!select || !tacJpPresetData) return;
    const selected = current || opts["tacjp_activePreset"] || tacJpPresetData.active || "";
    const names = Object.keys(tacJpPresetData.users || {});
    select.innerHTML = "";
    if (!names.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = tacJpText("noPresets");
        option.selected = true;
        select.appendChild(option);
        select.disabled = true;
        return;
    }
    select.disabled = false;
    names.forEach(name => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        option.selected = name === selected;
        select.appendChild(option);
    });
    if (!select.value && names.length) select.value = names[0];
}

function refreshTacJpControls() {
    const current = tacJpCurrentSettings();
    gradioApp().querySelectorAll(".tacjp-preset-select").forEach(select => tacJpFillPresetSelect(select));
    gradioApp().querySelectorAll(".tacjp-mode-select").forEach(select => { select.value = current.prompt_mode; });
    gradioApp().querySelectorAll(".tacjp-tag-files").forEach(select => {
        tacJpFillSelect(select, (tacJpFileData?.tag_files || []).map(x => x.name), current.tag_files);
    });
    gradioApp().querySelectorAll(".tacjp-translation-files").forEach(select => {
        tacJpFillSelect(select, (tacJpFileData?.translation_files || []).map(x => x.name), current.translation_files);
    });
}

function tacJpButton(text, action, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.className = `tacjp-button ${className}`.trim();
    button.addEventListener("click", async event => {
        event.preventDefault();
        try { await action(); } catch (error) { tacJpSetStatus(error.message, true); }
    });
    return button;
}

async function tacJpDownloadBackup(saveAs = false) {
    const data = await tacJpFetch("tacjp/v1/presets/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
    if (saveAs && typeof window.showSaveFilePicker === "function") {
        try {
            const handle = await window.showSaveFilePicker({
                suggestedName: "tagcomplete-jp-presets.json",
                types: [{
                    description: "JSON",
                    accept: {"application/json": [".json"]},
                }],
            });
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
            tacJpSetStatus(tacJpText("backupSaved"));
            return;
        } catch (error) {
            if (error?.name === "AbortError") return;
            console.warn("[TagComplete Neo Multi-CSV] Save As unavailable; using browser download.", error);
        }
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "tagcomplete-jp-presets.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    tacJpSetStatus(tacJpText("backupSaved"));
}

function tacJpCreateModeSelect() {
    const select = document.createElement("select");
    select.className = "tacjp-mode-select";
    [
        ["Tag", tacJpText("tagMode")],
        ["Hybrid", tacJpText("hybridMode")],
        ["Natural Language", tacJpText("naturalMode")],
        ["Custom", tacJpText("neutralMode")],
    ].forEach(([mode, label]) => {
        const option = document.createElement("option");
        option.value = mode;
        option.textContent = label;
        select.appendChild(option);
    });
    return select;
}

function tacJpCreateSettingsManager(open = false) {
    const wrapper = document.createElement("div");
    wrapper.className = "tacjp-manager-shell";
    const details = document.createElement("details");
    details.className = "tacjp-manager";
    details.open = open;
    const summary = document.createElement("summary");
    summary.className = "tacjp-manager-summary";
    const icon = document.createElement("span");
    icon.className = "tacjp-brand-icon";
    icon.textContent = "MC";
    const heading = document.createElement("span");
    heading.className = "tacjp-manager-heading";
    const title = document.createElement("strong");
    title.textContent = tacJpText("title");
    const subtitle = document.createElement("small");
    subtitle.textContent = tacJpText("subtitle");
    heading.append(title, subtitle, tacJpCreateBadge("CSV+", "tacjp-badge-jpplus"));
    summary.append(icon, heading);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "tacjp-manager-body";
    const status = document.createElement("span");
    status.className = "tacjp-status";

    const languageRow = document.createElement("div");
    languageRow.className = "tacjp-row tacjp-language-row";
    const languageLabel = document.createElement("span");
    languageLabel.textContent = `${tacJpText("language")}:`;
    const languageSelect = document.createElement("select");
    languageSelect.className = "tacjp-language-select";
    const languagePreference = String(opts["tacjp_uiLanguage"] || TAC_CFG?.uiLanguage || "Auto");
    [
        ["Auto", "Auto"],
        ["Japanese", "日本語"],
        ["English", "English"],
    ].forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        option.selected = value === languagePreference;
        languageSelect.appendChild(option);
    });
    languageSelect.addEventListener("change", async () => {
        const wasOpen = details.open;
        const response = await tacJpFetch("tacjp/v1/ui-language", {
            method: "POST",
            body: JSON.stringify({language: languageSelect.value}),
        });
        opts["tacjp_uiLanguage"] = response.language;
        if (TAC_CFG) TAC_CFG.uiLanguage = response.language;
        const replacement = tacJpCreateSettingsManager(wasOpen);
        wrapper.replaceWith(replacement);
        gradioApp().querySelectorAll(".tacjp-section-marker").forEach(marker => {
            marker.replaceWith(tacJpCreateSectionMarker());
        });
        tacJpDecorateAddedSettings();
        tacJpDecorateCoreSettings();
        const settingsContainer = gradioApp().querySelector("#settings_tac")
            || gradioApp().querySelector("#column_settings_tac")
            || gradioApp().querySelector("[id*='settings_tac']");
        tacJpGroupAdvancedSettings(settingsContainer);
        refreshTacJpControls();
    });
    languageRow.append(languageLabel, languageSelect);
    wrapper.appendChild(languageRow);

    // Preset controls are intentionally hidden in this release. Keep the
    // implementation below for the planned, fully reactive preset revision.
    return wrapper;

    const presetSelect = document.createElement("select");
    presetSelect.className = "tacjp-preset-select";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.placeholder = tacJpText("namePlaceholder");
    nameInput.className = "tacjp-name-input";

    const row1 = document.createElement("div");
    row1.className = "tacjp-row tacjp-preset-primary";
    const presetLabel = document.createElement("span");
    presetLabel.textContent = `${tacJpText("preset")}:`;
    const applyButton = tacJpButton(tacJpText("apply"), () => {
        if (!presetSelect.value) throw new Error(tacJpText("noPresetSelected"));
        return tacJpApplyPreset(presetSelect.value);
    }, "tacjp-action-primary");
    const deleteButton = tacJpButton(tacJpText("delete"), async () => {
        const name = presetSelect.value;
        if (!name) throw new Error(tacJpText("noPresetSelected"));
        if (!window.confirm(tacJpText("confirmDelete", {name}))) return;
        const response = await tacJpFetch(`tacjp/v1/presets/${encodeURIComponent(name)}`, {method: "DELETE"});
        if (!response.deleted) throw new Error(tacJpText("noPresetSelected"));
        await tacJpLoadData();
        if ((opts["tacjp_activePreset"] || "") === name) opts["tacjp_activePreset"] = "";
        refreshTacJpControls();
        updatePresetActionState();
        tacJpSetStatus(tacJpText("deleted", {name}));
    }, "tacjp-action-danger");
    row1.append(presetLabel, presetSelect, applyButton, deleteButton);

    const row2 = document.createElement("div");
    row2.className = "tacjp-row tacjp-preset-create";
    const newPresetLabel = document.createElement("span");
    newPresetLabel.textContent = `${tacJpText("newPreset")}:`;
    const saveAsButton = tacJpButton(tacJpText("saveAsNew"), async () => {
        const name = nameInput.value.trim();
        if (!name) throw new Error(tacJpText("enterName"));
        if (Object.prototype.hasOwnProperty.call(tacJpPresetData?.users || {}, name)
            && !window.confirm(tacJpText("confirmOverwrite", {name}))) return;
        await tacJpFetch("tacjp/v1/presets/save", {
            method: "POST",
            body: JSON.stringify({name, settings: tacJpCurrentSettings()}),
        });
        await tacJpLoadData();
        await tacJpApplyPreset(name);
        nameInput.value = "";
        refreshTacJpControls();
        updatePresetActionState();
        tacJpSetStatus(tacJpText("saved", {name}));
    }, "tacjp-action-success");
    row2.append(newPresetLabel, nameInput, saveAsButton);

    const updatePresetActionState = () => {
        const isUserPreset = Object.prototype.hasOwnProperty.call(tacJpPresetData?.users || {}, presetSelect.value);
        applyButton.disabled = !isUserPreset;
        deleteButton.disabled = !isUserPreset;
        [applyButton, deleteButton].forEach(button => {
            button.title = isUserPreset ? "" : tacJpText("noPresetSelected");
        });
    };
    presetSelect.addEventListener("change", updatePresetActionState);
    queueMicrotask(updatePresetActionState);

    const importInput = document.createElement("input");
    importInput.type = "file";
    importInput.accept = ".json,application/json";
    importInput.hidden = true;
    importInput.addEventListener("change", async () => {
        const file = importInput.files?.[0];
        if (!file) return;
        try {
            const data = JSON.parse(await file.text());
            await tacJpFetch("tacjp/v1/presets/import", {method: "POST", body: JSON.stringify({data, replace: false})});
            await tacJpLoadData();
            refreshTacJpControls();
            updatePresetActionState();
            tacJpSetStatus(tacJpText("imported", {name: file.name}));
        } catch (error) { tacJpSetStatus(error.message, true); }
        importInput.value = "";
    });

    const backupDetails = document.createElement("details");
    backupDetails.className = "tacjp-backup";
    const backupSummary = document.createElement("summary");
    backupSummary.textContent = tacJpText("backup");
    const backupActions = document.createElement("div");
    backupActions.className = "tacjp-row tacjp-buttons tacjp-backup-actions";
    backupActions.append(
        tacJpButton(tacJpText("downloadBackup"), () => tacJpDownloadBackup(false), "tacjp-action-backup"),
        tacJpButton(tacJpText("saveBackupAs"), () => tacJpDownloadBackup(true), "tacjp-action-backup"),
        tacJpButton(tacJpText("importBackup"), () => importInput.click(), "tacjp-action-backup"),
        importInput,
    );
    backupDetails.append(backupSummary, backupActions);

    const note = document.createElement("div");
    note.className = "tacjp-note";
    note.textContent = tacJpText("note");
    body.append(row1, row2, backupDetails, status, note);
    details.appendChild(body);
    wrapper.appendChild(details);
    return wrapper;
}

function tacJpCreateQuickControls(tabName) {
    const details = document.createElement("details");
    details.className = "tacjp-quick-controls";
    const summary = document.createElement("summary");
    summary.textContent = tacJpText("quickSummary");
    details.appendChild(summary);

    const grid = document.createElement("div");
    grid.className = "tacjp-quick-grid";
    const preset = document.createElement("select");
    preset.className = "tacjp-preset-select";
    const mode = tacJpCreateModeSelect();
    const tags = document.createElement("select");
    tags.multiple = true;
    tags.size = 4;
    tags.className = "tacjp-tag-files";
    const translationsSelect = document.createElement("select");
    translationsSelect.multiple = true;
    translationsSelect.size = 3;
    translationsSelect.className = "tacjp-translation-files";

    const labelled = (labelText, control) => {
        const label = document.createElement("label");
        const title = document.createElement("span");
        title.textContent = labelText;
        label.append(title, control);
        return label;
    };
    grid.append(
        labelled(tacJpText("preset"), preset),
        labelled(tacJpText("mode"), mode),
        labelled(tacJpText("tagFilesShort"), tags),
        labelled(tacJpText("translationsShort"), translationsSelect),
    );

    const actions = document.createElement("div");
    actions.className = "tacjp-row tacjp-buttons";
    actions.append(
        tacJpButton(tacJpText("apply"), () => tacJpApplyPreset(preset.value)),
        tacJpButton(tacJpText("applySelection"), () => {
            const settings = {
                ...tacJpCurrentSettings(),
                tag_files: [...tags.selectedOptions].map(x => x.value),
                translation_files: [...translationsSelect.selectedOptions].map(x => x.value),
                prompt_mode: mode.value,
            };
            return tacJpApplySettings(settings, "", true);
        }),
        (() => { const node = document.createElement("span"); node.className = "tacjp-status"; return node; })(),
    );
    details.append(grid, actions);
    details.dataset.tab = tabName;
    return details;
}

function tacJpInjectStyle() {
    if (document.getElementById("tacjp-style")) return;
    const style = document.createElement("style");
    style.id = "tacjp-style";
    style.textContent = `
        .tacjp-manager,.tacjp-quick-controls{border:1px solid color-mix(in srgb,var(--primary-500,#3b82f6) 48%,var(--block-border-color,#4b5563));border-radius:8px;margin:.25rem .35rem .6rem;padding:.48rem .65rem;background:color-mix(in srgb,var(--primary-500,#3b82f6) 5%,var(--block-background-fill,#111827));box-shadow:0 2px 7px rgba(0,0,0,.18)}
        .tacjp-manager-shell>.tacjp-language-row{margin:.6rem .6rem .2rem}
        .tacjp-manager-summary{display:flex;align-items:center;gap:.55rem;cursor:pointer;min-height:2rem;list-style-position:outside}
        .tacjp-manager-heading,.tacjp-section-copy{display:flex;align-items:baseline;gap:.45rem;min-width:0;line-height:1.12}
        .tacjp-manager-heading small,.tacjp-section-copy small{font-size:.72rem;font-weight:400;opacity:.72}
        .tacjp-brand-icon{display:inline-grid;place-items:center;flex:0 0 1.7rem;width:1.7rem;height:1.7rem;border-radius:6px;background:linear-gradient(180deg,#3b82f6,#1d4ed8);color:#fff;font-size:.72rem;font-weight:800;letter-spacing:.02em;box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 2px 4px rgba(0,0,0,.28)}
        .tacjp-badge{display:inline-flex;align-items:center;min-height:1rem;border-radius:4px;padding:.02rem .32rem;font-size:.58rem;font-weight:800;line-height:1;letter-spacing:.035em;white-space:nowrap}
        .tacjp-badge-jpplus{margin-left:.35rem;color:#c4b5fd;background:rgba(124,58,237,.18);border:1px solid #8b5cf6}
        .tacjp-label-badge-after [data-testid='block-info']::after{content:"CSV+";display:inline-flex;align-items:center;min-height:1rem;margin-left:.35rem;border:1px solid #8b5cf6;border-radius:4px;padding:.02rem .32rem;color:#c4b5fd;background:rgba(124,58,237,.18);font-size:.58rem;font-weight:800;line-height:1;letter-spacing:.035em;vertical-align:middle}
        .tacjp-manager-summary>.tacjp-badge-jpplus{margin-left:0}
        .tacjp-badge-core{background:#475569}
        .tacjp-section-marker{display:flex;align-items:center;gap:.55rem;margin:.7rem .35rem .4rem;padding:.42rem .65rem;border-radius:7px;border-left:4px solid}
        .tacjp-section-core{border-color:#64748b;background:color-mix(in srgb,#64748b 8%,transparent)}
        .tacjp-manager-body,.tacjp-quick-grid{display:grid;gap:.38rem;margin-top:.42rem;padding:.05rem .25rem .2rem}
        .tacjp-row{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
        .tacjp-row select,.tacjp-row input,.tacjp-quick-grid select{min-height:1.95rem;background:var(--input-background-fill,#1f2937)!important;color:var(--body-text-color,#f3f4f6)!important;-webkit-text-fill-color:var(--body-text-color,#f3f4f6);border:1px solid var(--input-border-color,#64748b);border-radius:6px;padding:.22rem .5rem;box-shadow:inset 0 1px 2px rgba(0,0,0,.25)}
        .tacjp-row input::placeholder{color:color-mix(in srgb,var(--body-text-color,#f3f4f6) 58%,transparent);opacity:1}
        .tacjp-row input:focus,.tacjp-row select:focus{outline:2px solid color-mix(in srgb,var(--primary-500,#3b82f6) 75%,transparent);outline-offset:1px}
        .tacjp-name-input{min-width:14rem}
        .tacjp-language-select{min-width:6.2rem}
        .tacjp-language-row{justify-content:flex-start}
        .tacjp-language-row>span,.tacjp-preset-primary>span,.tacjp-preset-create>span{flex:0 0 8.4rem}
        .tacjp-preset-primary select{min-width:10rem}.tacjp-preset-create{align-items:center}
        .tacjp-preset-manage{padding-top:.1rem}
        .tacjp-backup{width:max-content;max-width:100%;border:1px solid var(--block-border-color,#4b5563);border-radius:6px;padding:.28rem .5rem}
        .tacjp-backup>summary{cursor:pointer;font-size:.82rem;font-weight:650}
        .tacjp-backup-actions{padding-top:.45rem}
        .tacjp-button{min-height:1.95rem;border:1px solid rgba(255,255,255,.18);border-bottom-color:rgba(0,0,0,.55);border-radius:6px;padding:.25rem .58rem;color:#fff;cursor:pointer;font-weight:600;box-shadow:inset 0 1px 0 rgba(255,255,255,.22),0 2px 3px rgba(0,0,0,.3);text-shadow:0 1px 1px rgba(0,0,0,.28);transition:filter .12s ease,transform .06s ease,box-shadow .06s ease}
        .tacjp-button:hover{filter:brightness(1.12)}
        .tacjp-button:active{transform:translateY(1px);box-shadow:inset 0 1px 2px rgba(0,0,0,.28),0 1px 1px rgba(0,0,0,.2)}
        .tacjp-button:disabled{opacity:.42;cursor:not-allowed;filter:saturate(.45);box-shadow:none}
        .tacjp-action-primary{background:#2563eb}.tacjp-action-success{background:#16a34a}.tacjp-action-create{background:#0d9488}
        .tacjp-action-warning{background:#d97706}.tacjp-action-danger{background:#dc2626}.tacjp-action-restore{background:#7c3aed}
        .tacjp-action-neutral{background:#475569}.tacjp-action-info{background:#0284c7}.tacjp-action-backup{background:#4f46e5}
        .tacjp-restore-exclusions{margin:.35rem 0 0 .1rem;width:max-content}
        .tacjp-quick-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
        .tacjp-quick-grid label{display:flex;flex-direction:column;gap:.2rem;font-size:.85rem}
        .tacjp-quick-grid select[multiple]{min-height:5.4rem}
        .tacjp-status{font-size:.82rem;opacity:.9}
        .tacjp-note{font-size:.78rem;opacity:.75;line-height:1.35}
        .tacjp-advanced-panel{--tacjp-advanced-color:#64748b;border:1px solid color-mix(in srgb,var(--tacjp-advanced-color) 52%,var(--block-border-color,#4b5563));border-radius:8px;margin:.55rem .35rem;padding:.42rem .65rem;background:color-mix(in srgb,var(--tacjp-advanced-color) 5%,var(--block-background-fill,#111827))}
        .tacjp-core-advanced{--tacjp-advanced-color:#64748b}
        .tacjp-multicsv-advanced{--tacjp-advanced-color:#7c3aed;margin-bottom:.8rem}
        .tacjp-advanced-summary{display:flex;align-items:center;gap:.55rem;cursor:pointer;min-height:2rem}
        .tacjp-advanced-copy{display:flex;align-items:baseline;gap:.45rem}.tacjp-advanced-copy small{font-size:.72rem;font-weight:400;opacity:.72}
        .tacjp-advanced-note{margin:.55rem .15rem;padding:.45rem .6rem;border-left:3px solid var(--tacjp-advanced-color);background:color-mix(in srgb,var(--tacjp-advanced-color) 8%,transparent);font-size:.8rem;line-height:1.4}
        .tacjp-advanced-body{display:grid;gap:.35rem}
        .tacjp-maintenance-label{margin:.65rem .1rem .1rem;font-size:.82rem;font-weight:650;opacity:.82}
        .tacjp-inline-refresh-row{flex-wrap:nowrap!important;align-items:flex-end!important}.tacjp-inline-refresh-row>.form{min-width:0!important}.tacjp-inline-refresh-row>.tool{flex:0 0 auto!important}
        @media (max-width:720px){.tacjp-quick-grid{grid-template-columns:1fr}.tacjp-button{flex:1 1 auto}.tacjp-manager-heading,.tacjp-section-copy{align-items:flex-start;flex-direction:column;gap:.12rem}.tacjp-manager-heading small,.tacjp-section-copy small{display:none}}
    `;
    document.head.appendChild(style);
}

async function tacJpInitializeUI(forceReload = false) {
    if (tacJpInitPromise) return tacJpInitPromise;
    tacJpInitPromise = (async () => {
        try {
            const now = Date.now();
            if (forceReload || !tacJpPresetData || !tacJpFileData || now - tacJpLastDataLoad > 30000) {
                await tacJpLoadData();
                tacJpLastDataLoad = now;
            }
            tacJpInjectStyle();

            const settingsContainer = gradioApp().querySelector("#settings_tac")
                || gradioApp().querySelector("#column_settings_tac")
                || gradioApp().querySelector("[id*='settings_tac']");
            if (settingsContainer && !settingsContainer.querySelector(".tacjp-manager-shell")) {
                const manager = tacJpCreateSettingsManager();
                settingsContainer.prepend(manager);
                const coreSetting = settingsContainer.querySelector("#setting_tac_active")
                    || settingsContainer.querySelector("[id$='setting_tac_active']");
                if (coreSetting) coreSetting.insertAdjacentElement("beforebegin", tacJpCreateSectionMarker());
            }

            gradioApp().querySelectorAll(".tacjp-section-shared").forEach(node => node.remove());
            gradioApp().querySelectorAll(".tacjp-quick-controls").forEach(node => node.remove());
            refreshTacJpControls();
            tacJpDecorateAddedSettings();
            tacJpDecorateCoreSettings();
            tacJpGroupAdvancedSettings(settingsContainer);
        } catch (error) {
            console.error("[TagComplete Neo Multi-CSV] UI initialization failed", error);
        } finally {
            tacJpInitPromise = null;
        }
    })();
    return tacJpInitPromise;
}

QUEUE_AFTER_SETUP.push(async () => {
    await tacJpInitializeUI();
});
QUEUE_AFTER_CONFIG_CHANGE.push(async () => {
    await tacJpInitializeUI();
});

onUiUpdate(() => {
    if (!TAC_CFG) return;
    if (!gradioApp().querySelector(".tacjp-manager-shell")) {
        tacJpInitializeUI();
    } else {
        tacJpDecorateAddedSettings();
    }
});
