const assert = require("assert");
require("../javascript/tacjp_fast_search_core.js");

global.opts = {
    tacjp_searchEngine: "Server index",
    tacjp_serverResultPool: 250,
    tacjp_searchDebug: false,
};
global.TAC_CFG = {
    tagFiles: ["danbooru.csv"],
    promptMode: "Tag",
    wcWrap: "__",
    useIndexedSearch: true,
    showSourceLabels: false,
    alias: {searchByAlias: true},
    translation: {
        translationFiles: ["ja.csv"],
        searchByTranslation: true,
        liveTranslation: false,
    },
    extra: {extraFile: "None"},
};
global.QUEUE_AFTER_CONFIG_CHANGE = [];
global.tagword = "long";
global.allTags = [];
global.tagIndex = new Map();
global.translations = new Map();
global.tagsLoaded = false;
global.loadExtraTags = async () => {};
global.buildTagIndex = async () => {};
let legacyLoads = 0;
global.loadTags = async () => { legacyLoads += 1; };
global.BaseTagParser = class {
    constructor(triggerCondition) {
        this.triggerCondition = triggerCondition;
    }
};
global.PARSERS = [];
global.ResultType = {tag: 1};
global.AutocompleteResult = class {
    constructor(text, type) {
        this.text = text;
        this.type = type;
    }
};
global.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    assert.strictEqual(body.query, "long");
    return {
        ok: true,
        json: async () => ({
            results: [
                [
                    "long_hair",
                    0,
                    100,
                    "longhair",
                    "長髪",
                    "tag",
                    "tag",
                    "danbooru",
                    [],
                    10,
                ],
            ],
        }),
    };
};

require("../javascript/zzzz_tacjp_fast_search.js");

(async () => {
    assert.strictEqual(PARSERS.length, 1);
    await loadTags(TAC_CFG);
    assert.strictEqual(legacyLoads, 0);
    const parser = PARSERS[0];
    assert.strictEqual(parser.triggerCondition(), true);
    const results = await parser.parse({selectionStart: 4}, "long");
    assert.strictEqual(results.length, 1);
    assert.strictEqual(results[0].text, "long_hair");
    assert.strictEqual(results[0].translation, "長髪");
    assert.strictEqual(translations.get("long_hair"), "長髪");

    // Experimental full-prompt live translation requires the complete local map,
    // so changing to that mode must load the legacy browser dataset automatically.
    TAC_CFG.translation.liveTranslation = true;
    await QUEUE_AFTER_CONFIG_CHANGE[0]();
    assert.strictEqual(legacyLoads, 1);
    assert.strictEqual(parser.triggerCondition(), false);
    console.log("tacjp fast search integration tests passed");
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
