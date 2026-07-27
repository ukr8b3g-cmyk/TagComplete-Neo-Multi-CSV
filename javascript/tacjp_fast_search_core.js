(function (root, factory) {
    const api = factory();
    root.TACJPFastSearchCore = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    function optionList(value) {
        if (Array.isArray(value)) return value.filter(item => item && item !== "None");
        if (typeof value === "string" && value && value !== "None") return [value];
        return [];
    }

    function clampLimit(value, fallback = 250) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return fallback;
        return Math.max(20, Math.min(1000, Math.floor(parsed)));
    }

    function eligibleQuery(query, wildcardWrapper = "__") {
        const value = String(query || "").trim();
        if (!value) return false;
        if (value.startsWith("<") || value.startsWith("$") || value.startsWith("#")) return false;
        if (wildcardWrapper && value.startsWith(wildcardWrapper)) return false;
        return true;
    }

    function contextLooksNatural(prompt, cursor) {
        const text = String(prompt || "");
        const end = Number.isFinite(Number(cursor)) ? Number(cursor) : text.length;
        const before = text.slice(0, end);
        const segment = before.slice(Math.max(before.lastIndexOf(","), before.lastIndexOf("\n")) + 1);
        return /\s/.test(segment.trim())
            || /\b(a|an|the|with|in|on|at|from|under|over|near|while)\b/i.test(segment);
    }

    function makeRequest(config, query, prompt, cursor, options) {
        const settings = options || {};
        const rawQuery = String(query || "").replace(/[\n\r]/g, "");
        const substringOnly = rawQuery.startsWith("*");
        const tagFiles = optionList(config?.tagFiles);
        const extraFile = config?.extra?.extraFile;
        if (extraFile && extraFile !== "None" && !tagFiles.includes(extraFile)) {
            tagFiles.push(extraFile);
        }
        return {
            query: substringOnly ? rawQuery.slice(1) : rawQuery,
            tag_files: tagFiles,
            translation_files: optionList(config?.translation?.translationFiles),
            prompt_mode: config?.promptMode || "Tag",
            context_natural: contextLooksNatural(prompt, cursor),
            search_aliases: config?.alias?.searchByAlias !== false,
            search_translations: config?.translation?.searchByTranslation !== false,
            substring_only: substringOnly,
            limit: clampLimit(settings.resultPool, 250),
            include_sources: !!config?.showSourceLabels,
        };
    }

    return {optionList, clampLimit, eligibleQuery, contextLooksNatural, makeRequest};
});
