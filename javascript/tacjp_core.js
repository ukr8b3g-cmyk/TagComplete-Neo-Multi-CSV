/**
 * Pure helpers shared by TagComplete Neo Multi-CSV runtime code and Node tests.
 * This file intentionally has no DOM or WebUI dependencies.
 */
(function initTacJpCore(root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    if (root) root.TACJPCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function buildTacJpCore() {
    "use strict";

    function optionList(value, fallback = []) {
        let output = [];
        if (Array.isArray(value)) {
            output = value;
        } else if (typeof value === "string") {
            const text = value.trim();
            if (text.startsWith("[") && text.endsWith("]")) {
                try {
                    const parsed = JSON.parse(text);
                    if (Array.isArray(parsed)) output = parsed;
                } catch {
                    output = [];
                }
            }
            if (output.length === 0 && text && text !== "None") output = [text];
        }
        const seen = new Set();
        const cleaned = output
            .map(item => String(item || "").trim())
            .filter(item => item && item !== "None")
            .filter(item => {
                const key = item.toLocaleLowerCase();
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });
        return cleaned.length > 0 ? cleaned : [...fallback];
    }

    function parsePatterns(value) {
        const values = Array.isArray(value) ? value : String(value || "").split(/[,\n\r]+/);
        const seen = new Set();
        return values
            .map(item => String(item || "").trim())
            .filter(Boolean)
            .filter(item => {
                const key = item.toLocaleLowerCase();
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });
    }

    function globToRegex(pattern) {
        let escaped = String(pattern || "").replace(/[.+^${}()|[\]\\]/g, "\\$&");
        escaped = escaped.replace(/\*/g, ".*").replace(/\?/g, ".");
        return new RegExp(`^${escaped}$`, "iu");
    }

    function isUnderscoreProtected(text, patterns, wrapper = "__") {
        const value = String(text || "");
        const wrap = String(wrapper || "__");
        if (wrap && value.startsWith(wrap) && value.endsWith(wrap) && value.length >= wrap.length * 2) {
            return true;
        }
        return parsePatterns(patterns).some(pattern => {
            try {
                return globToRegex(pattern).test(value);
            } catch {
                return pattern.toLocaleLowerCase() === value.toLocaleLowerCase();
            }
        });
    }

    function normalizeSearch(value, preserveTrailingSeparator = false) {
        const raw = String(value || "")
            .normalize("NFKC")
            .toLocaleLowerCase();
        const hasTrailingSeparator = preserveTrailingSeparator && raw.endsWith("_");
        const normalized = raw
            .replaceAll("_", " ")
            .replace(/\s+/g, " ")
            .trim();
        return hasTrailingSeparator && normalized ? `${normalized} ` : normalized;
    }

    function matchScore(value, query, substringOnly = false) {
        const candidate = normalizeSearch(value);
        const needle = normalizeSearch(query, true);
        if (!candidate || !needle) return 99;
        if (substringOnly) return candidate.includes(needle) ? 30 : 99;
        if (candidate === needle) return 0;
        if (candidate.startsWith(needle)) return 10;
        const words = candidate.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
        if (words.some(word => word.startsWith(needle))) return 20;
        return candidate.includes(needle) ? 30 : 99;
    }

    function sourcePenalty(promptMode, sourceType, contextLooksNatural) {
        const mode = String(promptMode || "Tag");
        const source = String(sourceType || "tag");
        const natural = source === "natural_language";
        if (mode === "Natural Language") return natural ? 0 : 40;
        if (mode === "Tag") return natural ? 40 : 0;
        if (mode === "Hybrid") {
            return contextLooksNatural ? (natural ? 0 : 12) : (natural ? 12 : 0);
        }
        return 0;
    }

    function separatorForInsertMode(insertMode, config = {}, context = {}) {
        const mode = String(insertMode || "tag");
        const beforeSeparator = Boolean(context.beforeSeparator);
        const atEnd = Boolean(context.atEnd);
        if (mode === "raw" || mode === "wildcard") return "";
        if (mode === "word") {
            if (beforeSeparator) return "";
            return (config.appendSpace || (config.alwaysSpaceAtEnd && atEnd)) ? " " : "";
        }

        let separator = "";
        if (config.appendComma && !beforeSeparator) separator = ",";
        if (config.appendSpace && !beforeSeparator) separator += " ";
        if (!config.appendSpace && config.alwaysSpaceAtEnd && atEnd) separator += " ";
        return separator;
    }

    /**
     * Return the longest multi-word suffix before the cursor that is a prefix
     * of a selected natural-language phrase. This lets typing `soft nat` and
     * choosing `soft natural lighting` replace the whole partial phrase rather
     * than producing `soft soft natural lighting`.
     */
    function phraseReplacementRange(prompt, cursor, selectedText) {
        const text = String(prompt || "");
        const end = Math.max(0, Math.min(Number(cursor) || 0, text.length));
        const selected = normalizeSearch(selectedText);
        if (!selected || !selected.includes(" ")) return null;

        const before = text.slice(0, end);
        const boundary = Math.max(before.lastIndexOf(","), before.lastIndexOf("\n"), before.lastIndexOf("\r")) + 1;
        const segment = before.slice(boundary);
        const words = [...segment.matchAll(/\S+/gu)];
        if (words.length < 2) return null;

        for (let index = 0; index < words.length - 1; index++) {
            const startInSegment = words[index].index;
            const candidate = normalizeSearch(segment.slice(startInSegment));
            if (candidate.includes(" ") && selected.startsWith(candidate)) {
                return {start: boundary + startInSegment, end};
            }
        }
        return null;
    }

    function resolveTagWeightTarget(value, selectionStart, selectionEnd) {
        const text = String(value ?? "");
        let start = Math.max(0, Math.min(Number(selectionStart) || 0, text.length));
        let end = Math.max(start, Math.min(Number(selectionEnd) || start, text.length));

        if (start === end) {
            const before = text.slice(0, start);
            const leftBoundary = Math.max(
                before.lastIndexOf(","),
                before.lastIndexOf("\n"),
                before.lastIndexOf("\r"),
            );
            start = leftBoundary + 1;

            const after = text.slice(end);
            const rightOffsets = [
                after.indexOf(","),
                after.indexOf("\n"),
                after.indexOf("\r"),
            ].filter(index => index >= 0);
            end = rightOffsets.length > 0
                ? end + Math.min(...rightOffsets)
                : text.length;
        }

        while (start < end && /\s/u.test(text[start])) start++;
        while (end > start && /\s/u.test(text[end - 1])) end--;
        if (start >= end) return null;

        const raw = text.slice(start, end);
        const unsupported = raw.includes("__")
            || ["[", "]", "<", ">", "{", "}", "|", "\r", "\n", ","].some(char => raw.includes(char))
            || raw.startsWith("$")
            || /^(?:embedding|emb):/iu.test(raw);
        if (unsupported) return null;

        const weighted = raw.match(
            /^\((.+):([+-]?(?:\d+(?:\.\d+)?|\.\d+))\)$/u,
        );
        if (weighted) {
            const baseText = weighted[1].trim();
            const weight = Number(weighted[2]);
            const unsupportedBase = !baseText
                || baseText.includes("__")
                || ["(", ")", "[", "]", "<", ">", "{", "}", "|", ",", ":", "\r", "\n"].some(char => baseText.includes(char))
                || baseText.startsWith("$")
                || /^(?:embedding|emb):/iu.test(baseText);
            if (unsupportedBase || !Number.isFinite(weight)) return null;

            return {
                start,
                end,
                raw,
                baseText,
                weight,
                open: "(",
                close: ")",
            };
        }

        if (raw.includes("(") || raw.includes(")") || raw.includes(":")) return null;

        return {
            start,
            end,
            raw,
            baseText: raw,
            weight: 1.0,
            open: "(",
            close: ")",
        };
    }

    function adjustTagWeight(value, selectionStart, selectionEnd, direction) {
        const target = resolveTagWeightTarget(value, selectionStart, selectionEnd);
        if (!target) return null;

        const numericDirection = Number(direction);
        if (!Number.isFinite(numericDirection) || numericDirection === 0) return null;

        const nextWeight = Math.max(
            0,
            Math.round((target.weight + Math.sign(numericDirection) * 0.05) * 100) / 100,
        );
        if (Math.abs(nextWeight - target.weight) < 1e-9) return null;

        const replacement = Math.abs(nextWeight - 1.0) < 1e-9
            ? target.baseText
            : `(${target.baseText}:${nextWeight.toFixed(2)})`;
        const text = String(value ?? "");

        return {
            value: text.slice(0, target.start) + replacement + text.slice(target.end),
            start: target.start,
            end: target.start + replacement.length,
            replacement,
            weight: nextWeight,
        };
    }

    return {
        optionList,
        parsePatterns,
        globToRegex,
        isUnderscoreProtected,
        normalizeSearch,
        matchScore,
        sourcePenalty,
        separatorForInsertMode,
        phraseReplacementRange,
        resolveTagWeightTarget,
        adjustTagWeight,
    };
});
