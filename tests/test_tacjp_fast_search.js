const assert = require("assert");
const core = require("../javascript/tacjp_fast_search_core.js");

assert.deepStrictEqual(core.optionList(["a.csv", "None", ""]), ["a.csv"]);
assert.strictEqual(core.clampLimit(5000), 1000);
assert.strictEqual(core.eligibleQuery("long", "__"), true);
assert.strictEqual(core.eligibleQuery("__wildcards/eye-color__", "__"), false);
assert.strictEqual(core.eligibleQuery("<lora:test", "__"), false);
assert.strictEqual(core.contextLooksNatural("a girl with soft", 16), true);

const requestConfig = {
    tagFiles: ["danbooru.csv", "natural.csv"],
    translation: {
        translationFiles: ["ja.csv"],
        searchByTranslation: true,
    },
    alias: {searchByAlias: true},
    promptMode: "Hybrid",
    candidateSortMode: "Relevance",
    showSourceLabels: false,
    extra: {extraFile: "extra-quality-tags.csv"},
};
const request = core.makeRequest(
    requestConfig,
    "*髪",
    "1girl, 髪",
    8,
    {resultPool: 300},
);
assert.strictEqual(request.query, "髪");
assert.strictEqual(request.substring_only, true);
assert.strictEqual(request.limit, 300);
assert.strictEqual(request.candidate_sort_mode, "Relevance");
assert.deepStrictEqual(
    request.tag_files,
    ["danbooru.csv", "natural.csv"],
);
assert.deepStrictEqual(request.translation_files, ["ja.csv"]);

assert.deepStrictEqual(
    core.makeWarmupRequest({
        tagFiles: ["danbooru.csv", "natural.csv"],
        translation: {translationFiles: ["ja.csv"]},
    }),
    {
        tag_files: ["danbooru.csv", "natural.csv"],
        translation_files: ["ja.csv"],
    },
);

assert.strictEqual(
    core.makeRequest(
        {...requestConfig, candidateSortMode: "Count"},
        "earrings",
        "earrings",
        8,
        {resultPool: 300},
    ).candidate_sort_mode,
    "Count",
);

console.log("tacjp fast search core tests passed");
