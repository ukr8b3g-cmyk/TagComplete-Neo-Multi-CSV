// TagComplete Neo Multi-CSV preset manager and optional quick controls.

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
        sharedTitle: "Shared data sources and modes",
        sharedSubtitle: "TagComplete Neo controls enhanced for multiple CSV sources",
        coreTitle: "TagComplete Neo core settings",
        coreSubtitle: "Original autocomplete, providers and insertion controls",
        preset: "User preset",
        language: "Interface language",
        mode: "Mode",
        tagFilesShort: "Tag files",
        translationsShort: "Translations",
        applySelection: "Apply selection",
        apply: "Apply",
        noPresets: "No saved presets",
        namePlaceholder: "New preset name",
        saveChanges: "Overwrite",
        saveAsNew: "Save new",
        rename: "Rename",
        delete: "Delete",
        backup: "Backup",
        downloadBackup: "Download backup",
        saveBackupAs: "Save backup as…",
        importBackup: "Import backup",
        note: "User presets apply immediately. Standard Settings controls reflect them after Reload UI.",
        enterName: "Enter a new preset name",
        enterDifferentName: "Enter a different preset name",
        noPresetSelected: "Select a saved user preset first.",
        confirmDelete: 'Delete preset "{name}"?',
        saved: "Saved: {name}",
        renamed: "Renamed: {oldName} → {newName}",
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
        quickSummary: "TagComplete Neo Multi-CSV — preset / CSV / mode",
    },
    ja: {
        title: "Multi-CSV設定",
        subtitle: "ユーザープリセットと追加機能",
        sharedTitle: "共通データソースとモード",
        sharedSubtitle: "複数CSV対応で拡張されたTagComplete Neo共通設定",
        coreTitle: "TagComplete Neo基本設定",
        coreSubtitle: "従来の補完・プロバイダー・挿入設定",
        preset: "ユーザープリセット",
        language: "表示言語",
        mode: "モード",
        tagFilesShort: "タグファイル",
        translationsShort: "翻訳",
        applySelection: "選択を適用",
        apply: "適用",
        noPresets: "保存済みプリセットなし",
        namePlaceholder: "新しいプリセット名",
        saveChanges: "上書き",
        saveAsNew: "新規保存",
        rename: "名前変更",
        delete: "削除",
        backup: "バックアップ",
        downloadBackup: "バックアップを保存",
        saveBackupAs: "名前を付けて保存…",
        importBackup: "バックアップを読込",
        note: "ユーザープリセットは即時適用されます。標準設定欄への反映はReload UI後です。",
        enterName: "新しいプリセット名を入力してください",
        enterDifferentName: "現在と異なるプリセット名を入力してください",
        noPresetSelected: "保存済みユーザープリセットを選択してください。",
        confirmDelete: 'プリセット「{name}」を削除しますか？',
        saved: "保存しました: {name}",
        renamed: "名前を変更しました: {oldName} → {newName}",
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
        quickSummary: "TagComplete Neo Multi-CSV — プリセット / CSV / モード",
    },
};

