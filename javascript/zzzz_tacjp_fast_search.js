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

        function serverSelected() {
            return !remoteDisabledForSession
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
        // dataset to the browser. Extra tags stay local for compatibility.
        loadTags = async function fastLoadTags(config) {
            if (!serverSelected()) return legacyLoadTags(config);
            allTags = [];
            tagIndex?.clear?.();
            translations.clear();
            await loadExtraTags(config);
        };

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

                const body = TACJPFastSearchCore.makeRequest(
                    TAC_CFG,
                    tagword,
                    prompt,
                    textArea?.selectionStart ?? String(prompt || "").length,
                    {resultPool: opts?.["tacjp_serverResultPool"] || 250},
                );
                if (!body.query || body.tag_files.length === 0) return [];

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
                        // The original parser pipeline applies its normal name sort.
                        // Prefixing the sort key preserves server relevance when local
                        // frequency sorting is disabled; frequency sorting still uses
                        // matchScore as its primary criterion.
                        result.sortKey = `${String(result.matchScore).padStart(4, "0")}:${text}`;
                        if (result.translation) translations.set(text, result.translation);
                        output.push(result);
                    }
                    if (opts?.["tacjp_searchDebug"]) {
                        console.debug("[TagComplete Neo Multi-CSV] server search", data);
                    }
                    return output;
                } catch (error) {
                    if (error?.name === "AbortError" || sequence !== requestSequence) return [];
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
