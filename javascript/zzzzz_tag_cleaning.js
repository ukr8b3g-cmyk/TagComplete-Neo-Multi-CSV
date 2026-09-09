(function () {
    "use strict";

    const cache = new Map();
    let databaseId = "";
    let installed = false;
    let warnedMissingDatabase = false;

    const css = `
        .acCleaningBadge {
            display: inline-block;
            margin-left: 0.45rem;
            padding: 0.05rem 0.35rem;
            border: 1px solid #d97706;
            border-radius: 999px;
            color: #f59e0b;
            font-size: 0.72em;
            font-weight: 600;
            vertical-align: middle;
        }
        .acCleaningSuggestions {
            margin-top: 0.2rem;
            color: var(--meta-text-color);
            font-size: 0.75em;
            line-height: 1.25;
        }
    `;

    function injectStyle() {
        if (document.getElementById("tacjp-tag-cleaning-style")) return;
        const style = document.createElement("style");
        style.id = "tacjp-tag-cleaning-style";
        style.textContent = css;
        document.head.appendChild(style);
    }

    function enabled() {
        return !!globalThis.opts?.["tacjp_cleaningEnabled"];
    }

    function keyFor(result) {
        const category = Number.isInteger(Number(result?.category))
            ? Number(result.category)
            : "";
        return `${category}:${String(result?.text || "").trim().toLocaleLowerCase()}`;
    }

    function eligible(result) {
        if (!result || !result.text) return false;
        if (typeof ResultType !== "undefined" && result.type !== ResultType.tag) return false;
        const scheme = String(result.categoryScheme || "danbooru");
        return scheme === "danbooru";
    }

    async function fetchUnknown(results) {
        const unique = [];
        const seen = new Set();
        for (const result of results) {
            if (!eligible(result)) continue;
            const key = keyFor(result);
            if (!key || cache.has(key) || seen.has(key)) continue;
            seen.add(key);
            unique.push({
                key,
                tag: String(result.text || ""),
                category: Number.isInteger(Number(result.category))
                    ? Number(result.category)
                    : null,
            });
        }
        if (unique.length === 0) return;

        const response = await fetch("tacjp/v1/cleaning/lookup", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                items: unique.map(item => ({tag: item.tag, category: item.category})),
            }),
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        if (!data?.enabled) return;
        if (!data?.ready) {
            if (!warnedMissingDatabase) {
                warnedMissingDatabase = true;
                console.info(
                    "[TagComplete Neo Multi-CSV] Tag Cleaning is enabled but its SQLite "
                    + "database is not ready. Use Settings > Tag Autocomplete / Multi-CSV "
                    + "> Tag Cleaning database update."
                );
            }
            return;
        }
        const nextDatabaseId = String(data.database_id || "");
        if (databaseId && nextDatabaseId && nextDatabaseId !== databaseId) cache.clear();
        if (nextDatabaseId) databaseId = nextDatabaseId;
        const rows = Array.isArray(data.results) ? data.results : [];
        rows.forEach((row, index) => {
            const key = unique[index]?.key;
            if (key) cache.set(key, row?.match || null);
        });
    }

    function clearAnnotation(li) {
        li?.querySelectorAll?.(".acCleaningBadge, .acCleaningSuggestions")
            .forEach(node => node.remove());
    }

    function annotate(li, result) {
        if (!li?.isConnected || !eligible(result)) return;
        clearAnnotation(li);
        const info = cache.get(keyFor(result));
        if (!info) return;

        const label = li.querySelector(".acListItem");
        if (info.warning && label) {
            const badge = document.createElement("span");
            badge.className = "acCleaningBadge";
            badge.textContent = "⚠ correction";
            const removed = Number(info.remove_count || 0).toLocaleString();
            const added = Number(info.add_count || 0).toLocaleString();
            const ratio = Math.round(Number(info.remove_ratio || 0) * 100);
            badge.title = `Correction data: removed ${removed}, added ${added} (${ratio}% remove share). This does not mean the Danbooru tag is deprecated.`;
            label.appendChild(badge);
        }

        const suggestions = Array.isArray(info.suggestions) ? info.suggestions : [];
        if (suggestions.length > 0) {
            const suggestionLine = document.createElement("div");
            suggestionLine.className = "acCleaningSuggestions";
            suggestionLine.textContent = "Related adds: " + suggestions
                .map(item => `${item.tag} (${Math.round(Number(item.confidence || 0) * 100)}%)`)
                .join(", ");
            suggestionLine.title = "Tags frequently added in the same correction rows. Hints only; not automatic replacements.";
            li.appendChild(suggestionLine);
        }
    }

    function listItemsFor(textArea, resultCount) {
        try {
            const textAreaId = getTextAreaIdentifier(textArea);
            const resultDiv = gradioApp().querySelector(`.autocompleteResults${textAreaId}`);
            const nodes = Array.from(resultDiv?.querySelectorAll?.("ul > li") || []);
            return nodes.slice(Math.max(0, nodes.length - resultCount));
        } catch {
            return [];
        }
    }

    function install() {
        if (installed) return;
        if (typeof addResultsToList !== "function" || typeof gradioApp !== "function") {
            setTimeout(install, 50);
            return;
        }
        installed = true;
        injectStyle();
        const original = addResultsToList;
        addResultsToList = function tagCleaningAddResults(textArea, results, ...rest) {
            const output = original.call(this, textArea, results, ...rest);
            if (!enabled() || !Array.isArray(results) || results.length === 0) {
                return output;
            }
            const resultSnapshot = results.slice();
            const nodes = listItemsFor(textArea, resultSnapshot.length);
            resultSnapshot.forEach((result, index) => annotate(nodes[index], result));
            fetchUnknown(resultSnapshot)
                .then(() => {
                    resultSnapshot.forEach((result, index) => annotate(nodes[index], result));
                })
                .catch(error => {
                    console.debug(
                        "[TagComplete Neo Multi-CSV] Tag Cleaning lookup failed",
                        error,
                    );
                });
            return output;
        };
        console.info(
            "[TagComplete Neo Multi-CSV] Optional Tag Cleaning UI hook loaded (default OFF)."
        );
    }

    install();
})();