function tacJpLanguage() {
    const webuiLocale = String(opts.localization || "").trim();
    if (webuiLocale && webuiLocale.toLowerCase() !== "none") {
        return webuiLocale.toLowerCase().startsWith("ja") ? "ja" : "en";
    }
    const preference = String(opts["tacjp_uiLanguage"] || TAC_CFG?.uiLanguage || "Auto");
    if (preference === "Japanese") return "ja";
    if (preference === "English") return "en";
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

function tacJpAllPresets() {
    return {...(tacJpPresetData?.users || {})};
}

function tacJpCurrentSettings() {
    const cfg = TAC_CFG || {};
    return {
        tag_files: optionList(cfg.tagFiles || opts["tacjp_tagFiles"] || []),
        translation_files: optionList(cfg.translation?.translationFiles || opts["tacjp_translationFiles"] || []),
        prompt_mode: cfg.promptMode || opts["tacjp_promptMode"] || "Tag",
        search_translations: cfg.translation?.searchByTranslation ?? opts["tac_translation.searchByTranslation"] ?? true,
        show_translations: cfg.showTranslations ?? opts["tacjp_showTranslations"] ?? true,
        show_source_labels: cfg.showSourceLabels ?? opts["tacjp_showSourceLabels"] ?? false,
        color_natural_language: cfg.colorNaturalLanguage ?? opts["tacjp_colorNaturalLanguage"] ?? false,
        replace_underscores: cfg.replaceUnderscores ?? opts["tac_replaceUnderscores"] ?? true,
        append_comma: cfg.appendComma ?? opts["tac_appendComma"] ?? true,
        append_space: cfg.appendSpace ?? opts["tac_appendSpace"] ?? true,
        always_space_at_end: cfg.alwaysSpaceAtEnd ?? opts["tac_alwaysSpaceAtEnd"] ?? true,
        underscore_exclusions: cfg.replaceUnderscoresExclusionList || opts["tac_undersocreReplacementExclusionList"] || TACJP_DEFAULT_EXCLUSIONS,
        anima_artist_prefix: cfg.animaArtistPrefix || opts["tac_animaArtistPrefix"] || "Off",
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
        tacJpSetLocalSettings(response.settings || {}, name);
        if (TAC_CFG) await syncOptions();
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

function tacJpCreateSectionMarker(kind) {
    const marker = document.createElement("div");
    marker.className = `tacjp-section-marker tacjp-section-${kind}`;
    const copy = document.createElement("span");
    copy.className = "tacjp-section-copy";
    const title = document.createElement("strong");
    const subtitle = document.createElement("small");
    if (kind === "shared") {
        title.textContent = tacJpText("sharedTitle");
        subtitle.textContent = tacJpText("sharedSubtitle");
        marker.append(tacJpCreateBadge(tacJpLanguage() === "ja" ? "共通" : "SHARED", "tacjp-badge-shared"));
    } else {
        title.textContent = tacJpText("coreTitle");
        subtitle.textContent = tacJpText("coreSubtitle");
        marker.append(tacJpCreateBadge("CORE", "tacjp-badge-core"));
    }
    copy.append(title, subtitle);
    marker.append(copy);
    return marker;
}

function tacJpSetDirectLabelText(node, text) {
    if (!node) return;
    const directText = [...node.childNodes].find(child => child.nodeType === Node.TEXT_NODE && child.nodeValue.trim());
    if (directText) {
        directText.nodeValue = text;
    } else {
        const labelText = document.createElement("span");
        labelText.className = "tacjp-setting-label-text";
        labelText.textContent = text;
        node.prepend(labelText);
    }
}

function tacJpDecorateAddedSettings() {
    const settings = [
        ["tacjp_tagFiles", "tagFilesLabel"],
        ["tacjp_translationFiles", "translationFilesLabel"],
        ["tacjp_promptMode", "promptModeLabel"],
        ["tacjp_showTranslations", "showTranslationsLabel"],
        ["tacjp_showSourceLabels", "showSourceLabelsLabel"],
        ["tacjp_colorNaturalLanguage", "colorNaturalLabel"],
        ["tacjp_quickControls", "quickControlsLabel"],
        ["tac_animaArtistPrefix", "animaPrefixLabel"],
    ];
    settings.forEach(([option, textKey]) => {
        const root = gradioApp().querySelector(`#${CSS.escape(`setting_${option}`)}`);
        if (!root) return;
        const label = root.querySelector(".block-info") || root.querySelector("label > span") || root.querySelector("label");
        if (!label) return;
        tacJpSetDirectLabelText(label, tacJpText(textKey));
        if (!label.querySelector(".tacjp-badge-jpplus")) {
            label.appendChild(tacJpCreateBadge("CSV+", "tacjp-badge-jpplus"));
        }
    });

    const exclusionRoot = gradioApp().querySelector(
        `#${CSS.escape("setting_tac_undersocreReplacementExclusionList")}`
    );
    if (exclusionRoot && !exclusionRoot.querySelector(".tacjp-restore-exclusions")) {
        const button = tacJpButton(tacJpText("restoreExclusions"), async () => {
            const settings = {...tacJpCurrentSettings(), underscore_exclusions: TACJP_DEFAULT_EXCLUSIONS};
            await tacJpApplySettings(settings, opts["tacjp_activePreset"] || "", true);
            tacJpSetStatus(tacJpText("restoredExclusions"));
        }, "tacjp-action-restore tacjp-restore-exclusions");
        exclusionRoot.appendChild(button);
    }
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

function tacJpCreateSettingsManager() {
    const details = document.createElement("details");
    details.className = "tacjp-manager";
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
    heading.append(title, subtitle);
    summary.append(icon, heading, tacJpCreateBadge("CSV+", "tacjp-badge-jpplus"));
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "tacjp-manager-body";
    const status = document.createElement("span");
    status.className = "tacjp-status";

    const webuiLocale = String(opts.localization || "").trim();
    if (!webuiLocale || webuiLocale.toLowerCase() === "none") {
        const languageRow = document.createElement("div");
        languageRow.className = "tacjp-row tacjp-language-row";
        const languageLabel = document.createElement("span");
        languageLabel.textContent = `${tacJpText("language")}:`;
        const languageSelect = document.createElement("select");
        languageSelect.className = "tacjp-language-select";
        [
            ["Japanese", "日本語"],
            ["English", "English"],
        ].forEach(([value, label]) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            option.selected = value === (tacJpLanguage() === "ja" ? "Japanese" : "English");
            languageSelect.appendChild(option);
        });
        languageSelect.addEventListener("change", async () => {
            const response = await tacJpFetch("tacjp/v1/ui-language", {
                method: "POST",
                body: JSON.stringify({language: languageSelect.value}),
            });
            opts["tacjp_uiLanguage"] = response.language;
            if (TAC_CFG) TAC_CFG.uiLanguage = response.language;
            const replacement = tacJpCreateSettingsManager();
            details.replaceWith(replacement);
            gradioApp().querySelectorAll(".tacjp-section-marker").forEach(marker => {
                const kind = marker.classList.contains("tacjp-section-shared") ? "shared" : "core";
                marker.replaceWith(tacJpCreateSectionMarker(kind));
            });
            tacJpDecorateAddedSettings();
            refreshTacJpControls();
        });
        languageRow.append(languageLabel, languageSelect);
        body.appendChild(languageRow);
    }

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
    row1.append(
        presetLabel,
        presetSelect,
        applyButton,
    );

    const row2 = document.createElement("div");
    row2.className = "tacjp-row tacjp-preset-create";
    const saveAsButton = tacJpButton(tacJpText("saveAsNew"), async () => {
        const name = nameInput.value.trim();
        if (!name) throw new Error(tacJpText("enterName"));
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
    row2.append(nameInput, saveAsButton);

    const row3 = document.createElement("div");
    row3.className = "tacjp-row tacjp-buttons tacjp-preset-manage";
    const saveChangesButton = tacJpButton(tacJpText("saveChanges"), async () => {
        const name = presetSelect.value;
        if (!name) throw new Error(tacJpText("noPresetSelected"));
        await tacJpFetch("tacjp/v1/presets/save", {
            method: "POST",
            body: JSON.stringify({name, settings: tacJpCurrentSettings()}),
        });
        await tacJpLoadData();
        await tacJpApplyPreset(name);
        tacJpSetStatus(tacJpText("saved", {name}));
    }, "tacjp-action-neutral");
    const renameButton = tacJpButton(tacJpText("rename"), async () => {
        const oldName = presetSelect.value;
        const newName = nameInput.value.trim();
        if (!oldName) throw new Error(tacJpText("noPresetSelected"));
        if (!newName || newName === oldName) throw new Error(tacJpText("enterDifferentName"));
        const settings = tacJpAllPresets()[oldName];
        await tacJpFetch("tacjp/v1/presets/save", {method: "POST", body: JSON.stringify({name: newName, settings})});
        await tacJpFetch(`tacjp/v1/presets/${encodeURIComponent(oldName)}`, {method: "DELETE"});
        await tacJpLoadData();
        await tacJpApplyPreset(newName);
        nameInput.value = "";
        updatePresetActionState();
        tacJpSetStatus(tacJpText("renamed", {oldName, newName}));
    }, "tacjp-action-warning");
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
    const updatePresetActionState = () => {
        const isUserPreset = Object.prototype.hasOwnProperty.call(tacJpPresetData?.users || {}, presetSelect.value);
        applyButton.disabled = !isUserPreset;
        saveChangesButton.disabled = !isUserPreset;
        renameButton.disabled = !isUserPreset;
        deleteButton.disabled = !isUserPreset;
        [applyButton, saveChangesButton, renameButton, deleteButton].forEach(button => {
            button.title = isUserPreset ? "" : tacJpText("noPresetSelected");
        });
    };
    presetSelect.addEventListener("change", updatePresetActionState);
    row3.append(
        saveChangesButton,
        renameButton,
        deleteButton,
    );
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
    body.append(row1, row2, row3, backupDetails, status, note);
    details.appendChild(body);
    return details;
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
        .tacjp-manager,.tacjp-quick-controls{border:1px solid color-mix(in srgb,var(--primary-500,#3b82f6) 48%,var(--block-border-color,#4b5563));border-radius:8px;margin:.6rem .35rem;padding:.48rem .65rem;background:color-mix(in srgb,var(--primary-500,#3b82f6) 5%,var(--block-background-fill,#111827));box-shadow:0 2px 7px rgba(0,0,0,.18)}
        .tacjp-manager-summary{display:flex;align-items:center;gap:.55rem;cursor:pointer;min-height:2rem;list-style-position:outside}
        .tacjp-manager-heading,.tacjp-section-copy{display:flex;flex-direction:column;min-width:0;line-height:1.12}
        .tacjp-manager-heading small,.tacjp-section-copy small{font-size:.72rem;font-weight:400;opacity:.72;margin-top:.15rem}
        .tacjp-brand-icon{display:inline-grid;place-items:center;flex:0 0 1.7rem;width:1.7rem;height:1.7rem;border-radius:6px;background:linear-gradient(180deg,#3b82f6,#1d4ed8);color:#fff;font-size:.72rem;font-weight:800;letter-spacing:.02em;box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 2px 4px rgba(0,0,0,.28)}
        .tacjp-badge{display:inline-flex;align-items:center;min-height:1rem;border-radius:4px;padding:.02rem .32rem;font-size:.58rem;font-weight:800;line-height:1;letter-spacing:.035em;white-space:nowrap}
        .tacjp-badge-jpplus{margin-left:.35rem;color:#c4b5fd;background:rgba(124,58,237,.18);border:1px solid #8b5cf6}
        .tacjp-manager-summary>.tacjp-badge-jpplus{margin-left:auto}
        .tacjp-badge-shared{background:#0f766e}
        .tacjp-badge-core{background:#475569}
        .tacjp-section-marker{display:flex;align-items:center;gap:.55rem;margin:.7rem .35rem .4rem;padding:.42rem .65rem;border-radius:7px;border-left:4px solid}
        .tacjp-section-shared{border-color:#0f766e;background:color-mix(in srgb,#0f766e 9%,transparent)}
        .tacjp-section-core{border-color:#64748b;background:color-mix(in srgb,#64748b 8%,transparent)}
        .tacjp-manager-body,.tacjp-quick-grid{display:grid;gap:.6rem;margin-top:.65rem;padding:.1rem .25rem .3rem}
        .tacjp-row{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
        .tacjp-row select,.tacjp-row input,.tacjp-quick-grid select{min-height:2.15rem;background:var(--input-background-fill,#1f2937)!important;color:var(--body-text-color,#f3f4f6)!important;-webkit-text-fill-color:var(--body-text-color,#f3f4f6);border:1px solid var(--input-border-color,#64748b);border-radius:6px;padding:.3rem .55rem;box-shadow:inset 0 1px 2px rgba(0,0,0,.25)}
        .tacjp-row input::placeholder{color:color-mix(in srgb,var(--body-text-color,#f3f4f6) 58%,transparent);opacity:1}
        .tacjp-row input:focus,.tacjp-row select:focus{outline:2px solid color-mix(in srgb,var(--primary-500,#3b82f6) 75%,transparent);outline-offset:1px}
        .tacjp-name-input{min-width:14rem}
        .tacjp-language-select{min-width:6.2rem}
        .tacjp-language-row{justify-content:flex-end;padding-bottom:.15rem;border-bottom:1px solid color-mix(in srgb,var(--block-border-color,#4b5563) 65%,transparent)}
        .tacjp-preset-primary select{min-width:10rem}.tacjp-preset-create{align-items:stretch}
        .tacjp-preset-manage{padding-top:.1rem}
        .tacjp-backup{width:max-content;max-width:100%;border:1px solid var(--block-border-color,#4b5563);border-radius:6px;padding:.28rem .5rem}
        .tacjp-backup>summary{cursor:pointer;font-size:.82rem;font-weight:650}
        .tacjp-backup-actions{padding-top:.45rem}
        .tacjp-button{min-height:2.1rem;border:1px solid rgba(255,255,255,.18);border-bottom-color:rgba(0,0,0,.55);border-radius:6px;padding:.32rem .68rem;color:#fff;cursor:pointer;font-weight:600;box-shadow:inset 0 1px 0 rgba(255,255,255,.22),0 2px 3px rgba(0,0,0,.3);text-shadow:0 1px 1px rgba(0,0,0,.28);transition:filter .12s ease,transform .06s ease,box-shadow .06s ease}
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
        @media (max-width:720px){.tacjp-quick-grid{grid-template-columns:1fr}.tacjp-button{flex:1 1 auto}.tacjp-manager-heading small,.tacjp-section-copy small{display:none}}
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
            if (settingsContainer && !settingsContainer.querySelector(".tacjp-manager")) {
                const manager = tacJpCreateSettingsManager();
                settingsContainer.prepend(manager);
                manager.insertAdjacentElement("afterend", tacJpCreateSectionMarker("shared"));
                const coreSetting = settingsContainer.querySelector("#setting_tac_active")
                    || settingsContainer.querySelector("[id$='setting_tac_active']");
                if (coreSetting) coreSetting.insertAdjacentElement("beforebegin", tacJpCreateSectionMarker("core"));
            }

            if (TAC_CFG?.quickControls) {
                [["txt2img", "#txt2img_prompt"], ["img2img", "#img2img_prompt"]].forEach(([name, selector]) => {
                    const prompt = gradioApp().querySelector(selector);
                    const host = prompt?.parentElement || prompt;
                    if (!prompt || host?.querySelector(`.tacjp-quick-controls[data-tab='${name}']`)) return;
                    host?.insertBefore(tacJpCreateQuickControls(name), prompt);
                });
            } else {
                gradioApp().querySelectorAll(".tacjp-quick-controls").forEach(node => node.remove());
            }
            refreshTacJpControls();
            tacJpDecorateAddedSettings();
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
    if (!gradioApp().querySelector(".tacjp-manager") || (TAC_CFG.quickControls && !gradioApp().querySelector(".tacjp-quick-controls"))) {
        tacJpInitializeUI();
    } else {
        tacJpDecorateAddedSettings();
    }
});
