(function () {
    "use strict";

    let installed = false;
    let remoteDisabledForSession = false;
    let activeController = null;
    let requestSequence = 0;

    function install() {
        if (installed) return;
        if (
            typeof loadTags !== "function"
            || typeof BaseTagParser === "undefined"
            || typeof PARSERS === "undefined"
            || typeof AutocompleteResult === "undefined"
            || typeof ResultType === "undefined"
            || typeof TACJPFastSearchCore === "undefined"
        ) {
            setTimeout(install, 50);
            return;
        }
        installed = true;

        const legacyLoadTags = loadTags;
        const normalizeSearch = value => globalThis.TACJPCore?.normalizeSearch
            ? globalThis.TACJPCore.normalizeSearch(value)
            : String(value || "").toLocaleLowerCase().replaceAll("_", " ").trim();
        const matchScore = (value, query, substringOnly) => globalThis.TACJPCore?.matchScore
            ? globalThis.TACJPCore.matchScore(value, query, substringOnly)
            : (() => {
                const candidate = normalizeSearch(value);
                const needle = normalizeSearch(query);
                if (!candidate || !needle) return 99;
                if (substringOnly) return candidate.includes(needle) ? 30 : 99;
                if (candidate === needle) return 0;
                if (candidate.startsWith(needle)) return 10;
                return candidate.includes(needle) ? 30 : 99;
            })();

        function stableSortKey(group, score, count, text) {
            const boundedCount = Math.max(0, Math.min(999999999999, Number(count) || 0));
            const inverseCount = String(999999999999 - boundedCount).padStart(12, "0");
            return `${group}:${String(Number(score) || 0).padStart(4, "0")}:${inverseCount}:${normalizeSearch(text)}`;
        }

        function serverSelected() {
            return !remoteDisabledForSession
                && !TAC_CFG?.translation?.liveTranslation
                && String(opts?.["tacjp_searchEngine"] || "Server index") !== "Legacy browser";
        }

        async function switchToLegacy(error) {
            if (remoteDisabledForSession) return;
            remoteDisabledForSession = true;
            console.warn(
                "[TagComplete Neo Multi-CSV] Server search unavailable; "
                + "falling back to the legacy browser index for this session.",
                error,
            );
            allTags = [];
            tagIndex?.clear?.();
            translations.clear();
            tagsLoaded = false;
            await legacyLoadTags(TAC_CFG);
            if (TAC_CFG?.useIndexedSearch && allTags.length > 0) await buildTagIndex();
            tagsLoaded = true;
        }

        // Keep lazy loading, but in server mode do not transfer the complete merged
        // dataset to the browser. The legacy extra-file list stays local because it
        // has separate Insert before/after semantics in upstream TagComplete.
        loadTags = async function fastLoadTags(config) {
            if (!serverSelected()) return legacyLoadTags(config);
            allTags = [];
            tagIndex?.clear?.();
            translations.clear();
            await loadExtraTags(config);
        };

        let previousServerMode = serverSelected();
        if (typeof QUEUE_AFTER_CONFIG_CHANGE !== "undefined") {
            QUEUE_AFTER_CONFIG_CHANGE.push(async () => {
                const nextServerMode = serverSelected();
                if (nextServerMode === previousServerMode) return;
                previousServerMode = nextServerMode;
                allTags = [];
                tagIndex?.clear?.();
                translations.clear();
                tagsLoaded = false;
                if (nextServerMode) {
                    await loadTags(TAC_CFG);
                } else {
                    await legacyLoadTags(TAC_CFG);
                    if (TAC_CFG?.useIndexedSearch && allTags.length > 0) {
                        await buildTagIndex();
                    }
                }
                tagsLoaded = true;
            });
        }

        function appendLocalExtraResults(output, body) {
            if (!Array.isArray(extras) || extras.length === 0) return output;
            if (!TAC_CFG?.extra?.extraFile || TAC_CFG.extra.extraFile === "None") return output;

            const existing = new Set(output.map(result => normalizeSearch(result.text)));
            const group = TAC_CFG.extra.addMode === "Insert before" ? "0" : "2";
            for (const row of extras) {
                const text = String(row?.[0] || "").trim();
                if (!text || existing.has(normalizeSearch(text))) continue;
                const fields = [text];
                if (body.search_aliases && row?.[3]) fields.push(...String(row[3]).split(","));
                if (body.search_translations && row?.[4]) fields.push(String(row[4]));
                const score = Math.min(...fields.map(value => matchScore(value, body.query, body.substring_only)));
                if (!Number.isFinite(score) || score >= 99) continue;

                const result = new AutocompleteResult(text, ResultType.extra);
                result.category = row?.[1] || 0;
                result.meta = row?.[2] || "Custom tag";
                result.aliases = String(row?.[3] || "");
                result.translation = String(row?.[4] || "");
                result.sourceType = "custom";
                result.sourceTypes = ["custom"];
                result.sourceFiles = [TAC_CFG.extra.extraFile];
                result.insertMode = "tag";
                result.categoryScheme = "custom";
                result.matchScore = score;
                result.sortKey = stableSortKey(group, score, 0, text);
                if (result.translation) translations.set(text, result.translation);
                output.push(result);
                existing.add(normalizeSearch(text));
            }
            return output;
        }

        class ServerTagParser extends BaseTagParser {
            constructor() {
                super(() => {
                    if (!serverSelected() || !TAC_CFG) return false;
                    return TACJPFastSearchCore.eligibleQuery(tagword, TAC_CFG.wcWrap || "__");
                });
            }

            async parse(textArea, prompt) {
                const sequence = ++requestSequence;
                if (activeController) activeController.abort();
                activeController = new AbortController();

                if (typeof updateTacStatusDot === "function") updateTacStatusDot("loading");
                const body = TACJPFastSearchCore.makeRequest(
                    TAC_CFG,
                    tagword,
                    prompt,
                    textArea?.selectionStart ?? String(prompt || "").length,
                    {resultPool: opts?.["tacjp_serverResultPool"] || 250},
                );
                if (!body.query || body.tag_files.length === 0) {
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("ready");
                    return appendLocalExtraResults([], body);
                }

                try {
                    const response = await fetch("tacjp/v1/search", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body),
                        signal: activeController.signal,
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    const data = await response.json();
                    if (sequence !== requestSequence) return [];
                    if (!data || !Array.isArray(data.results)) {
                        throw new Error(data?.error || "Search API returned no results array");
                    }
                    const output = [];
                    for (const row of data.results) {
                        const text = String(row?.[0] || "").trim();
                        if (!text) continue;
                        const result = new AutocompleteResult(text, ResultType.tag);
                        result.category = row[1];
                        result.count = Number(row[2]) || 0;
                        result.aliases = String(row[3] || "");
                        result.translation = String(row[4] || "");
                        result.sourceType = String(row[5] || "tag");
                        result.insertMode = String(row[6] || "tag");
                        result.categoryScheme = String(row[7] || "danbooru");
                        result.sourceFiles = Array.isArray(row[8]) ? row[8] : [];
                        result.sourceTypes = [result.sourceType];
                        result.matchScore = Number(row[9]) || 0;
                        result.sortKey = stableSortKey(
                            "1",
                            result.matchScore,
                            result.count,
                            text,
                        );
                        if (result.translation) translations.set(text, result.translation);
                        output.push(result);
                    }
                    appendLocalExtraResults(output, body);
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("ready");
                    if (opts?.["tacjp_searchDebug"]) {
                        console.debug("[TagComplete Neo Multi-CSV] server search", data);
                    }
                    return output;
                } catch (error) {
                    if (error?.name === "AbortError" || sequence !== requestSequence) return [];
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("error");
                    await switchToLegacy(error);
                    return [];
                }
            }
        }

        PARSERS.push(new ServerTagParser());
        console.info("[TagComplete Neo Multi-CSV] Persistent server search enabled.");
    }

    install();
})();
