const assert = require("assert");
const core = require("../javascript/tacjp_fast_search_core.js");

assert.deepStrictEqual(core.optionList(["a.csv", "None", ""]), ["a.csv"]);
assert.strictEqual(core.clampLimit(5000), 1000);
assert.strictEqual(core.eligibleQuery("long", "__"), true);
assert.strictEqual(core.eligibleQuery("__wildcards/eye-color__", "__"), false);
assert.strictEqual(core.eligibleQuery("<lora:test", "__"), false);
assert.strictEqual(core.contextLooksNatural("a girl with soft", 16), true);

const request = core.makeRequest(
    {
        tagFiles: ["danbooru.csv", "natural.csv"],
        translation: {
            translationFiles: ["ja.csv"],
            searchByTranslation: true,
        },
        alias: {searchByAlias: true},
        promptMode: "Hybrid",
        showSourceLabels: false,
        extra: {extraFile: "extra-quality-tags.csv"},
    },
    "*髪",
    "1girl, 髪",
    8,
    {resultPool: 300},
);
assert.strictEqual(request.query, "髪");
assert.strictEqual(request.substring_only, true);
assert.strictEqual(request.limit, 300);
assert.deepStrictEqual(
    request.tag_files,
    ["danbooru.csv", "natural.csv", "extra-quality-tags.csv"],
);
assert.deepStrictEqual(request.translation_files, ["ja.csv"]);

console.log("tacjp fast search core tests passed");
